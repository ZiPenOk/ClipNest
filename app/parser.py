import asyncio
import html
import json
import re
from typing import Any, Protocol
from urllib.parse import unquote, urlencode, urlsplit, urlunsplit

import httpx

from .config import normalize_cookie_header, settings


class ParserError(RuntimeError):
    pass


def _get_play_addr_url(video_rate: dict[str, Any]) -> str | None:
    play_addr = video_rate.get("play_addr") or {}
    url_list = play_addr.get("url_list") or []
    return url_list[0] if url_list else None


def _video_rate_sort_key(video_rate: dict[str, Any]) -> tuple[int, int, int]:
    play_addr = video_rate.get("play_addr") or {}
    width = int(play_addr.get("width") or 0)
    height = int(play_addr.get("height") or 0)
    bit_rate = int(video_rate.get("bit_rate") or 0)
    return max(width, height), min(width, height), bit_rate


def _video_rate_is_h265(video_rate: dict[str, Any]) -> bool:
    gear_name = str(video_rate.get("gear_name") or "")
    return bool(video_rate.get("is_h265")) or gear_name.startswith("adapt_lowest")


def get_best_bit_rate_video_url(video_data: dict[str, Any]) -> str | None:
    bit_rates = [
        item for item in video_data.get("bit_rate") or []
        if isinstance(item, dict) and _get_play_addr_url(item)
    ]
    if not bit_rates:
        return None
    sorted_bit_rates = sorted(bit_rates, key=_video_rate_sort_key, reverse=True)
    best_video_rate = sorted_bit_rates[0]
    h265_bit_rates = [
        item for item in bit_rates
        if str(item.get("gear_name") or "").startswith("adapt_lowest")
    ]
    sorted_h265_bit_rates = sorted(h265_bit_rates, key=_video_rate_sort_key, reverse=True)
    if sorted_h265_bit_rates:
        best_h265_rate = sorted_h265_bit_rates[0]
        best_min_side = min(_video_rate_sort_key(best_video_rate)[:2])
        h265_min_side = min(_video_rate_sort_key(best_h265_rate)[:2])
        if h265_min_side >= best_min_side:
            best_video_rate = best_h265_rate
    return _get_play_addr_url(best_video_rate)


def get_bit_rate_video_candidates(video_data: dict[str, Any]) -> list[dict[str, Any]]:
    best_by_shape: dict[tuple[int, int, int], dict[str, Any]] = {}
    for item in video_data.get("bit_rate") or []:
        if not isinstance(item, dict):
            continue
        play_addr = item.get("play_addr") or {}
        url_list = [url for url in play_addr.get("url_list") or [] if isinstance(url, str) and url]
        if not url_list:
            continue
        width = int(play_addr.get("width") or 0)
        height = int(play_addr.get("height") or 0)
        fps = int(item.get("FPS") or item.get("fps") or 0)
        bit_rate = int(item.get("bit_rate") or 0)
        data_size = int(play_addr.get("data_size") or 0)
        key = (width, height, fps)
        previous = best_by_shape.get(key)
        previous_score = (
            int(_video_rate_is_h265(previous or {})),
            int((previous or {}).get("data_size") or 0),
            int((previous or {}).get("bit_rate") or 0),
        )
        score = (int(_video_rate_is_h265(item)), data_size, bit_rate)
        if previous is None or score > previous_score:
            best_by_shape[key] = {
                "url": url_list[0],
                "back_urls": url_list[1:],
                "width": width,
                "height": height,
                "fps": fps,
                "bit_rate": bit_rate,
                "data_size": data_size,
                "format": item.get("format"),
                "gear_name": item.get("gear_name"),
                "quality_type": item.get("quality_type"),
                "is_h265": _video_rate_is_h265(item),
            }
    return sorted(
        best_by_shape.values(),
        key=lambda item: (
            max(int(item.get("width") or 0), int(item.get("height") or 0)),
            min(int(item.get("width") or 0), int(item.get("height") or 0)),
            int(bool(item.get("is_h265"))),
            int(item.get("data_size") or 0),
            int(item.get("bit_rate") or 0),
        ),
        reverse=True,
    )


class ParserAdapter(Protocol):
    name: str

    async def parse(self, url: str) -> dict[str, Any]:
        ...

    async def health(self) -> dict[str, Any]:
        ...

    def info(self) -> dict[str, Any]:
        ...


class DouyinDetailSigner(Protocol):
    name: str

    async def sign(self, params: dict[str, Any], user_agent: str) -> dict[str, Any]:
        ...


class NoopDouyinDetailSigner:
    name = "none"

    async def sign(self, params: dict[str, Any], user_agent: str) -> dict[str, Any]:
        return dict(params)


class LocalABogusSigner:
    name = "local_abogus"

    async def sign(self, params: dict[str, Any], user_agent: str) -> dict[str, Any]:
        try:
            from .vendor.f2_abogus import ABogus
        except ImportError as exc:
            raise ParserError("Local A-Bogus signer dependency is missing") from exc
        query = urlencode(params)
        try:
            _, a_bogus, _ = ABogus(user_agent=user_agent).generate_abogus(params=query, request="GET")
        except Exception as exc:
            raise ParserError(f"Local A-Bogus generation failed: {exc}") from exc
        signed = dict(params)
        signed["a_bogus"] = a_bogus
        return signed


def create_douyin_signer(parser_settings: dict[str, Any] | None = None) -> DouyinDetailSigner:
    return LocalABogusSigner()


class NativeDouyinParserAdapter:
    name = "native_douyin"
    detail_endpoint = "https://www.douyin.com/aweme/v1/web/aweme/detail/"
    share_endpoint = "https://www.douyin.com/share/video/{aweme_id}"
    author_post_endpoint = "https://www.douyin.com/aweme/v1/web/aweme/post/"
    _ROUTER_DATA_RE = re.compile(r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", re.S)

    _ID_PATTERNS = (
        re.compile(r"/video/(\d+)"),
        re.compile(r"/note/(\d+)"),
        re.compile(r"/share/video/(\d+)"),
        re.compile(r"[?&](?:modal_id|aweme_id|vid)=(\d+)"),
    )
    _SEC_UID_PATTERNS = (
        re.compile(r"/user/([^/?#]+)"),
        re.compile(r"[?&](?:sec_uid|sec_user_id)=([^&#]+)"),
        re.compile(r'"secUid"\s*:\s*"([^"]+)"'),
        re.compile(r'"sec_uid"\s*:\s*"([^"]+)"'),
        re.compile(r'"sec_user_id"\s*:\s*"([^"]+)"'),
    )

    def __init__(self, signer: DouyinDetailSigner | None = None, parser_settings: dict[str, Any] | None = None):
        self.parser_settings = parser_settings or {}
        self.signer = signer or create_douyin_signer(self.parser_settings)

    async def parse(self, url: str) -> dict[str, Any]:
        aweme_id = await self.resolve_aweme_id(url)
        try:
            detail = await self.fetch_aweme_detail(aweme_id)
            aweme_detail = detail.get("aweme_detail")
            if not isinstance(aweme_detail, dict):
                raise ParserError("Douyin detail response did not contain aweme_detail")
            result = self.normalize_aweme_detail(aweme_id, aweme_detail)
            result["parser_source"] = "aweme_detail"
            return result
        except Exception as detail_error:
            try:
                aweme_detail = await self.fetch_share_aweme_detail(aweme_id)
            except Exception as share_error:
                raise ParserError(
                    f"Douyin detail failed ({type(detail_error).__name__}: {detail_error}); "
                    f"share fallback failed ({type(share_error).__name__}: {share_error})"
                ) from share_error
            result = self.normalize_aweme_detail(aweme_id, aweme_detail)
            result["parser_source"] = "share_page_fallback"
            result["parser_warning"] = (
                f"aweme_detail failed with {type(detail_error).__name__}; "
                "using lower-resolution share-page data"
            )
            return result

    async def resolve_aweme_id(self, url: str) -> str:
        direct = self.extract_aweme_id(url)
        if direct:
            return direct
        timeout = httpx.Timeout(12.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=self.request_headers())
            response.raise_for_status()
        resolved = self.extract_aweme_id(str(response.url))
        if not resolved:
            raise ParserError("Could not resolve Douyin aweme_id from URL")
        return resolved

    @classmethod
    def extract_aweme_id(cls, url: str) -> str | None:
        for pattern in cls._ID_PATTERNS:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None

    @classmethod
    def extract_sec_uid(cls, value: str) -> str | None:
        for pattern in cls._SEC_UID_PATTERNS:
            match = pattern.search(value)
            if match:
                return unquote(match.group(1)).strip()
        return None

    async def resolve_sec_uid(self, url: str) -> str:
        direct = self.extract_sec_uid(url)
        if direct and direct.lower() != "self":
            return direct
        timeout = httpx.Timeout(15.0, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=self.request_headers())
            response.raise_for_status()
        resolved = self.extract_sec_uid(str(response.url)) or self.extract_sec_uid(response.text)
        if not resolved:
            raise ParserError("Could not resolve Douyin sec_uid from author URL")
        return resolved

    def request_headers(self) -> dict[str, str]:
        user_agent = str(self.parser_settings.get("douyin_user_agent") or settings.douyin_user_agent)
        douyin_cookie = normalize_cookie_header(self.parser_settings.get("douyin_cookie") or settings.douyin_cookie)
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.douyin.com/",
            "User-Agent": user_agent,
        }
        if douyin_cookie:
            headers["Cookie"] = douyin_cookie
        return headers

    def mobile_request_headers(self) -> dict[str, str]:
        douyin_cookie = normalize_cookie_header(self.parser_settings.get("douyin_cookie") or settings.douyin_cookie)
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.douyin.com/",
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            ),
        }
        if douyin_cookie:
            headers["Cookie"] = douyin_cookie
        return headers

    @staticmethod
    def build_detail_params(aweme_id: str) -> dict[str, Any]:
        return {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "aweme_id": aweme_id,
            "pc_client_type": 1,
            "version_code": "290100",
            "version_name": "29.1.0",
            "cookie_enabled": "true",
            "screen_width": 1920,
            "screen_height": 1080,
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "130.0.0.0",
            "browser_online": "true",
            "engine_name": "Blink",
            "engine_version": "130.0.0.0",
            "os_name": "Windows",
            "os_version": "10",
            "cpu_core_num": 12,
            "device_memory": 8,
            "platform": "PC",
            "downlink": "10",
            "effective_type": "4g",
            "round_trip_time": "0",
            "msToken": "",
        }

    @staticmethod
    def build_author_post_params(sec_uid: str, max_cursor: int = 0, count: int = 18) -> dict[str, Any]:
        return {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "sec_user_id": sec_uid,
            "max_cursor": str(max_cursor),
            "locate_query": "false",
            "show_live_replay_strategy": "1",
            "need_time_list": "1",
            "time_list_query": "0",
            "whale_cut_token": "",
            "cut_version": "1",
            "count": str(max(1, min(30, int(count or 18)))),
            "publish_video_strategy_type": "2",
            "update_version_code": "170400",
            "pc_client_type": 1,
            "version_code": "290100",
            "version_name": "29.1.0",
            "cookie_enabled": "true",
            "screen_width": 1920,
            "screen_height": 1080,
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "130.0.0.0",
            "browser_online": "true",
            "engine_name": "Blink",
            "engine_version": "130.0.0.0",
            "os_name": "Windows",
            "os_version": "10",
            "cpu_core_num": 12,
            "device_memory": 8,
            "platform": "PC",
            "downlink": "10",
            "effective_type": "4g",
            "round_trip_time": "0",
            "msToken": "",
        }

    async def detail_url(self, aweme_id: str) -> str:
        params = self.build_detail_params(aweme_id)
        user_agent = str(self.parser_settings.get("douyin_user_agent") or settings.douyin_user_agent)
        signed = await self.signer.sign(params, user_agent)
        return f"{self.detail_endpoint}?{urlencode(signed)}"

    async def author_post_url(self, sec_uid: str, max_cursor: int = 0, count: int = 18) -> str:
        params = self.build_author_post_params(sec_uid, max_cursor=max_cursor, count=count)
        user_agent = str(self.parser_settings.get("douyin_user_agent") or settings.douyin_user_agent)
        signed = await self.signer.sign(params, user_agent)
        return f"{self.author_post_endpoint}?{urlencode(signed)}"

    async def fetch_aweme_detail(self, aweme_id: str) -> dict[str, Any]:
        timeout = httpx.Timeout(20.0, connect=8.0)
        detail_url = await self.detail_url(aweme_id)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(detail_url, headers=self.request_headers())
        if response.status_code >= 400:
            raise ParserError(
                f"Douyin detail returned HTTP {response.status_code}: {response.text[:240]}"
            )
        data = response.json()
        if data.get("status_code") not in (None, 0):
            raise ParserError(str(data.get("status_msg") or data))
        return data

    async def fetch_author_post_page(self, sec_uid: str, max_cursor: int = 0, count: int = 18) -> dict[str, Any]:
        timeout = httpx.Timeout(20.0, connect=8.0)
        url = await self.author_post_url(sec_uid, max_cursor=max_cursor, count=count)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=self.request_headers())
        if response.status_code >= 400:
            raise ParserError(
                f"Douyin author post returned HTTP {response.status_code}: {response.text[:240]}"
            )
        data = response.json()
        if data.get("status_code") not in (None, 0):
            raise ParserError(str(data.get("status_msg") or data))
        return data

    def author_items_from_page(self, page: dict[str, Any], sec_uid: str) -> list[dict[str, Any]]:
        raw_items = page.get("aweme_list") or page.get("data") or []
        if not isinstance(raw_items, list):
            raw_items = []
        items: list[dict[str, Any]] = []
        for raw_item in raw_items:
            aweme = raw_item.get("aweme_info") if isinstance(raw_item, dict) else None
            if not isinstance(aweme, dict):
                aweme = raw_item if isinstance(raw_item, dict) else {}
            aweme_id = str(aweme.get("aweme_id") or aweme.get("group_id") or "").strip()
            if not aweme_id:
                continue
            normalized = self.normalize_aweme_detail(aweme_id, aweme)
            normalized["parser_source"] = "author_post"
            normalized["author_sec_uid"] = sec_uid
            path = "note" if normalized.get("type") == "image" else "video"
            items.append(
                {
                    "aweme_id": aweme_id,
                    "url": f"https://www.douyin.com/{path}/{aweme_id}",
                    "type": normalized.get("type"),
                    "desc": normalized.get("desc"),
                    "author_name": author_name_from_payload(normalized),
                    "metadata": normalized,
                }
            )
        return items

    async def list_author_posts(
        self,
        url: str,
        max_pages: int = 30,
        max_items: int = 200,
        count: int = 18,
        delay_ms: int = 600,
    ) -> dict[str, Any]:
        sec_uid = await self.resolve_sec_uid(url)
        max_pages = max(1, min(100, int(max_pages or 30)))
        max_items = max(1, min(1000, int(max_items or 200)))
        count = max(1, min(30, int(count or 18)))
        delay_ms = max(0, min(5000, int(delay_ms or 0)))
        cursor = 0
        pages = 0
        has_more = True
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        while has_more and pages < max_pages and len(items) < max_items:
            page = await self.fetch_author_post_page(sec_uid, max_cursor=cursor, count=count)
            pages += 1
            for item in self.author_items_from_page(page, sec_uid):
                aweme_id = str(item.get("aweme_id") or "").strip()
                if not aweme_id or aweme_id in seen:
                    continue
                seen.add(aweme_id)
                items.append(item)
                if len(items) >= max_items:
                    break
            has_more = bool(page.get("has_more"))
            try:
                cursor = int(page.get("max_cursor") or page.get("cursor") or 0)
            except (TypeError, ValueError):
                cursor = 0
            if has_more and pages < max_pages and len(items) < max_items and delay_ms:
                await asyncio.sleep(delay_ms / 1000)
        return {
            "sec_uid": sec_uid,
            "items": items,
            "count": len(items),
            "pages": pages,
            "has_more": has_more and len(items) >= max_items or (has_more and pages >= max_pages),
            "next_cursor": cursor,
            "limit_reached": bool(has_more and (len(items) >= max_items or pages >= max_pages)),
        }

    async def fetch_share_aweme_detail(self, aweme_id: str) -> dict[str, Any]:
        timeout = httpx.Timeout(20.0, connect=8.0)
        url = self.share_endpoint.format(aweme_id=aweme_id)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=self.mobile_request_headers())
        if response.status_code >= 400:
            raise ParserError(f"Douyin share page returned HTTP {response.status_code}: {response.text[:240]}")
        return self.extract_share_aweme_detail(response.text)

    @classmethod
    def extract_share_aweme_detail(cls, html: str) -> dict[str, Any]:
        match = cls._ROUTER_DATA_RE.search(html)
        if not match:
            raise ParserError("Douyin share page did not contain router data")
        raw = match.group(1).strip().rstrip(";")
        try:
            router_data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ParserError("Douyin share page router data was not valid JSON") from exc
        loader_data = router_data.get("loaderData")
        if not isinstance(loader_data, dict):
            raise ParserError("Douyin share page router data did not contain loaderData")
        for value in loader_data.values():
            if not isinstance(value, dict):
                continue
            video_info = value.get("videoInfoRes")
            if not isinstance(video_info, dict):
                continue
            item_list = video_info.get("item_list")
            if isinstance(item_list, list) and item_list and isinstance(item_list[0], dict):
                return item_list[0]
        raise ParserError("Douyin share page router data did not contain a video item")

    @staticmethod
    def normalize_aweme_detail(aweme_id: str, data: dict[str, Any]) -> dict[str, Any]:
        aweme_type = data.get("aweme_type")
        url_type = "image" if aweme_type in {2, 68} else "video"
        result = {
            "type": url_type,
            "platform": "douyin",
            "video_id": aweme_id,
            "desc": data.get("desc"),
            "create_time": data.get("create_time"),
            "author": data.get("author"),
            "music": data.get("music"),
            "statistics": data.get("statistics"),
            "cover_data": {
                "cover": (data.get("video") or {}).get("cover"),
                "origin_cover": (data.get("video") or {}).get("origin_cover"),
                "dynamic_cover": (data.get("video") or {}).get("dynamic_cover"),
            },
            "hashtags": data.get("text_extra"),
        }
        if url_type == "video":
            video = data.get("video") or {}
            play_addr = video.get("play_addr") or {}
            uri = play_addr.get("uri")
            wm_video_url_hq = (play_addr.get("url_list") or [None])[0]
            bit_rate_candidates = get_bit_rate_video_candidates(video)
            best_url = get_best_bit_rate_video_url(video)
            fallback_url = wm_video_url_hq.replace("playwm", "play") if wm_video_url_hq else None
            result["video_data"] = {
                "wm_video_url": f"https://aweme.snssdk.com/aweme/v1/playwm/?video_id={uri}&radio=1080p&line=0"
                if uri else wm_video_url_hq,
                "wm_video_url_HQ": wm_video_url_hq,
                "nwm_video_url": f"https://aweme.snssdk.com/aweme/v1/play/?video_id={uri}&ratio=1080p&line=0"
                if uri else fallback_url,
                "nwm_video_url_HQ": best_url or fallback_url,
                "bit_rate_candidates": bit_rate_candidates,
            }
        elif data.get("images"):
            result["image_data"] = {
                "no_watermark_image_list": [
                    (item.get("url_list") or [None])[0] for item in data.get("images") or []
                ],
                "watermark_image_list": [
                    (item.get("download_url_list") or [None])[0] for item in data.get("images") or []
                ],
            }
        return result

    async def health(self) -> dict[str, Any]:
        cookie_configured = bool(self.parser_settings.get("douyin_cookie") or settings.douyin_cookie)
        return {
            **self.info(),
            "ok": cookie_configured,
            "stage": "detail_request_signed",
            "cookie_configured": cookie_configured,
            "warning": None,
        }

    def info(self) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "detail_endpoint": self.detail_endpoint,
            "signer": self.signer.name,
            "signer_configured": True,
            "cookie_configured": bool(self.parser_settings.get("douyin_cookie") or settings.douyin_cookie),
            "dependency_mode": "native_local_signer",
            "legacy_dependency": False,
            "external_dependencies": [],
            "capabilities": ["resolve_aweme_id", "fetch_aweme_detail", "share_page_fallback", "normalize_aweme_detail"],
        }


class NativeDouyinShareParserAdapter(NativeDouyinParserAdapter):
    name = "native_douyin_share"

    def __init__(self, parser_settings: dict[str, Any] | None = None):
        super().__init__(signer=NoopDouyinDetailSigner(), parser_settings=parser_settings)

    async def parse(self, url: str) -> dict[str, Any]:
        aweme_id = await self.resolve_aweme_id(url)
        aweme_detail = await self.fetch_share_aweme_detail(aweme_id)
        result = self.normalize_aweme_detail(aweme_id, aweme_detail)
        result["parser_source"] = "share_page"
        return result

    async def health(self) -> dict[str, Any]:
        return {
            **self.info(),
            "ok": True,
            "stage": "share_page_router_data",
            "warning": "Share-page parsing does not use A-Bogus, but may only expose lower-resolution video URLs",
        }

    def info(self) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "share_endpoint": self.share_endpoint,
            "signer": self.signer.name,
            "signer_configured": False,
            "cookie_configured": bool(self.parser_settings.get("douyin_cookie") or settings.douyin_cookie),
            "dependency_mode": "native",
            "legacy_dependency": False,
            "external_dependencies": [],
            "capabilities": ["resolve_aweme_id", "fetch_share_page", "normalize_aweme_detail"],
        }


def first_tiktok_url(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            url = first_tiktok_url(item)
            if url:
                return url
    if isinstance(value, dict):
        for key in ("UrlList", "url_list", "urls"):
            url = first_tiktok_url(value.get(key))
            if url:
                return url
    if isinstance(value, str):
        url = value.strip().split()[0] if value.strip() else ""
        if url.startswith("//"):
            return f"https:{url}"
        return url
    return ""


def all_tiktok_urls(value: Any) -> list[str]:
    urls: list[str] = []
    raw = value
    if isinstance(value, dict):
        raw = value.get("UrlList") or value.get("url_list") or value.get("urls") or []
    if isinstance(raw, str):
        raw = [raw]
    if isinstance(raw, list):
        for item in raw:
            url = first_tiktok_url(item)
            if url and url not in urls:
                urls.append(url)
    return urls


class NativeTikTokParserAdapter:
    name = "native_tiktok"
    _ID_PATTERNS = (
        re.compile(r"/video/(\d+)"),
        re.compile(r"[?&](?:item_id|video_id)=(\d+)"),
    )
    _JSON_SCRIPT_RE = re.compile(
        r'<script[^>]+id=["\'](?P<id>SIGI_STATE|__UNIVERSAL_DATA_FOR_REHYDRATION__)["\'][^>]*>(?P<body>.*?)</script>',
        re.S,
    )

    def __init__(self, parser_settings: dict[str, Any] | None = None):
        self.parser_settings = parser_settings or {}

    async def parse(self, url: str) -> dict[str, Any]:
        page_url = url
        page_html = ""
        item: dict[str, Any] | None = None
        video_id = self.extract_video_id(url)
        last_error: Exception | None = None
        max_attempts = 6
        for attempt in range(max_attempts):
            try:
                page_url, page_html = await self.fetch_video_page(url, attempt=attempt)
                video_id = self.extract_video_id(page_url) or video_id
                item = self.extract_item_from_html(page_html, video_id)
                break
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.35 * (attempt + 1))
                    continue
                raise ParserError(f"TikTok parse failed after retries: {exc}") from exc
        if not item:
            raise ParserError(f"TikTok parse failed: {last_error}")
        item_id = str(item.get("id") or video_id or "").strip()
        if not item_id:
            raise ParserError("TikTok page did not contain a video id")
        result = self.normalize_item(item_id, item)
        result["parser_source"] = "web_page_json"
        result["source_url"] = page_url
        return result

    async def fetch_video_page(self, url: str, attempt: int = 0) -> tuple[str, str]:
        timeout = httpx.Timeout(20.0, connect=8.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=self.request_headers(url, attempt=attempt))
            canonical_url = self.canonical_video_url(str(response.url))
            if canonical_url and canonical_url != str(response.url):
                response = await client.get(canonical_url, headers=self.request_headers(canonical_url, attempt=attempt))
        if response.status_code >= 400:
            raise ParserError(f"TikTok page returned HTTP {response.status_code}: {response.text[:240]}")
        return str(response.url), response.text

    @classmethod
    def extract_video_id(cls, url: str) -> str | None:
        for pattern in cls._ID_PATTERNS:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None

    @classmethod
    def canonical_video_url(cls, url: str) -> str:
        if not cls.extract_video_id(url):
            return url
        parts = urlsplit(url)
        if not parts.query and not parts.fragment:
            return url
        return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))

    def request_headers(self, url: str | None = None, attempt: int = 0) -> dict[str, str]:
        desktop_user_agent = str(self.parser_settings.get("tiktok_user_agent") or settings.tiktok_user_agent)
        mobile_user_agent = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
            "Mobile/15E148 Safari/604.1"
        )
        user_agent = mobile_user_agent if attempt % 2 else desktop_user_agent
        tiktok_cookie = normalize_cookie_header(self.parser_settings.get("tiktok_cookie") or settings.tiktok_cookie)
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Referer": "https://www.tiktok.com/",
            "User-Agent": user_agent,
        }
        if url:
            headers["Referer"] = url
        if tiktok_cookie:
            headers["Cookie"] = tiktok_cookie
        return headers

    @classmethod
    def extract_item_from_html(cls, page_html: str, video_id: str | None = None) -> dict[str, Any]:
        errors: list[str] = []
        for match in cls._JSON_SCRIPT_RE.finditer(page_html):
            raw = html.unescape(match.group("body") or "").strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"{match.group('id')}: {exc}")
                continue
            item = cls.find_item_struct(data, video_id)
            if item:
                return item
        if errors:
            raise ParserError("TikTok page JSON could not be parsed: " + "; ".join(errors[:2]))
        raise ParserError("TikTok page did not contain supported video JSON")

    @classmethod
    def find_item_struct(cls, data: Any, video_id: str | None = None) -> dict[str, Any] | None:
        stack = [data]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                item_module = current.get("ItemModule")
                if isinstance(item_module, dict) and video_id:
                    item = item_module.get(video_id)
                    if cls.looks_like_item(item, video_id):
                        return item
                item_info = current.get("itemInfo")
                if isinstance(item_info, dict):
                    item_struct = item_info.get("itemStruct")
                    if cls.looks_like_item(item_struct, video_id):
                        return item_struct
                item_struct = current.get("itemStruct")
                if cls.looks_like_item(item_struct, video_id):
                    return item_struct
                if cls.looks_like_item(current, video_id):
                    return current
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)
        return None

    @staticmethod
    def looks_like_item(value: Any, video_id: str | None = None) -> bool:
        if not isinstance(value, dict):
            return False
        item_id = str(value.get("id") or value.get("item_id") or "").strip()
        if video_id and item_id and item_id != str(video_id):
            return False
        return isinstance(value.get("video"), dict) and (bool(item_id) or bool(video_id))

    @staticmethod
    def normalize_author(author: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(author or {})
        normalized["uid"] = str(author.get("id") or author.get("uid") or "").strip()
        normalized["unique_id"] = str(author.get("uniqueId") or author.get("unique_id") or "").strip()
        normalized["nickname"] = str(author.get("nickname") or normalized.get("unique_id") or "").strip()
        for source_key, target_key in (
            ("avatarThumb", "avatar_thumb"),
            ("avatarMedium", "avatar_medium"),
            ("avatarLarger", "avatar_larger"),
        ):
            url = first_tiktok_url(author.get(source_key) or author.get(target_key))
            if url:
                normalized[target_key] = {"url_list": [url]}
        return normalized

    @classmethod
    def normalize_bitrate_candidates(cls, video: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for index, item in enumerate(video.get("bitrateInfo") or video.get("bit_rate") or []):
            if not isinstance(item, dict):
                continue
            play_addr = item.get("PlayAddr") or item.get("play_addr") or {}
            urls = all_tiktok_urls(play_addr)
            if not urls:
                continue
            codec = str(item.get("CodecType") or item.get("codec_type") or item.get("Codec") or "").lower()
            width = int(play_addr.get("Width") or play_addr.get("width") or video.get("width") or 0)
            height = int(play_addr.get("Height") or play_addr.get("height") or video.get("height") or 0)
            candidates.append(
                {
                    "url": urls[0],
                    "back_urls": urls[1:],
                    "width": width,
                    "height": height,
                    "fps": int(item.get("FPS") or item.get("fps") or 0),
                    "bit_rate": int(item.get("Bitrate") or item.get("bit_rate") or 0),
                    "data_size": int(play_addr.get("DataSize") or play_addr.get("data_size") or 0),
                    "format": item.get("Format") or item.get("format"),
                    "gear_name": item.get("GearName") or item.get("gear_name") or f"tiktok_{index}",
                    "quality_type": item.get("QualityType") or item.get("quality_type"),
                    "is_h265": codec in {"h265", "hevc", "hvc1", "bytevc1"},
                }
            )
        return sorted(
            candidates,
            key=lambda item: (
                max(int(item.get("width") or 0), int(item.get("height") or 0)),
                min(int(item.get("width") or 0), int(item.get("height") or 0)),
                int(bool(item.get("is_h265"))),
                int(item.get("data_size") or 0),
                int(item.get("bit_rate") or 0),
            ),
            reverse=True,
        )

    @classmethod
    def normalize_item(cls, item_id: str, item: dict[str, Any]) -> dict[str, Any]:
        video = item.get("video") or {}
        author = cls.normalize_author(item.get("author") if isinstance(item.get("author"), dict) else {})
        play_addr = first_tiktok_url(video.get("playAddr") or video.get("play_addr"))
        download_addr = first_tiktok_url(video.get("downloadAddr") or video.get("download_addr"))
        cover = first_tiktok_url(video.get("cover"))
        origin_cover = first_tiktok_url(video.get("originCover") or video.get("origin_cover"))
        dynamic_cover = first_tiktok_url(video.get("dynamicCover") or video.get("dynamic_cover"))
        bitrate_candidates = cls.normalize_bitrate_candidates(video)
        best_url = bitrate_candidates[0]["url"] if bitrate_candidates else play_addr
        result = {
            "type": "video",
            "platform": "tiktok",
            "video_id": item_id,
            "desc": item.get("desc") or item.get("description") or "",
            "create_time": item.get("createTime") or item.get("create_time"),
            "author": author,
            "music": item.get("music"),
            "statistics": item.get("stats") or item.get("statistics"),
            "hashtags": item.get("textExtra") or item.get("text_extra"),
            "cover_url": origin_cover or cover or dynamic_cover,
            "cover_data": {
                "cover": {"url_list": [cover]} if cover else {},
                "origin_cover": {"url_list": [origin_cover]} if origin_cover else {},
                "dynamic_cover": {"url_list": [dynamic_cover]} if dynamic_cover else {},
            },
            "video_data": {
                "wm_video_url": download_addr,
                "wm_video_url_HQ": download_addr,
                "nwm_video_url": play_addr,
                "nwm_video_url_HQ": best_url,
                "bit_rate_candidates": bitrate_candidates,
            },
        }
        if not best_url and not play_addr and not download_addr:
            raise ParserError("TikTok video item did not expose playable URLs")
        return result

    async def health(self) -> dict[str, Any]:
        return {
            **self.info(),
            "ok": True,
            "stage": "web_page_json",
            "cookie_configured": bool(self.parser_settings.get("tiktok_cookie") or settings.tiktok_cookie),
            "warning": None,
        }

    def info(self) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "detail_endpoint": "https://www.tiktok.com/@user/video/{id}",
            "cookie_configured": bool(self.parser_settings.get("tiktok_cookie") or settings.tiktok_cookie),
            "dependency_mode": "native_web_json",
            "legacy_dependency": False,
            "external_dependencies": [],
            "capabilities": ["fetch_video_page", "extract_web_json", "normalize_item"],
        }


def first_present(mapping: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = mapping.get(key)
        if value:
            return str(value)
    return ""


def author_name_from_payload(payload: dict[str, Any]) -> str:
    author = payload.get("author")
    if isinstance(author, dict):
        return first_present(author, ("nickname", "unique_id", "short_id", "uid", "sec_uid"))
    return str(author or "")


def runtime_parser_settings() -> dict[str, Any]:
    from . import db

    return db.get_parser_settings(include_secret=True)


def is_tiktok_url(url: str) -> bool:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    return host == "tiktok.com" or host.endswith(".tiktok.com")


def create_adapter(
    name: str | None = None,
    parser_settings: dict[str, Any] | None = None,
) -> ParserAdapter:
    parser_settings = parser_settings or runtime_parser_settings()
    adapter_name = name or parser_settings.get("parser_adapter") or settings.parser_adapter
    if adapter_name == "native_douyin":
        return NativeDouyinParserAdapter(parser_settings=parser_settings)
    if adapter_name == "native_douyin_share":
        return NativeDouyinShareParserAdapter(parser_settings=parser_settings)
    if adapter_name == "native_tiktok":
        return NativeTikTokParserAdapter(parser_settings=parser_settings)
    raise ParserError(f"Unknown parser adapter: {adapter_name}")


class ParserClient:
    def __init__(
        self,
        adapter: ParserAdapter | None = None,
        parser_settings: dict[str, Any] | None = None,
    ):
        self.parser_settings = parser_settings or runtime_parser_settings()
        self.explicit_adapter = adapter is not None
        if adapter:
            self.adapter = adapter
        else:
            self.adapter = create_adapter(parser_settings=self.parser_settings)

    async def parse(self, url: str) -> dict[str, Any]:
        if not self.explicit_adapter:
            if is_tiktok_url(url):
                routed_adapter = NativeTikTokParserAdapter(parser_settings=self.parser_settings)
                result = await routed_adapter.parse(url)
                result["_clipnest_adapter_name"] = routed_adapter.name
                return result
            if self.adapter.name == "native_tiktok":
                routed_adapter = NativeDouyinParserAdapter(parser_settings=self.parser_settings)
                result = await routed_adapter.parse(url)
                result["_clipnest_adapter_name"] = routed_adapter.name
                return result
        result = await self.adapter.parse(url)
        result["_clipnest_adapter_name"] = self.adapter.name
        return result

    async def health(self) -> dict[str, Any]:
        return await self.adapter.health()

    def info(self) -> dict[str, Any]:
        return self.adapter.info()
