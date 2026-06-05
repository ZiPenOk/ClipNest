// ==UserScript==
// @name         ClipNest Douyin Remote Push
// @namespace    https://clipnest.local/userscripts
// @version      2026.06.02.1
// @description  Detect the current Douyin video/note and push it to ClipNest for remote download.
// @author       ClipNest
// @match        *://*.douyin.com/*
// @match        *://*.iesdouyin.com/*
// @exclude      *://creator.douyin.com/*
// @connect      *
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        GM_xmlhttpRequest
// @grant        unsafeWindow
// @run-at       document-idle
// ==/UserScript==

(function () {
  "use strict";

  const DEFAULT_BASE_URL = "http://10.10.10.200:8090";
  const DEFAULT_QUALITY = "best";
  const STORAGE_KEYS = {
    baseUrl: "clipnest.baseUrl",
    token: "clipnest.token",
    quality: "clipnest.quality",
  };
  const PLAYER_BUTTON_CLASS = "clipnest-player-push-btn";
  const win = typeof unsafeWindow !== "undefined" ? unsafeWindow : window;
  const state = {
    current: null,
    busy: false,
    lastHref: location.href,
    observedVideos: new WeakSet(),
  };

  function gmGet(key, fallback) {
    try {
      const value = typeof GM_getValue === "function" ? GM_getValue(key) : undefined;
      return value == null || value === "" ? fallback : value;
    } catch {
      return fallback;
    }
  }

  function gmSet(key, value) {
    if (typeof GM_setValue === "function") {
      GM_setValue(key, value);
    }
  }

  function getBaseUrl() {
    return String(gmGet(STORAGE_KEYS.baseUrl, DEFAULT_BASE_URL)).replace(/\/+$/, "");
  }

  function getToken() {
    return String(gmGet(STORAGE_KEYS.token, "")).trim();
  }

  function getQuality() {
    return String(gmGet(STORAGE_KEYS.quality, DEFAULT_QUALITY)).trim() || DEFAULT_QUALITY;
  }

  function cleanUrl(value) {
    if (!value || typeof value !== "string") {
      return "";
    }
    try {
      const url = new URL(value, location.href);
      url.hash = "";
      if (!url.hostname.includes("douyin.com") && !url.hostname.includes("iesdouyin.com")) {
        return "";
      }
      return url.toString();
    } catch {
      return "";
    }
  }

  function canonicalDouyinUrl(id, type) {
    if (!id) {
      return "";
    }
    const kind = type === "note" ? "note" : "video";
    return `https://www.douyin.com/${kind}/${id}`;
  }

  function normalizeItem(item) {
    if (!item || !item.url) {
      return null;
    }
    return {
      url: item.url,
      id: String(item.id || ""),
      type: item.type || "video",
      source: item.source || "unknown",
      desc: item.desc || "",
      author: item.author || "",
      cover_url: item.cover_url || "",
    };
  }

  function detectFromUrl(href, options = {}) {
    const includeQuery = options.includeQuery !== false;
    let url;
    try {
      url = new URL(href || location.href);
    } catch {
      return null;
    }

    const path = url.pathname;
    let match = path.match(/^\/(video|note)\/(\d+)/);
    if (match) {
      return normalizeItem({
        id: match[2],
        type: match[1] === "note" ? "note" : "video",
        url: canonicalDouyinUrl(match[2], match[1]),
        source: "url-path",
      });
    }

    match = path.match(/^\/share\/(video|note)\/(\d+)/);
    if (match) {
      return normalizeItem({
        id: match[2],
        type: match[1] === "note" ? "note" : "video",
        url: canonicalDouyinUrl(match[2], match[1]),
        source: "share-path",
      });
    }

    match = path.match(/^\/shipin\/(\d+)/);
    if (match) {
      return normalizeItem({
        id: match[1],
        type: "video",
        url: canonicalDouyinUrl(match[1], "video"),
        source: "mobile-path",
      });
    }

    if (includeQuery) {
      const queryId =
        url.searchParams.get("modal_id") ||
        url.searchParams.get("aweme_id") ||
        url.searchParams.get("awemeId") ||
        url.searchParams.get("item_id");
      if (queryId && /^\d{8,}$/.test(queryId)) {
        return normalizeItem({
          id: queryId,
          type: "video",
          url: canonicalDouyinUrl(queryId, "video"),
          source: "query-id",
        });
      }
    }

    return null;
  }

  function isPlainSearchableObject(value) {
    if (!value || typeof value !== "object") {
      return false;
    }
    if (value instanceof Node || value === window || value === document || value === win) {
      return false;
    }
    return true;
  }

  function getObjectText(value, keys) {
    for (const key of keys) {
      const found = value && value[key];
      if (typeof found === "string" && found.trim()) {
        return found.trim();
      }
    }
    return "";
  }

  function normalizeImageUrl(value) {
    if (typeof value !== "string" || !value.trim()) {
      return "";
    }
    const raw = value.trim().replace(/&amp;/g, "&");
    try {
      const url = new URL(raw, location.href);
      if (!url.hostname.includes("douyinpic.com")) {
        return "";
      }
      return url.toString();
    } catch {
      return "";
    }
  }

  function coverUrlScore(url) {
    let score = 0;
    if (!url) return score;
    if (url.includes("cropcenter")) score += 100;
    if (url.includes("PackSourceEnum_PUBLISH")) score += 35;
    if (url.includes("dynamic_cover") || url.includes("/obj/tos-cn-i-")) score += 60;
    if (url.includes("origin_cover")) score += 35;
    if (url.includes("pcweb_cover")) score += 20;
    if (url.includes("image-cut-tos-priv")) score -= 10;
    return score;
  }

  function betterCoverUrl(left, right) {
    if (!left) return right || "";
    if (!right) return left || "";
    return coverUrlScore(right) > coverUrlScore(left) ? right : left;
  }

  function coverUrlFromCssValue(value) {
    if (typeof value !== "string" || !value.includes("url(")) {
      return "";
    }
    let best = "";
    const matches = value.matchAll(/url\((['"]?)(.*?)\1\)/g);
    for (const match of matches) {
      best = betterCoverUrl(best, normalizeImageUrl(match[2]));
    }
    return best;
  }

  function coverUrlFromValue(value, depth = 0, seen = new WeakSet(), budget = { count: 0 }) {
    const direct = normalizeImageUrl(value);
    if (direct) {
      return direct;
    }
    if (!isPlainSearchableObject(value) || depth > 4 || budget.count > 320) {
      return "";
    }
    if (seen.has(value)) {
      return "";
    }
    seen.add(value);
    budget.count += 1;

    let best = "";
    const priorityKeys = [
      "pc_card_cover",
      "pcCardCover",
      "coverUrl",
      "cover_url",
      "dynamic_cover",
      "dynamicCover",
      "origin_cover",
      "originCover",
      "cover",
      "imagePostCover",
      "url_list",
      "urlList",
      "src",
    ];
    for (const key of priorityKeys) {
      if (Object.prototype.hasOwnProperty.call(value, key)) {
        best = betterCoverUrl(best, coverUrlFromValue(value[key], depth + 1, seen, budget));
      }
    }
    const keys = Object.keys(value).slice(0, 50);
    for (const key of keys) {
      best = betterCoverUrl(best, coverUrlFromValue(value[key], depth + 1, seen, budget));
    }
    return best;
  }

  function awemeIdFromObject(value) {
    return getObjectText(value, ["aweme_id", "awemeId", "group_id", "groupId", "item_id", "itemId"]);
  }

  function looksLikeAweme(value) {
    if (!isPlainSearchableObject(value)) {
      return false;
    }
    if (awemeIdFromObject(value)) {
      return true;
    }
    const shareInfo = value.shareInfo || value.share_info;
    return Boolean(shareInfo && (shareInfo.shareUrl || shareInfo.share_url));
  }

  function itemFromAweme(value, source) {
    if (!looksLikeAweme(value)) {
      return null;
    }
    const id = awemeIdFromObject(value);
    const isNote =
      value.aweme_type === 68 ||
      value.awemeType === 68 ||
      (Array.isArray(value.images) && value.images.length > 0) ||
      (Array.isArray(value.imagePostCover) && value.imagePostCover.length > 0);
    const shareInfo = value.shareInfo || value.share_info || {};
    const shareUrl = cleanUrl(shareInfo.shareUrl || shareInfo.share_url || "");
    const url = id ? canonicalDouyinUrl(id, isNote ? "note" : "video") : shareUrl;
    return normalizeItem({
      id,
      type: isNote ? "note" : "video",
      url,
      source,
      desc: getObjectText(value, ["desc", "caption", "title"]),
      author: getObjectText(value.author || value.authorInfo || value.author_info || {}, [
        "nickname",
        "name",
        "unique_id",
        "uniqueId",
      ]),
      cover_url: coverUrlFromValue(value),
    });
  }

  function findAwemeObject(value, depth = 0, seen = new WeakSet(), budget = { count: 0 }) {
    if (!isPlainSearchableObject(value) || depth > 5 || budget.count > 600) {
      return null;
    }
    if (seen.has(value)) {
      return null;
    }
    seen.add(value);
    budget.count += 1;

    if (looksLikeAweme(value)) {
      return value;
    }

    const directKeys = ["awemeInfo", "aweme_info", "itemData", "item_data", "video", "data"];
    for (const key of directKeys) {
      const child = value[key];
      if (looksLikeAweme(child)) {
        return child;
      }
    }

    const keys = Object.keys(value).slice(0, 80);
    for (const key of keys) {
      const child = value[key];
      if (!isPlainSearchableObject(child)) {
        continue;
      }
      const found = findAwemeObject(child, depth + 1, seen, budget);
      if (found) {
        return found;
      }
    }

    return null;
  }

  function getReactFiber(element) {
    let node = element;
    while (node && node !== document) {
      for (const key in node) {
        if (
          key.startsWith("__reactFiber$") ||
          key.startsWith("__reactInternalInstance$") ||
          key.startsWith("__reactProps$")
        ) {
          return node[key];
        }
      }
      node = node.parentElement;
    }
    return null;
  }

  function findAwemeFromFiber(fiber) {
    const stack = [fiber];
    const seen = new Set();
    while (stack.length && seen.size < 1500) {
      const node = stack.pop();
      if (!node || seen.has(node)) {
        continue;
      }
      seen.add(node);

      const aweme =
        findAwemeObject(node.memoizedProps) ||
        findAwemeObject(node.pendingProps) ||
        findAwemeObject(node.memoizedState);
      if (aweme) {
        return aweme;
      }

      if (node.child) stack.push(node.child);
      if (node.sibling) stack.push(node.sibling);
      if (node.return) stack.push(node.return);
    }
    return null;
  }

  function isVisible(element) {
    if (!element || !(element instanceof Element)) {
      return false;
    }
    const rect = element.getBoundingClientRect();
    return rect.width > 30 && rect.height > 30 && rect.bottom > 0 && rect.right > 0 && rect.top < innerHeight;
  }

  function uniqueElements(elements) {
    const seen = new Set();
    const result = [];
    for (const element of elements) {
      if (!element || seen.has(element)) {
        continue;
      }
      seen.add(element);
      result.push(element);
    }
    return result;
  }

  function candidateElements() {
    const centerElements = document.elementsFromPoint(Math.round(innerWidth / 2), Math.round(innerHeight / 2));
    const playingVideos = Array.from(document.querySelectorAll("video"))
      .filter((video) => isVisible(video))
      .sort((a, b) => {
        const aScore = (!a.paused ? 100 : 0) + a.getBoundingClientRect().width * a.getBoundingClientRect().height;
        const bScore = (!b.paused ? 100 : 0) + b.getBoundingClientRect().width * b.getBoundingClientRect().height;
        return bScore - aScore;
      });
    const knownContainers = Array.from(
      document.querySelectorAll(
        [
          ".basePlayerContainer",
          "[data-e2e='video-share-container']",
          "[data-e2e='feed-video']",
          "[data-e2e='note-detail']",
          "[data-e2e='search-card']",
        ].join(",")
      )
    ).filter(isVisible);

    return uniqueElements([...playingVideos, ...centerElements, ...knownContainers]);
  }

  function detectCoverFromDom(rootElement) {
    const roots = uniqueElements([
      rootElement,
      rootElement && rootElement.closest && rootElement.closest(".basePlayerContainer"),
      rootElement && rootElement.closest && rootElement.closest("[data-e2e='feed-video']"),
      ...candidateElements(),
    ]).filter(Boolean);
    let best = "";
    for (const root of roots) {
      const images = [];
      if (root instanceof HTMLImageElement) {
        images.push(root);
      }
      if (root.querySelectorAll) {
        images.push(...root.querySelectorAll("img"));
      }
      for (const image of images) {
        if (!isVisible(image)) {
          continue;
        }
        best = betterCoverUrl(best, normalizeImageUrl(image.currentSrc || image.src || image.getAttribute("src")));
      }
      const nodes = root.querySelectorAll ? [root, ...Array.from(root.querySelectorAll("*")).slice(0, 140)] : [root];
      for (const node of nodes) {
        if (!isVisible(node)) {
          continue;
        }
        best = betterCoverUrl(best, coverUrlFromCssValue(node.style && node.style.backgroundImage));
        try {
          best = betterCoverUrl(best, coverUrlFromCssValue(getComputedStyle(node).backgroundImage));
        } catch {
          // Ignore detached nodes.
        }
      }
    }
    return best;
  }

  function detectFromReact(rootElement) {
    const elements = rootElement ? [rootElement] : candidateElements();
    for (const element of elements) {
      const fiber = getReactFiber(element);
      if (!fiber) {
        continue;
      }
      const aweme = findAwemeFromFiber(fiber);
      const item = itemFromAweme(aweme, "react-fiber");
      if (item) {
        return item;
      }
    }
    return null;
  }

  function detectFromRouterData() {
    const scripts = Array.from(document.scripts || []).slice(-25);
    for (const script of scripts) {
      const text = script.textContent || "";
      if (!text.includes("aweme") && !text.includes("awemeId")) {
        continue;
      }
      const idMatch = text.match(/"aweme_id"\s*:\s*"(\d{8,})"/) || text.match(/"awemeId"\s*:\s*"(\d{8,})"/);
      if (!idMatch) {
        continue;
      }
      const isNote = /"aweme_type"\s*:\s*68/.test(text) || /"awemeType"\s*:\s*68/.test(text);
      return normalizeItem({
        id: idMatch[1],
        type: isNote ? "note" : "video",
        url: canonicalDouyinUrl(idMatch[1], isNote ? "note" : "video"),
        source: "router-data",
      });
    }
    return null;
  }

  function detectCurrentItem(rootElement) {
    const item = (
      detectFromUrl(location.href, { includeQuery: false }) ||
      detectFromReact(rootElement) ||
      detectFromUrl(location.href, { includeQuery: true }) ||
      detectFromRouterData()
    );
    if (item && !item.cover_url) {
      item.cover_url = detectCoverFromDom(rootElement);
    }
    return item;
  }

  function requestJson(url, payload) {
    return new Promise((resolve, reject) => {
      if (typeof GM_xmlhttpRequest !== "function") {
        reject(new Error("GM_xmlhttpRequest is not available"));
        return;
      }
      GM_xmlhttpRequest({
        method: "POST",
        url,
        headers: {
          "Content-Type": "application/json",
          "X-Api-Token": getToken(),
        },
        data: JSON.stringify(payload),
        timeout: 20000,
        onload(response) {
          const ok = response.status >= 200 && response.status < 300;
          let body = null;
          try {
            body = response.responseText ? JSON.parse(response.responseText) : null;
          } catch {
            body = response.responseText;
          }
          if (ok) {
            resolve({ status: response.status, body });
          } else {
            const message = body && body.detail ? body.detail : response.responseText || response.statusText;
            reject(new Error(`HTTP ${response.status}: ${message}`));
          }
        },
        onerror() {
          reject(new Error("network error"));
        },
        ontimeout() {
          reject(new Error("request timeout"));
        },
      });
    });
  }

  function fallbackNavigate(item, dryRun) {
    const params = new URLSearchParams({
      token: getToken(),
      url: item.url,
    });
    if (dryRun) {
      params.set("dry_run", "true");
    }
    if (item.cover_url) {
      params.set("cover_url", item.cover_url);
    }
    window.open(`${getBaseUrl()}/api/push?${params.toString()}`, "_blank", "noopener,noreferrer");
  }

  async function pushCurrent(dryRun, rootElement) {
    if (state.busy) {
      return;
    }
    const item = detectCurrentItem(rootElement);
    if (!item) {
      toast("没有检测到当前作品", "error");
      updatePlayerButtons();
      return;
    }
    if (!getToken()) {
      toast("请先设置 ClipNest Token", "error");
      openSettings();
      return;
    }

    state.busy = true;
    updatePlayerButtons();
    try {
      const payload = {
        url: item.url,
        quality_preference: getQuality(),
        cover_url: item.cover_url || "",
        dry_run: Boolean(dryRun),
      };
      const result = await requestJson(`${getBaseUrl()}/api/push`, payload);
      const body = result.body || {};
      if (body.message) {
        toast(body.message, body.reused_count && !body.created_count ? "info" : "success");
      } else if (dryRun) {
        toast(`预检通过：${body.count || 1} 个链接`, "success");
      } else {
        toast(`已推送到 ClipNest：${item.id || item.type}`, "success");
      }
    } catch (error) {
      console.warn("[ClipNest] POST push failed, opening GET fallback", error);
      openFallbackDialog(error, item, dryRun);
    } finally {
      state.busy = false;
      updatePlayerButtons();
    }
  }

  function closeDialog() {
    const old = document.getElementById("clipnest-push-modal");
    if (old) {
      old.remove();
    }
  }

  function showFieldError(message) {
    const errorNode = document.getElementById("clipnest-dialog-error");
    if (errorNode) {
      errorNode.textContent = message;
      errorNode.hidden = !message;
    }
  }

  function openSettings() {
    closeDialog();
    addStyles();
    const modal = document.createElement("div");
    modal.id = "clipnest-push-modal";
    modal.innerHTML = `
      <div class="clipnest-modal-card" role="dialog" aria-modal="true" aria-label="ClipNest 设置">
        <div class="clipnest-modal-head">
          <div>
            <div class="clipnest-modal-title">ClipNest 远端推送</div>
            <div class="clipnest-modal-subtitle">保存一次后，抖音页面可直接推送到家里的下载队列。</div>
          </div>
          <button class="clipnest-icon-btn" type="button" data-clipnest-close aria-label="关闭">×</button>
        </div>
        <div class="clipnest-form">
          <label class="clipnest-field">
            <span>服务地址</span>
            <input id="clipnest-setting-base-url" type="url" autocomplete="off" placeholder="http://10.10.10.200:8090" />
          </label>
          <label class="clipnest-field">
            <span>API Token</span>
            <input id="clipnest-setting-token" type="password" autocomplete="off" placeholder="CLIPNEST_API_TOKEN" />
          </label>
          <label class="clipnest-field">
            <span>默认清晰度</span>
            <select id="clipnest-setting-quality">
              <option value="best">最高画质</option>
              <option value="2160">4K / 2160P</option>
              <option value="1440">2K / 1440P</option>
              <option value="1080">1080P</option>
              <option value="720">720P</option>
            </select>
          </label>
          <div id="clipnest-dialog-error" class="clipnest-error" hidden></div>
        </div>
        <div class="clipnest-modal-actions">
          <button type="button" class="clipnest-secondary" data-clipnest-close>取消</button>
          <button type="button" class="clipnest-primary" id="clipnest-save-settings">保存设置</button>
        </div>
      </div>
    `;
    document.documentElement.appendChild(modal);

    const baseUrlInput = document.getElementById("clipnest-setting-base-url");
    const tokenInput = document.getElementById("clipnest-setting-token");
    const qualityInput = document.getElementById("clipnest-setting-quality");
    baseUrlInput.value = getBaseUrl();
    tokenInput.value = getToken();
    qualityInput.value = getQuality();

    modal.addEventListener("click", (event) => {
      if (event.target === modal || event.target.closest("[data-clipnest-close]")) {
        closeDialog();
      }
    });
    document.getElementById("clipnest-save-settings").addEventListener("click", () => {
      const baseUrl = baseUrlInput.value.trim().replace(/\/+$/, "") || DEFAULT_BASE_URL;
      const token = tokenInput.value.trim();
      const quality = qualityInput.value.trim() || DEFAULT_QUALITY;
      try {
        const parsed = new URL(baseUrl);
        if (!["http:", "https:"].includes(parsed.protocol)) {
          throw new Error("服务地址必须是 http 或 https");
        }
      } catch {
        showFieldError("服务地址格式不对，例如 http://10.10.10.200:8090");
        return;
      }
      if (!token) {
        showFieldError("API Token 不能为空");
        return;
      }
      gmSet(STORAGE_KEYS.baseUrl, baseUrl);
      gmSet(STORAGE_KEYS.token, token);
      gmSet(STORAGE_KEYS.quality, quality);
      closeDialog();
      toast("ClipNest 设置已保存", "success");
      updatePlayerButtons();
    });
    window.setTimeout(() => baseUrlInput.focus(), 30);
  }

  function openFallbackDialog(error, item, dryRun) {
    closeDialog();
    addStyles();
    const modal = document.createElement("div");
    modal.id = "clipnest-push-modal";
    modal.innerHTML = `
      <div class="clipnest-modal-card clipnest-modal-card-small" role="dialog" aria-modal="true" aria-label="推送失败">
        <div class="clipnest-modal-head">
          <div>
            <div class="clipnest-modal-title">推送失败</div>
            <div class="clipnest-modal-subtitle">可以改用打开 ClipNest 推送页的方式继续。</div>
          </div>
          <button class="clipnest-icon-btn" type="button" data-clipnest-close aria-label="关闭">×</button>
        </div>
        <div class="clipnest-fail-box"></div>
        <div class="clipnest-modal-actions">
          <button type="button" class="clipnest-secondary" data-clipnest-close>取消</button>
          <button type="button" class="clipnest-primary" id="clipnest-open-fallback">打开推送页</button>
        </div>
      </div>
    `;
    document.documentElement.appendChild(modal);
    const box = modal.querySelector(".clipnest-fail-box");
    box.textContent = error && error.message ? error.message : "请求失败";
    modal.addEventListener("click", (event) => {
      if (event.target === modal || event.target.closest("[data-clipnest-close]")) {
        closeDialog();
      }
    });
    document.getElementById("clipnest-open-fallback").addEventListener("click", () => {
      closeDialog();
      fallbackNavigate(item, dryRun);
    });
  }

  function addStyles() {
    if (document.getElementById("clipnest-push-style")) {
      return;
    }
    const style = document.createElement("style");
    style.id = "clipnest-push-style";
    style.textContent = `
      .${PLAYER_BUTTON_CLASS} {
        position: relative;
        width: 44px;
        height: 44px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin: 0;
        border: 0;
        border-radius: 50%;
        color: #fff;
        background: rgba(0,0,0,.34);
        cursor: pointer;
        font: 12px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        user-select: none;
        transition: background .16s ease, transform .16s ease, opacity .16s ease;
      }
      .${PLAYER_BUTTON_CLASS}:hover {
        background: rgba(15,139,255,.88);
        transform: translateY(-1px);
      }
      .${PLAYER_BUTTON_CLASS}:disabled {
        cursor: not-allowed;
        opacity: .45;
        transform: none;
      }
      .${PLAYER_BUTTON_CLASS}.is-busy {
        background: rgba(15,139,255,.68);
      }
      .${PLAYER_BUTTON_CLASS} svg {
        width: 21px;
        height: 21px;
        display: block;
      }
      .${PLAYER_BUTTON_CLASS} .clipnest-spinner {
        width: 18px;
        height: 18px;
        border: 2px solid rgba(255,255,255,.32);
        border-top-color: #fff;
        border-radius: 50%;
        animation: clipnest-spin .8s linear infinite;
      }
      @keyframes clipnest-spin {
        to { transform: rotate(360deg); }
      }
      #clipnest-push-toast {
        position: fixed;
        right: 22px;
        bottom: 86px;
        z-index: 2147483647;
        box-sizing: border-box;
        width: max-content;
        max-width: min(300px, calc(100vw - 44px));
        padding: 10px 13px 10px 15px;
        border-left: 4px solid #39a1ff;
        border-top: 1px solid rgba(60,86,120,.14);
        border-right: 1px solid rgba(60,86,120,.14);
        border-bottom: 1px solid rgba(60,86,120,.14);
        border-radius: 8px;
        color: #10243d;
        background: rgba(232,244,255,.98);
        box-shadow: 0 14px 34px rgba(28,72,120,.24);
        font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        overflow-wrap: anywhere;
        animation: clipnest-toast-in .18s ease-out;
        backdrop-filter: blur(10px);
      }
      #clipnest-push-toast.success { border-left-color: #1fa971; background: rgba(225,249,238,.98); color: #0d3d2c; }
      #clipnest-push-toast.info { border-left-color: #d99218; background: rgba(255,241,209,.98); color: #4a3210; }
      #clipnest-push-toast.error { border-left-color: #d94d4d; background: rgba(255,229,229,.98); color: #501717; }
      @keyframes clipnest-toast-in {
        from { opacity: 0; transform: translateY(12px) scale(.98); }
        to { opacity: 1; transform: translateY(0) scale(1); }
      }
      #clipnest-push-modal {
        position: fixed;
        inset: 0;
        z-index: 2147483647;
        display: grid;
        place-items: center;
        padding: 22px;
        background: rgba(0,0,0,.46);
        color: #f7f8fb;
        font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        backdrop-filter: blur(8px);
      }
      #clipnest-push-modal .clipnest-modal-card {
        width: min(440px, calc(100vw - 32px));
        border: 1px solid rgba(255,255,255,.14);
        border-radius: 8px;
        background: #17191f;
        box-shadow: 0 24px 70px rgba(0,0,0,.42);
      }
      #clipnest-push-modal .clipnest-modal-card-small {
        width: min(390px, calc(100vw - 32px));
      }
      #clipnest-push-modal .clipnest-modal-head {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        padding: 18px 18px 10px;
      }
      #clipnest-push-modal .clipnest-modal-title {
        font-size: 17px;
        font-weight: 700;
      }
      #clipnest-push-modal .clipnest-modal-subtitle {
        margin-top: 4px;
        color: rgba(247,248,251,.66);
        font-size: 12px;
      }
      #clipnest-push-modal .clipnest-icon-btn {
        flex: 0 0 auto;
        width: 28px;
        height: 28px;
        border: 0;
        border-radius: 6px;
        color: rgba(247,248,251,.78);
        background: rgba(255,255,255,.08);
        cursor: pointer;
        font-size: 20px;
        line-height: 28px;
      }
      #clipnest-push-modal .clipnest-form {
        display: grid;
        gap: 12px;
        padding: 10px 18px 4px;
      }
      #clipnest-push-modal .clipnest-field {
        display: grid;
        gap: 6px;
      }
      #clipnest-push-modal .clipnest-field span {
        color: rgba(247,248,251,.78);
        font-size: 12px;
      }
      #clipnest-push-modal input,
      #clipnest-push-modal select {
        box-sizing: border-box;
        width: 100%;
        height: 36px;
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 6px;
        padding: 0 10px;
        outline: none;
        color: #fff;
        background: rgba(255,255,255,.07);
        font: inherit;
      }
      #clipnest-push-modal input:focus,
      #clipnest-push-modal select:focus {
        border-color: #39a1ff;
        box-shadow: 0 0 0 3px rgba(57,161,255,.18);
      }
      #clipnest-push-modal select option {
        color: #111;
      }
      #clipnest-push-modal .clipnest-error,
      #clipnest-push-modal .clipnest-fail-box {
        border-radius: 6px;
        padding: 9px 10px;
        color: #ffd9d9;
        background: rgba(220,60,60,.14);
        word-break: break-word;
      }
      #clipnest-push-modal .clipnest-fail-box {
        margin: 10px 18px 0;
      }
      #clipnest-push-modal .clipnest-modal-actions {
        display: flex;
        justify-content: flex-end;
        gap: 8px;
        padding: 16px 18px 18px;
      }
      #clipnest-push-modal .clipnest-primary,
      #clipnest-push-modal .clipnest-secondary {
        height: 34px;
        border: 0;
        border-radius: 6px;
        padding: 0 14px;
        color: #fff;
        cursor: pointer;
        font: inherit;
      }
      #clipnest-push-modal .clipnest-primary {
        background: #0f8bff;
      }
      #clipnest-push-modal .clipnest-secondary {
        background: rgba(255,255,255,.10);
      }
    `;
    document.documentElement.appendChild(style);
  }

  function buttonIconHtml() {
    return `
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3v11" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
        <path d="M7.5 9.5 12 14l4.5-4.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M5 17.5v1.2A2.3 2.3 0 0 0 7.3 21h9.4a2.3 2.3 0 0 0 2.3-2.3v-1.2" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>
      </svg>
    `;
  }

  function createPlayerButton(container) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = PLAYER_BUTTON_CLASS;
    button.innerHTML = buttonIconHtml();
    button.setAttribute("aria-label", "推送到 ClipNest");
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (event.shiftKey) {
        openSettings();
        return;
      }
      pushCurrent(Boolean(event.altKey), container.closest(".basePlayerContainer") || container);
    });
    button.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openSettings();
    });
    return button;
  }

  function playerToolbars() {
    const selectors = [
      ".basePlayerContainer xg-right-grid",
      ".basePlayerContainer [class*='right'][class*='grid']",
      "[data-e2e='video-share-container']",
    ];
    const result = [];
    const seen = new Set();
    for (const selector of selectors) {
      for (const node of document.querySelectorAll(selector)) {
        if (!(node instanceof Element) || seen.has(node)) {
          continue;
        }
        seen.add(node);
        result.push(node);
      }
    }
    return result;
  }

  function ensurePlayerButtons() {
    addStyles();
    document.querySelectorAll(".clipnest-player-button-host").forEach((node) => node.remove());
    for (const toolbar of playerToolbars()) {
      if (toolbar.querySelector(`.${PLAYER_BUTTON_CLASS}`)) {
        continue;
      }
      const player = toolbar.closest(".basePlayerContainer") || toolbar;
      const existingInPlayer = player.querySelector(`.${PLAYER_BUTTON_CLASS}`);
      if (existingInPlayer && existingInPlayer.parentElement !== toolbar) {
        existingInPlayer.remove();
      } else if (existingInPlayer) {
        continue;
      }
      const button = createPlayerButton(toolbar);
      toolbar.prepend(button);
    }
  }

  function observeVideos(scheduleUpdate) {
    for (const video of document.querySelectorAll("video")) {
      if (!(video instanceof HTMLVideoElement) || state.observedVideos.has(video)) {
        continue;
      }
      state.observedVideos.add(video);
      video.addEventListener("play", scheduleUpdate, { passive: true });
      video.addEventListener("pause", scheduleUpdate, { passive: true });
      video.addEventListener("loadedmetadata", scheduleUpdate, { passive: true });
      video.addEventListener("emptied", scheduleUpdate, { passive: true });
    }
  }

  function updatePlayerButtons() {
    ensurePlayerButtons();
    const buttons = Array.from(document.querySelectorAll(`.${PLAYER_BUTTON_CLASS}`));
    let firstItem = null;
    for (const button of buttons) {
      const root = button.closest(".basePlayerContainer") || button.parentElement;
      const item = detectCurrentItem(root);
      if (!firstItem && item) {
        firstItem = item;
      }
      button.disabled = state.busy || !item;
      button.classList.toggle("is-busy", state.busy);
      button.innerHTML = state.busy ? '<span class="clipnest-spinner" aria-hidden="true"></span>' : buttonIconHtml();
      if (item) {
        button.removeAttribute("title");
        delete button.dataset.clipnestTip;
      } else {
        button.removeAttribute("title");
        delete button.dataset.clipnestTip;
      }
    }
    state.current = firstItem;
  }

  function toast(message, type = "info", duration = 2600) {
    addStyles();
    const old = document.getElementById("clipnest-push-toast");
    if (old) {
      old.remove();
    }
    const node = document.createElement("div");
    node.id = "clipnest-push-toast";
    node.className = type;
    node.textContent = message;
    document.documentElement.appendChild(node);
    window.setTimeout(() => node.remove(), duration);
  }

  function hookHistory() {
    const emit = () => {
      window.dispatchEvent(new Event("clipnest-location-change"));
    };
    for (const name of ["pushState", "replaceState"]) {
      const original = history[name];
      history[name] = function (...args) {
        const result = original.apply(this, args);
        emit();
        return result;
      };
    }
    window.addEventListener("popstate", emit);
  }

  function registerMenus() {
    if (typeof GM_registerMenuCommand !== "function") {
      return;
    }
    GM_registerMenuCommand("ClipNest: 推送当前作品", () => pushCurrent(false));
    GM_registerMenuCommand("ClipNest: 预检当前作品", () => pushCurrent(true));
    GM_registerMenuCommand("ClipNest: 设置地址和 Token", openSettings);
  }

  function init() {
    ensurePlayerButtons();
    hookHistory();
    registerMenus();
    const scheduleUpdate = debounce(updatePlayerButtons, 350);
    const scheduleObserveAndUpdate = debounce(() => {
      observeVideos(scheduleUpdate);
      updatePlayerButtons();
    }, 250);
    window.addEventListener("clipnest-location-change", scheduleUpdate);
    window.addEventListener("hashchange", scheduleUpdate);
    window.addEventListener("focus", scheduleUpdate);
    new MutationObserver(scheduleObserveAndUpdate).observe(document.documentElement, {
      childList: true,
      subtree: true,
    });
    window.setInterval(scheduleObserveAndUpdate, 1000);
    observeVideos(scheduleUpdate);
    updatePlayerButtons();
  }

  function debounce(fn, delay) {
    let timer = 0;
    return function (...args) {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fn.apply(this, args), delay);
    };
  }

  init();
})();
