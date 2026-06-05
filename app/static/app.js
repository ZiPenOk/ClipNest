const state = {
  token: localStorage.getItem("clipnest-token") || document.querySelector("#token").value || "",
  authenticated: false,
  currentView: ["dashboard", "library", "sync", "tasks", "logs", "settings"].includes(sessionStorage.getItem("clipnest-view"))
    ? sessionStorage.getItem("clipnest-view")
    : "dashboard",
  jobs: [],
  activeJobs: [],
  authorCrawls: [],
  tasksPage: 1,
  tasksTotal: 0,
  tasksTotalPages: 1,
  logs: [],
  logsPage: 1,
  logsTotal: 0,
  logsTotalPages: 1,
  logsEventTypes: [],
  logsSearch: "",
  logsType: "",
  logsPlatform: "",
  logsStatus: "",
  logsDateFrom: "",
  logsDateTo: "",
  stats: null,
  authors: [],
  libraryAuthors: [],
  libraryAuthorsTotal: 0,
  libraryAuthorsTotalPages: 1,
  libraryMediaJobs: [],
  libraryMediaTotal: 0,
  libraryMediaTotalPages: 1,
  libraryRecords: [],
  libraryRecordsTotal: 0,
  libraryRecordsTotalPages: 1,
  libraryRecordsKind: ["media", "deleted"].includes(localStorage.getItem("clipnest-library-record-kind"))
    ? localStorage.getItem("clipnest-library-record-kind")
    : "media",
  libraryAuthorDetail: null,
  syncAuthors: [],
  syncAuthorsTotal: 0,
  syncAuthorsTotalPages: 1,
  syncAuthorsPage: 1,
  syncSources: [],
  syncSourcesTotal: 0,
  syncSourcesTotalPages: 1,
  syncSourceStats: { total: 0, enabled: 0, disabled: 0, missing_identity: 0 },
  syncDetail: null,
  syncSearch: "",
  syncEnabledFilter: ["", "enabled", "disabled"].includes(localStorage.getItem("clipnest-sync-enabled-filter") || "")
    ? (localStorage.getItem("clipnest-sync-enabled-filter") || "")
    : "",
  syncPageSize: (() => {
    const stored = Number(localStorage.getItem("clipnest-sync-page-size") || 12);
    return [12, 24, 48].includes(stored) ? stored : 12;
  })(),
  selectedSyncSourceIds: new Set(),
  selectedJobIds: new Set(),
  taskSearch: "",
  statusFilter: "",
  authorFilter: "",
  taskPlatform: "",
  librarySearch: "",
  libraryMode: ["authors", "media", "records"].includes(localStorage.getItem("clipnest-library-mode"))
    ? localStorage.getItem("clipnest-library-mode")
    : "authors",
  libraryPlatform: ["", "douyin", "tiktok"].includes(localStorage.getItem("clipnest-library-platform") || "")
    ? (localStorage.getItem("clipnest-library-platform") || "")
    : "",
  libraryAuthor: "",
  libraryType: "",
  librarySort: "publish_desc",
  recordStatus: localStorage.getItem("clipnest-record-status") || "finished",
  recordAuthor: "",
  recordDateField: localStorage.getItem("clipnest-record-date-field") || "download",
  recordDateFrom: "",
  recordDateTo: "",
  libraryAuthorsPage: 1,
  libraryMediaPage: 1,
  libraryRecordsPage: 1,
  libraryMediaCache: new Map(),
  libraryMediaPending: new Map(),
  libraryMediaTransitioning: false,
  libraryMediaTargetPage: null,
  libraryMediaQueuedPage: null,
  libraryMediaQueuedDirection: 0,
  libraryMediaQueuedForce: false,
  libraryEditMode: false,
  selectedLibraryAuthors: new Set(),
  selectedLibraryJobIds: new Set(),
  reelJobs: [],
  reelIndex: 0,
  reelTouchStartY: 0,
  reelVideoWidth: 9,
  reelVideoHeight: 16,
  reelVolume: (() => {
    const stored = localStorage.getItem("clipnest-reel-volume");
    const value = stored === null ? NaN : Number(stored);
    return Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 1;
  })(),
  reelMuted: localStorage.getItem("clipnest-reel-muted") === "true",
  pendingQualityPreview: null,
  pendingQualityAction: null,
};

const libraryAuthorsPageSize = 24;
const libraryMediaPageSize = 12;
const tasksPageSize = 15;
const authorMaxItemsStorageKey = "clipnest-author-max-items";
const authorCrawlPageSize = 18;

const tokenInput = document.querySelector("#token");
const loginPanelEl = document.querySelector("#login-panel");
const sessionStatusEl = document.querySelector("#session-status");
const logoutButton = document.querySelector("#logout");
const urlsInput = document.querySelector("#urls");
const submitButton = document.querySelector("#submit");
const authorCrawlUrlInput = document.querySelector("#author-crawl-url");
const authorCrawlMaxInput = document.querySelector("#author-crawl-max");
const authorCrawlButton = document.querySelector("#author-crawl-submit");
const authorCrawlResultEl = document.querySelector("#author-crawl-result");
const authorCrawlJobsEl = document.querySelector("#author-crawl-jobs");
const summaryEl = document.querySelector("#summary");
const statsEl = document.querySelector("#stats");
const dashboardChartEl = document.querySelector("#dashboard-chart");
const dashboardPlatformsEl = document.querySelector("#dashboard-platforms");
const dashboardRecentEl = document.querySelector("#dashboard-recent");
const activeJobsEl = document.querySelector("#active-jobs");
const viewKickerEl = document.querySelector("#view-kicker");
const viewTitleEl = document.querySelector("#view-title");
const logsRefreshButton = document.querySelector("#logs-refresh");
const logsSearchInput = document.querySelector("#logs-search");
const logsTypeFilter = document.querySelector("#logs-type-filter");
const logsPlatformFilter = document.querySelector("#logs-platform-filter");
const logsStatusFilter = document.querySelector("#logs-status-filter");
const logsDateFrom = document.querySelector("#logs-date-from");
const logsDateTo = document.querySelector("#logs-date-to");
const logsClearFilterButton = document.querySelector("#logs-clear-filter");
const logsOverviewEl = document.querySelector("#logs-overview");
const logsEventsEl = document.querySelector("#logs-events");
const logsPaginationEl = document.querySelector("#logs-pagination");
const librarySectionKicker = document.querySelector("#library-section-kicker");
const librarySectionTitle = document.querySelector("#library-section-title");
const libraryAuthorsPanel = document.querySelector("#library-authors-panel");
const libraryMediaPanel = document.querySelector("#library-media-panel");
const libraryRecordsPanel = document.querySelector("#library-records-panel");
const libraryOverviewEl = document.querySelector("#library-overview");
const libraryAuthorsEl = document.querySelector("#library-authors");
const libraryAuthorsPaginationEl = document.querySelector("#library-authors-pagination");
const libraryAuthorDetailEl = document.querySelector("#library-author-detail");
const libraryMediaEl = document.querySelector("#library-media");
const libraryMediaPaginationEl = document.querySelector("#library-media-pagination");
const libraryRecordsHeadEl = document.querySelector("#library-records-head");
const libraryRecordsEl = document.querySelector("#library-records");
const libraryRecordsPaginationEl = document.querySelector("#library-records-pagination");
const librarySearchInput = document.querySelector("#library-search");
const libraryTypeFilter = document.querySelector("#library-type-filter");
const librarySort = document.querySelector("#library-sort");
const libraryClearButton = document.querySelector("#library-clear");
const libraryPlayModeButton = document.querySelector("#library-play-mode");
const libraryPlatformTabsEl = document.querySelector("#library-platform-tabs");
const libraryRefreshButton = document.querySelector("#library-refresh");
const libraryEditToggleButton = document.querySelector("#library-edit-toggle");
const librarySelectPageButton = document.querySelector("#library-select-page");
const libraryInvertPageButton = document.querySelector("#library-invert-page");
const libraryDeleteSelectedButton = document.querySelector("#library-delete-selected");
const libraryFilterLabel = document.querySelector("#library-filter-label");
const recordToolsEl = document.querySelector(".record-tools");
const recordClearDeletedButton = document.querySelector("#record-clear-deleted");
const recordStatusFilter = document.querySelector("#record-status-filter");
const recordAuthorFilter = document.querySelector("#record-author-filter");
const recordDateField = document.querySelector("#record-date-field");
const recordDateFrom = document.querySelector("#record-date-from");
const recordDateTo = document.querySelector("#record-date-to");
const recordFilterClearButton = document.querySelector("#record-filter-clear");
const syncSearchInput = document.querySelector("#sync-search");
const syncEnabledFilterSelect = document.querySelector("#sync-enabled-filter");
const syncPageSizeSelect = document.querySelector("#sync-page-size");
const syncMaxItemsInput = document.querySelector("#sync-max-items");
const syncSourceUrlInput = document.querySelector("#sync-source-url");
const syncSourceNameInput = document.querySelector("#sync-source-name");
const syncSourceAddButton = document.querySelector("#sync-source-add");
const syncImportLibraryButton = document.querySelector("#sync-import-library");
const syncRunEnabledButton = document.querySelector("#sync-run-enabled");
const syncBulkActionsEl = document.querySelector("#sync-bulk-actions");
const syncBulkCountEl = document.querySelector("#sync-bulk-count");
const syncSelectPageButton = document.querySelector("#sync-select-page");
const syncInvertPageButton = document.querySelector("#sync-invert-page");
const syncClearSelectionButton = document.querySelector("#sync-clear-selection");
const syncApplyDefaultsButton = document.querySelector("#sync-apply-defaults");
const syncEnableSelectedButton = document.querySelector("#sync-enable-selected");
const syncDisableSelectedButton = document.querySelector("#sync-disable-selected");
const syncRunSelectedButton = document.querySelector("#sync-run-selected");
const syncRunSelectedFullButton = document.querySelector("#sync-run-selected-full");
const syncDeleteSelectedButton = document.querySelector("#sync-delete-selected");
const syncRefreshButton = document.querySelector("#sync-refresh");
const syncJobsRefreshButton = document.querySelector("#sync-jobs-refresh");
const syncJobsCleanupButton = document.querySelector("#sync-jobs-cleanup");
const syncOverviewEl = document.querySelector("#sync-overview");
const syncAuthorsEl = document.querySelector("#sync-authors");
const syncDetailEl = document.querySelector("#sync-detail");
const syncAuthorsPaginationEl = document.querySelector("#sync-authors-pagination");
const syncCrawlJobsEl = document.querySelector("#sync-crawl-jobs");

function clampAuthorMaxItems(value, fallback = 200) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(1, Math.min(1000, Math.round(parsed))) : fallback;
}

function setAuthorMaxInputs(value) {
  const normalized = String(clampAuthorMaxItems(value));
  if (authorCrawlMaxInput) authorCrawlMaxInput.value = normalized;
  if (syncMaxItemsInput) syncMaxItemsInput.value = normalized;
}

function persistAuthorMaxItems(value, normalizeInputs = false) {
  const text = String(value ?? "").trim();
  const fallback = clampAuthorMaxItems(localStorage.getItem(authorMaxItemsStorageKey) || 200);
  if (!text) return fallback;
  const normalized = clampAuthorMaxItems(text, fallback);
  localStorage.setItem(authorMaxItemsStorageKey, String(normalized));
  if (normalizeInputs) setAuthorMaxInputs(normalized);
  return normalized;
}

function authorCrawlMaxPages(maxItems) {
  return Math.max(30, Math.min(100, Math.ceil(clampAuthorMaxItems(maxItems) / authorCrawlPageSize) + 5));
}

setAuthorMaxInputs(localStorage.getItem(authorMaxItemsStorageKey) || 200);
if (syncEnabledFilterSelect) syncEnabledFilterSelect.value = state.syncEnabledFilter;
if (syncPageSizeSelect) syncPageSizeSelect.value = String(state.syncPageSize);

const searchInput = document.querySelector("#search");
const statusFilter = document.querySelector("#status-filter");
const taskPlatformTabsEl = document.querySelector("#task-platform-tabs");
const tasksRefreshButton = document.querySelector("#tasks-refresh");
const tasksClearFailedButton = document.querySelector("#tasks-clear-failed");
const tasksClearCancelledButton = document.querySelector("#tasks-clear-cancelled");
const authorsEl = document.querySelector("#authors");
const jobsEl = document.querySelector("#jobs");
const tasksPaginationEl = document.querySelector("#tasks-pagination");
const taskAuthorCrawlsEl = document.querySelector("#task-author-crawls");
const downloadTaskTitleEl = document.querySelector("#download-task-title");
const downloadTaskCountEl = document.querySelector("#download-task-count");
const authorCrawlTaskCountEl = document.querySelector("#author-crawl-task-count");
const bulkActionsEl = document.querySelector("#bulk-actions");
const bulkCountEl = document.querySelector("#bulk-count");
const bulkRetryButton = document.querySelector("#bulk-retry");
const bulkRedownloadButton = document.querySelector("#bulk-redownload");
const bulkCancelButton = document.querySelector("#bulk-cancel");
const bulkDeleteButton = document.querySelector("#bulk-delete");
const tasksSelectAllButton = document.querySelector("#tasks-select-all");
const tasksInvertSelectionButton = document.querySelector("#tasks-invert-selection");
const tasksClearSelectionButton = document.querySelector("#tasks-clear-selection");
const drawerEl = document.querySelector("#job-drawer");
const drawerScrimEl = document.querySelector("#drawer-scrim");
const drawerTitleEl = document.querySelector("#drawer-title");
const drawerKickerEl = document.querySelector("#drawer-kicker");
const drawerBodyEl = document.querySelector("#job-detail");
const mediaPreviewDialogEl = document.querySelector("#media-preview-dialog");
const mediaPreviewCloseButton = document.querySelector("#media-preview-close");
const mediaPreviewKickerEl = document.querySelector("#media-preview-kicker");
const mediaPreviewTitleEl = document.querySelector("#media-preview-title");
const mediaPreviewBodyEl = document.querySelector("#media-preview-body");
const reelViewerEl = document.querySelector("#reel-viewer");
const reelStageEl = document.querySelector("#reel-stage");
const reelInfoEl = document.querySelector("#reel-info");
const reelCloseButton = document.querySelector("#reel-close");
const reelPrevButton = document.querySelector("#reel-prev");
const reelNextButton = document.querySelector("#reel-next");
const reelDeleteButton = document.querySelector("#reel-delete");
const settingSkipExisting = document.querySelector("#setting-skip-existing");
const settingQueuePaused = document.querySelector("#setting-queue-paused");
const settingMaxConcurrent = document.querySelector("#setting-max-concurrent");
const settingAutoRetryAttempts = document.querySelector("#setting-auto-retry-attempts");
const settingAutoRetryDelay = document.querySelector("#setting-auto-retry-delay");
const settingAuthorFolders = document.querySelector("#setting-author-folders");
const settingFilenameTemplate = document.querySelector("#setting-filename-template");
const settingTelegramEnabled = document.querySelector("#setting-telegram-enabled");
const settingTelegramToken = document.querySelector("#setting-telegram-token");
const settingTelegramStatus = document.querySelector("#setting-telegram-status");
const settingTelegramChatId = document.querySelector("#setting-telegram-chat-id");
const settingTelegramSuccess = document.querySelector("#setting-telegram-success");
const settingTelegramFailure = document.querySelector("#setting-telegram-failure");
const telegramTestButton = document.querySelector("#telegram-test");
const settingParserAdapter = document.querySelector("#setting-parser-adapter");
const settingDouyinCookie = document.querySelector("#setting-douyin-cookie");
const settingDouyinCookieStatus = document.querySelector("#setting-douyin-cookie-status");
const settingTikTokCookie = document.querySelector("#setting-tiktok-cookie");
const settingTikTokCookieStatus = document.querySelector("#setting-tiktok-cookie-status");
const settingDouyinUserAgent = document.querySelector("#setting-douyin-user-agent");
const parserInfoEl = document.querySelector("#parser-info");
const parserHealthButton = document.querySelector("#parser-health");
const settingsSaveButton = document.querySelector("#settings-save");
const settingsSaveStatus = document.querySelector("#settings-save-status");
const maintenanceHealthButton = document.querySelector("#maintenance-health");
const maintenanceCookieButton = document.querySelector("#maintenance-cookie");
const maintenanceTikTokButton = document.querySelector("#maintenance-tiktok");
const maintenanceEventsButton = document.querySelector("#maintenance-events");
const maintenanceExportButton = document.querySelector("#maintenance-export");
const maintenanceBackupButton = document.querySelector("#maintenance-backup");
const maintenanceCacheAssetsButton = document.querySelector("#maintenance-cache-assets");
const maintenanceDuplicatesButton = document.querySelector("#maintenance-duplicates");
const maintenanceCleanDuplicatesButton = document.querySelector("#maintenance-clean-duplicates");
const maintenanceOrphansButton = document.querySelector("#maintenance-orphans");
const maintenanceCleanOrphansButton = document.querySelector("#maintenance-clean-orphans");
const maintenanceOutputEl = document.querySelector("#maintenance-output");
const qualityDialogEl = document.querySelector("#quality-dialog");
const qualityCloseButton = document.querySelector("#quality-close");
const qualityPlatformEl = document.querySelector("#quality-platform");
const qualityTitleEl = document.querySelector("#quality-title");
const qualityCoverEl = document.querySelector("#quality-cover");
const qualityAuthorEl = document.querySelector("#quality-author");
const qualityVideoIdEl = document.querySelector("#quality-video-id");
const qualityOptionsEl = document.querySelector("#quality-options");

const runningStatuses = new Set(["parsing", "downloading", "cancelling"]);
const statusLabels = {
  queued: "排队",
  retry: "重试",
  parsing: "解析",
  downloading: "下载",
  cancelling: "取消中",
  cancelled: "已取消",
  finished: "完成",
  failed: "失败",
};
let logsSearchTimer = null;

tokenInput.value = state.token;

function headers() {
  const values = { "Content-Type": "application/json" };
  if (state.token) values["X-Api-Token"] = state.token;
  return values;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    credentials: "same-origin",
    headers: { ...headers(), ...(options.headers || {}) },
  });
  if (!response.ok) {
    let text = await response.text();
    try {
      const parsed = JSON.parse(text);
      text = parsed.detail || text;
    } catch (_) {}
    throw new Error(text || response.statusText);
  }
  if (response.status === 204) return null;
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function fmtBytes(value) {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = Number(value);
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index ? 1 : 0)} ${units[index]}`;
}

function fmtDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", { hour12: false });
}

function fmtEpoch(value) {
  if (!value) return "-";
  const number = Number(value);
  if (!Number.isFinite(number)) return String(value);
  return fmtDate(new Date(number * 1000).toISOString());
}

function fmtDuration(value) {
  if (!value) return "-";
  const total = Math.round(Number(value));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  if (hours) return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function statusLabel(status) {
  return statusLabels[status] || status || "-";
}

function crawlStatusLabel(status) {
  return {
    queued: "排队",
    running: "抓取中",
    pausing: "暂停中",
    paused: "已暂停",
    cancelling: "取消中",
    cancelled: "已取消",
    finished: "完成",
    failed: "失败",
  }[status] || status || "-";
}

function mediaUrl(job, field) {
  const tokenQuery = state.token ? `?token=${encodeURIComponent(state.token)}` : "";
  return `/api/jobs/${job.id}/${field}${tokenQuery}`;
}

function assetUrl(path) {
  const cleanPath = String(path || "").split("/").filter(Boolean).map(encodeURIComponent).join("/");
  const tokenQuery = state.token ? `?token=${encodeURIComponent(state.token)}` : "";
  return cleanPath ? `/api/assets/${cleanPath}${tokenQuery}` : "";
}

function clearLibraryMediaCache() {
  state.libraryMediaCache.clear();
  state.libraryMediaPending.clear();
}

function cleanUrl(value) {
  return String(value || "").trim().replace(/[.,;)\uFF0C\u3002\uFF1B]+$/g, "");
}

async function copyText(value) {
  const text = String(value || "");
  if (!text) return false;
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  const input = document.createElement("textarea");
  input.value = text;
  input.style.position = "fixed";
  input.style.left = "-9999px";
  document.body.appendChild(input);
  input.focus();
  input.select();
  const copied = document.execCommand("copy");
  document.body.removeChild(input);
  return copied;
}

function extractUrls(text) {
  const matches = text.match(/https?:\/\/[^\s"'<>]+/g) || [];
  const candidates = matches.length ? matches : [text];
  const urls = [];
  const seen = new Set();
  for (const candidate of candidates) {
    const url = cleanUrl(candidate);
    if (!url.startsWith("http") || seen.has(url)) continue;
    urls.push(url);
    seen.add(url);
  }
  return urls;
}

function renderSession() {
  sessionStatusEl.textContent = state.authenticated ? "已登录" : "未登录";
  loginPanelEl.hidden = state.authenticated;
  logoutButton.hidden = !state.authenticated;
}

function viewTitleParts(view) {
  if (view === "library") {
    if (state.libraryMode === "media") return ["媒体库", "按作品浏览媒体"];
    if (state.libraryMode === "records") return ["媒体库", "按记录管理媒体"];
    return ["媒体库", "按作者管理作品"];
  }
  return {
    dashboard: ["工作台", "下载工作台"],
    sync: ["同步", "作者作品同步"],
    tasks: ["任务", "队列和历史"],
    logs: ["日志", "运维日志"],
    settings: ["设置", "规则和维护"],
  }[view] || ["工作台", "下载工作台"];
}

function renderViewHeader() {
  const [kicker, title] = viewTitleParts(state.currentView);
  viewKickerEl.textContent = kicker;
  viewTitleEl.textContent = title;
}

function setView(view) {
  if (!["dashboard", "library", "sync", "tasks", "logs", "settings"].includes(view)) view = "dashboard";
  state.currentView = view;
  sessionStorage.setItem("clipnest-view", view);
  document.querySelectorAll(".view").forEach((item) => {
    item.hidden = item.id !== `view-${view}`;
    item.classList.toggle("active", item.id === `view-${view}`);
  });
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === view);
  });
  renderViewHeader();
  if (view === "settings" && state.authenticated) loadSettings();
  if (view === "library" && state.authenticated) loadLibraryPage();
  if (view === "sync" && state.authenticated) loadSyncPage();
  if (view === "logs" && state.authenticated) loadLogsPage();
}

function setLibraryMode(mode) {
  state.libraryMode = ["authors", "media", "records"].includes(mode) ? mode : "authors";
  localStorage.setItem("clipnest-library-mode", state.libraryMode);
  clearLibraryMediaCache();
  clearLibrarySelection();
  state.libraryEditMode = false;
  renderViewHeader();
}

function setLibraryPlatform(platform) {
  state.libraryPlatform = ["douyin", "tiktok"].includes(platform) ? platform : "";
  localStorage.setItem("clipnest-library-platform", state.libraryPlatform);
  state.libraryAuthor = "";
  state.libraryAuthorDetail = null;
  state.libraryAuthorsPage = 1;
  state.libraryMediaPage = 1;
  state.libraryRecordsPage = 1;
  clearLibraryMediaCache();
  clearLibrarySelection();
}

async function checkSession() {
  const response = await fetch("/api/session", { credentials: "same-origin" });
  state.authenticated = response.ok;
  renderSession();
  return state.authenticated;
}

async function loginWithToken(token) {
  const response = await fetch("/api/session", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  if (!response.ok) throw new Error(await response.text());
  state.authenticated = true;
  state.token = "";
  tokenInput.value = "";
  localStorage.removeItem("clipnest-token");
  renderSession();
}

function renderStats(stats) {
  statsEl.innerHTML = `
    <div class="stat stat-total"><span>总数</span><strong>${stats.total || 0}</strong></div>
    <div class="stat stat-running"><span>运行</span><strong>${stats.running || 0}</strong></div>
    <div class="stat stat-queued"><span>排队</span><strong>${stats.queued || 0}</strong></div>
    <div class="stat stat-finished"><span>完成</span><strong>${stats.finished || 0}</strong></div>
    <div class="stat stat-failed"><span>失败</span><strong>${stats.failed || 0}</strong></div>
    <div class="stat stat-cancelled"><span>取消</span><strong>${stats.cancelled || 0}</strong></div>
    <div class="stat stat-storage"><span>占用</span><strong>${fmtBytes(stats.bytes || 0)}</strong></div>
  `;
  renderDashboardInsights(stats);
}

function renderDashboardInsights(stats) {
  const chart = Array.isArray(stats.chart) ? stats.chart : [];
  dashboardChartEl.innerHTML = renderDashboardChart(chart);

  const platforms = Array.isArray(stats.platforms) ? stats.platforms : [];
  const media = stats.media || {};
  const platformMax = Math.max(1, ...platforms.map((item) => Number(item.finished || 0)));
  dashboardPlatformsEl.innerHTML = `
    <div class="platform-metrics">
      <div><span>视频</span><strong>${Number(media.videos || 0)}</strong></div>
      <div><span>图集</span><strong>${Number(media.images || 0)}</strong></div>
      <div><span>已删除</span><strong>${Number(stats.deleted || 0)}</strong></div>
    </div>
    <div class="platform-bars">
      ${platforms.length ? platforms.map((item) => `
        <div class="platform-row">
          <div>
            <span>${escapeHtml(platformLabel(item.platform || ""))}</span>
            <strong>${Number(item.finished || 0)} 完成 / ${fmtBytes(item.bytes || 0)}</strong>
          </div>
          <i style="--value:${Math.max(3, Math.round((Number(item.finished || 0) / platformMax) * 100))}%"></i>
        </div>
      `).join("") : `<div class="empty compact">暂无平台数据</div>`}
    </div>
  `;

  const recent = (Array.isArray(stats.recent) ? stats.recent : []).slice(0, 4);
  dashboardRecentEl.innerHTML = recent.length ? recent.map((item) => `
    <button class="recent-row ${escapeHtml(item.status || "")}" type="button" data-dashboard-job="${item.id}">
      <strong>${escapeHtml(item.title || item.description || `任务 #${item.id}`)}</strong>
      <span>${platformLabel(item.platform || "")} · ${escapeHtml(item.author_name || "Unknown")} · ${statusLabel(item.status)} · ${fmtBytes(item.size_bytes || 0)}</span>
      ${item.error ? `<em>${escapeHtml(friendlyError(item.error, item.platform))}</em>` : ""}
    </button>
  `).join("") : `<div class="empty compact">暂无最近记录</div>`;
}

function renderDashboardChart(chart) {
  if (!chart.length) return `<div class="empty compact">暂无趋势数据</div>`;
  const series = normalizeDashboardChart(chart);
  const values = series.map((item) => Number(item.finished || 0));
  const bytesValues = series.map((item) => Number(item.bytes || 0));
  const maxValue = Math.max(1, ...values);
  const total = values.reduce((sum, value) => sum + value, 0);
  const totalBytes = bytesValues.reduce((sum, value) => sum + value, 0);
  const peakValue = Math.max(...values);
  const peakIndex = values.indexOf(peakValue);
  const width = 640;
  const height = 220;
  const padding = { top: 18, right: 18, bottom: 34, left: 46 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const xFor = (index) => padding.left + (series.length === 1 ? plotWidth / 2 : (plotWidth * index) / (series.length - 1));
  const yFor = (value) => padding.top + plotHeight - (value / maxValue) * plotHeight;
  const points = values.map((value, index) => [xFor(index), yFor(value)]);
  const linePath = points.map(([x, y], index) => `${index ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L ${xFor(series.length - 1).toFixed(1)} ${(padding.top + plotHeight).toFixed(1)} L ${xFor(0).toFixed(1)} ${(padding.top + plotHeight).toFixed(1)} Z`;
  const tickIndexes = Array.from(new Set([0, Math.floor((series.length - 1) / 2), series.length - 1])).filter((index) => index >= 0);
  const gridLines = [0, 0.5, 1].map((ratio) => {
    const y = padding.top + plotHeight * ratio;
    return `<line x1="${padding.left}" x2="${width - padding.right}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}"></line>`;
  }).join("");
  const yLabels = [maxValue, Math.round(maxValue / 2), 0].map((value) => `
    <text x="${padding.left - 10}" y="${(yFor(value) + 4).toFixed(1)}" text-anchor="end">${value}</text>
  `).join("");
  const labels = tickIndexes.map((index) => `
    <text x="${xFor(index).toFixed(1)}" y="${height - 10}" text-anchor="${index === 0 ? "start" : index === series.length - 1 ? "end" : "middle"}">${escapeHtml(String(series[index].day || "").slice(5))}</text>
  `).join("");
  const dots = points.map(([x, y], index) => {
    const item = series[index];
    const value = values[index];
    const valueText = `${value} 个`;
    const tooltipWidth = Math.max(44, Math.min(86, 22 + valueText.length * 8));
    const tooltipX = Math.max(padding.left - 8, Math.min(width - padding.right - tooltipWidth, x - tooltipWidth / 2));
    const tooltipY = Math.max(4, y - 34);
    return `
      <g class="trend-point" tabindex="0" aria-label="${escapeHtml(item.day)} ${valueText}">
        <line class="trend-guide" x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${padding.top}" y2="${(padding.top + plotHeight).toFixed(1)}"></line>
        <circle class="trend-hit" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="13"></circle>
        <circle class="trend-dot ${index === peakIndex && peakValue ? "peak" : ""}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${index === peakIndex && peakValue ? 5 : 3.5}"></circle>
        <g class="trend-tooltip">
          <rect x="${tooltipX.toFixed(1)}" y="${tooltipY.toFixed(1)}" width="${tooltipWidth.toFixed(1)}" height="24" rx="6"></rect>
          <text x="${(tooltipX + tooltipWidth / 2).toFixed(1)}" y="${(tooltipY + 16).toFixed(1)}" text-anchor="middle">${valueText}</text>
        </g>
        <title>${escapeHtml(item.day)} / ${value} 个 / ${fmtBytes(item.bytes || 0)}</title>
      </g>
    `;
  }).join("");
  const peakItem = series[Math.max(0, peakIndex)] || {};
  return `
    <div class="chart-summary">
      <div><span>14 天完成</span><strong>${total}</strong></div>
      <div><span>峰值</span><strong>${peakValue} 个</strong></div>
      <div><span>新增体积</span><strong>${fmtBytes(totalBytes)}</strong></div>
    </div>
    <svg class="trend-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="近 14 天下载趋势">
      <defs>
        <linearGradient id="trend-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#0f766e" stop-opacity="0.26"></stop>
          <stop offset="100%" stop-color="#0f766e" stop-opacity="0.02"></stop>
        </linearGradient>
      </defs>
      <g class="trend-grid">${gridLines}</g>
      <g class="trend-y-labels">${yLabels}</g>
      <path class="trend-area" d="${areaPath}"></path>
      <path class="trend-line" d="${linePath}"></path>
      <g class="trend-dots">${dots}</g>
      <g class="trend-labels">${labels}</g>
    </svg>
    <div class="chart-foot">
      <span>峰值 ${escapeHtml(String(peakItem.day || "").slice(5) || "-")}</span>
      <span>按完成时间统计</span>
    </div>
  `;
}

function normalizeDashboardChart(chart) {
  const byDay = new Map(chart.map((item) => [String(item.day || ""), item]));
  const today = new Date();
  const series = [];
  for (let index = 13; index >= 0; index -= 1) {
    const date = new Date(today);
    date.setDate(today.getDate() - index);
    const day = [
      date.getFullYear(),
      String(date.getMonth() + 1).padStart(2, "0"),
      String(date.getDate()).padStart(2, "0"),
    ].join("-");
    const item = byDay.get(day) || {};
    series.push({
      day,
      finished: Number(item.finished || 0),
      failed: Number(item.failed || 0),
      bytes: Number(item.bytes || 0),
    });
  }
  return series;
}

function jobMatchesSearch(job, query) {
  if (!query) return true;
  const text = [job.title, job.description, job.author_name, job.video_id, job.url].join(" ").toLowerCase();
  return text.includes(query.toLowerCase());
}

function timestampValue(value) {
  if (!value) return 0;
  const time = new Date(value).getTime();
  return Number.isFinite(time) ? time : 0;
}

function publishTimestampValue(job) {
  const metadata = job && job.metadata ? job.metadata : {};
  const value = Number(metadata.create_time || 0);
  return Number.isFinite(value) ? value : 0;
}

function mediaType(job) {
  const metadataType = job.metadata && job.metadata.type;
  if (metadataType === "image") return "image";
  const path = String(job.file_path || "").toLowerCase();
  if (/\.(jpe?g|png|webp|gif)$/.test(path)) return "image";
  return "video";
}

function mediaTypeLabel(job) {
  return mediaType(job) === "image" ? "图集" : "视频";
}

function mediaPreviewSource(job) {
  return assetUrl(job.cover_path) || job.cover_url || (job.preview_path ? mediaUrl(job, "preview") : "");
}

function platformBadge(job) {
  const platform = String(job.platform || "").toLowerCase();
  if (!platform) return "";
  return `<span class="platform-badge ${escapeHtml(platform)}">${escapeHtml(platformLabel(platform))}</span>`;
}

function friendlyError(value, platform = "") {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const lower = raw.toLowerCase();
  const cleanPlatform = String(platform || "").toLowerCase();
  if (lower.includes("cookie") || lower.includes("login") || lower.includes("captcha")) {
    return `${platformLabel(cleanPlatform)} Cookie 可能失效或需要重新登录`;
  }
  if (lower.includes("403") || lower.includes("forbidden")) {
    return "链接被平台拒绝访问，建议更新 Cookie 后重试";
  }
  if (lower.includes("404") || lower.includes("not found")) {
    return "作品可能已删除、私密或链接无效";
  }
  if (lower.includes("timeout") || lower.includes("timed out")) {
    return "网络超时，稍后重试或检查代理/网络";
  }
  if (cleanPlatform === "tiktok" && (lower.includes("region") || lower.includes("signature") || lower.includes("aweme"))) {
    return "TikTok 解析受地区或签名影响，建议补充 Cookie 后重试";
  }
  return raw.split("\n")[0];
}

function filteredTasks() {
  return state.jobs.filter((job) => {
    if (state.statusFilter && job.status !== state.statusFilter) return false;
    if (state.authorFilter && (job.author_name || "Unknown") !== state.authorFilter) return false;
    if (state.taskPlatform && String(job.platform || "").toLowerCase() !== state.taskPlatform) return false;
    return jobMatchesSearch(job, state.taskSearch);
  });
}

function libraryJobs() {
  const items = state.libraryMediaJobs.filter((job) => {
    if (job.status !== "finished") return false;
    if (state.libraryPlatform && String(job.platform || "").toLowerCase() !== state.libraryPlatform) return false;
    if (state.libraryAuthor && (job.author_name || "Unknown") !== state.libraryAuthor) return false;
    if (state.libraryType && mediaType(job) !== state.libraryType) return false;
    return jobMatchesSearch(job, state.librarySearch);
  });
  return items.sort((left, right) => {
    if (state.librarySort === "publish_desc") {
      return (publishTimestampValue(right) - publishTimestampValue(left))
        || (timestampValue(right.finished_at || right.created_at) - timestampValue(left.finished_at || left.created_at));
    }
    if (state.librarySort === "oldest") {
      return timestampValue(left.finished_at || left.created_at) - timestampValue(right.finished_at || right.created_at);
    }
    if (state.librarySort === "size_desc") {
      return Number(right.size_bytes || 0) - Number(left.size_bytes || 0);
    }
    if (state.librarySort === "size_asc") {
      return Number(left.size_bytes || 0) - Number(right.size_bytes || 0);
    }
    if (state.librarySort === "title") {
      const leftTitle = left.title || left.description || left.video_id || "";
      const rightTitle = right.title || right.description || right.video_id || "";
      return leftTitle.localeCompare(rightTitle, "zh-CN");
    }
    return timestampValue(right.finished_at || right.created_at) - timestampValue(left.finished_at || left.created_at);
  });
}

function previewFor(job, className = "preview") {
  const source = mediaPreviewSource(job);
  return source
    ? `<img class="${className}" src="${escapeHtml(source)}" alt="" loading="lazy">`
    : `<div class="${className} placeholder"></div>`;
}

function renderJobList(target, jobs, compact = false) {
  if (!jobs.length) {
    target.innerHTML = `<div class="empty">暂无任务</div>`;
    return;
  }
  target.classList.toggle("compact", compact);
  target.innerHTML = jobs.map((job) => {
    const title = job.title || job.description || job.url;
    const isRunning = runningStatuses.has(job.status);
    const canDownload = job.status === "finished" && job.file_path;
    const actions = [];
    if (canDownload) {
      actions.push(`<a href="${mediaUrl(job, "file")}"><button type="button">打开</button></a>`);
      actions.push(`<button class="secondary" type="button" data-force="${job.id}">重下</button>`);
    }
    if (job.status === "failed" || job.status === "cancelled") {
      actions.push(`<button class="secondary" type="button" data-retry="${job.id}">重试</button>`);
    }
    if (isRunning && job.status !== "cancelling") {
      actions.push(`<button class="danger" type="button" data-cancel="${job.id}">取消</button>`);
    }
    if (!isRunning) {
      actions.push(`<button class="danger" type="button" data-delete="${job.id}">删记录</button>`);
    }
    return `
      <article class="job" data-job-id="${job.id}">
        <input class="job-select" type="checkbox" data-select="${job.id}" ${state.selectedJobIds.has(String(job.id)) ? "checked" : ""} />
        ${previewFor(job)}
        <div class="meta">
          <div class="title">${escapeHtml(title)}</div>
          <div class="task-meta-line">${platformBadge(job)}<span>${escapeHtml(mediaTypeLabel(job))}</span><span>${escapeHtml(job.author_name || "Unknown")}</span><span>${escapeHtml(job.resolution || "-")}</span><span>${fmtBytes(job.size_bytes || 0)}</span></div>
          <div>
            <span class="pill ${job.status}">${escapeHtml(statusLabel(job.status))}</span>
            <span class="sub">${escapeHtml(job.message || "")}</span>
          </div>
          <div class="progress"><div class="bar" style="width:${Math.max(0, Math.min(100, job.progress || 0))}%"></div></div>
          ${job.error ? `<div class="sub error-text">${escapeHtml(friendlyError(job.error, job.platform))}</div>` : ""}
        </div>
        <div class="actions">${actions.join("")}</div>
      </article>
    `;
  }).join("");
}

function renderBulkActions() {
  const visibleIds = new Set(filteredTasks().map((job) => String(job.id)));
  for (const id of Array.from(state.selectedJobIds)) {
    if (!visibleIds.has(String(id))) state.selectedJobIds.delete(id);
  }
  const count = state.selectedJobIds.size;
  bulkActionsEl.hidden = count === 0;
  bulkCountEl.textContent = `已选择 ${count} 个任务`;
  if (tasksClearSelectionButton) {
    tasksClearSelectionButton.disabled = count === 0;
  }
}

function visibleTaskIds() {
  return filteredTasks().map((job) => String(job.id));
}

function selectVisibleTasks() {
  for (const id of visibleTaskIds()) {
    state.selectedJobIds.add(id);
  }
  renderAll();
}

function invertVisibleTasks() {
  for (const id of visibleTaskIds()) {
    if (state.selectedJobIds.has(id)) state.selectedJobIds.delete(id);
    else state.selectedJobIds.add(id);
  }
  renderAll();
}

function clearTaskSelection() {
  state.selectedJobIds.clear();
  renderAll();
}

function pageItems(items, page, pageSize) {
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const currentPage = Math.max(1, Math.min(totalPages, page));
  const start = (currentPage - 1) * pageSize;
  return {
    currentPage,
    totalPages,
    items: items.slice(start, start + pageSize),
  };
}

function renderPagination(target, kind, currentPage, totalPages, total) {
  if (!total) {
    target.innerHTML = "";
    return;
  }
  target.innerHTML = `
    <span>第 ${currentPage} / ${totalPages} 页，共 ${total} 项</span>
    <div>
      <button class="secondary" type="button" data-library-page="${kind}" data-page-delta="-1" ${currentPage <= 1 ? "disabled" : ""}>上一页</button>
      <button class="secondary" type="button" data-library-page="${kind}" data-page-delta="1" ${currentPage >= totalPages ? "disabled" : ""}>下一页</button>
    </div>
  `;
}

function filteredAuthors() {
  const query = state.libraryMode === "authors" ? state.librarySearch.toLowerCase() : "";
  return state.authors.filter((item) => {
    if (!query) return true;
    return String(item.author || "Unknown").toLowerCase().includes(query);
  });
}

function authorInitial(author) {
  return Array.from(String(author || "?").trim())[0] || "?";
}

function authorAvatar(item, className = "author-avatar") {
  const source = item ? (assetUrl(item.avatar_path) || item.avatar_url) : "";
  if (source) {
    return `<img class="${className}" src="${escapeHtml(source)}" alt="" loading="lazy">`;
  }
  return `<div class="${className} fallback">${escapeHtml(authorInitial(item && item.author))}</div>`;
}

function authorSyncText(item) {
  if (!item || !item.last_sync_at) return "最近同步：未同步";
  const status = crawlStatusLabel(item.last_sync_status);
  return `最近同步：${fmtDate(item.last_sync_at)} / ${status} / 新增 ${Number(item.last_sync_created_count || 0)}`;
}

function clearLibrarySelection() {
  state.selectedLibraryAuthors.clear();
  state.selectedLibraryJobIds.clear();
}

function visibleLibraryKeys() {
  if (state.libraryMode === "authors") {
    return state.libraryAuthors.map((item) => item.author || "Unknown");
  }
  if (state.libraryMode === "records") {
    return state.libraryRecords.map((item) => String(item.id));
  }
  return state.libraryMediaJobs.map((job) => String(job.id));
}

function selectedLibrarySet() {
  return state.libraryMode === "authors" ? state.selectedLibraryAuthors : state.selectedLibraryJobIds;
}

function selectedLibraryCount() {
  return selectedLibrarySet().size;
}

function toggleLibraryEditMode() {
  state.libraryEditMode = !state.libraryEditMode;
  if (!state.libraryEditMode) clearLibrarySelection();
  renderLibrary();
}

function toggleLibrarySelection(key, checked) {
  if (!key) return;
  const selected = selectedLibrarySet();
  const value = String(key);
  if (checked === undefined) {
    if (selected.has(value)) selected.delete(value);
    else selected.add(value);
  } else if (checked) {
    selected.add(value);
  } else {
    selected.delete(value);
  }
  renderLibrary();
}

function selectVisibleLibraryItems() {
  const selected = selectedLibrarySet();
  for (const key of visibleLibraryKeys()) selected.add(String(key));
  renderLibrary();
}

function invertVisibleLibraryItems() {
  const selected = selectedLibrarySet();
  for (const key of visibleLibraryKeys()) {
    const value = String(key);
    if (selected.has(value)) selected.delete(value);
    else selected.add(value);
  }
  renderLibrary();
}

function renderLibraryManageActions() {
  const editing = state.libraryEditMode;
  const recordMode = state.libraryMode === "records";
  const count = selectedLibraryCount();
  libraryEditToggleButton.hidden = false;
  librarySelectPageButton.hidden = !editing;
  libraryInvertPageButton.hidden = !editing;
  libraryDeleteSelectedButton.hidden = !editing;
  libraryEditToggleButton.textContent = editing ? "退出管理" : "管理";
  libraryDeleteSelectedButton.disabled = count === 0;
  if (recordMode && state.libraryRecordsKind === "deleted") {
    libraryDeleteSelectedButton.textContent = count ? `恢复所选 ${count}` : "恢复所选";
    libraryDeleteSelectedButton.classList.remove("danger");
    libraryDeleteSelectedButton.classList.add("secondary");
  } else {
    libraryDeleteSelectedButton.textContent = count ? `删除所选 ${count}` : "删除所选";
    libraryDeleteSelectedButton.classList.add("danger");
    libraryDeleteSelectedButton.classList.remove("secondary");
  }
}

function renderLibraryPlatformTabs() {
  libraryPlatformTabsEl.querySelectorAll("[data-library-platform]").forEach((button) => {
    button.classList.toggle("active", (button.dataset.libraryPlatform || "") === state.libraryPlatform);
  });
}

function renderLibraryOverview() {
  if (!libraryOverviewEl) return;
  const platformText = state.libraryPlatform ? platformLabel(state.libraryPlatform) : "全部平台";
  const modeText = {
    authors: "作者",
    media: "作品",
    records: state.libraryRecordsKind === "deleted" ? "已删除记录" : "媒体记录",
  }[state.libraryMode] || "媒体库";
  const total = state.libraryMode === "authors"
    ? state.libraryAuthorsTotal
    : state.libraryMode === "media"
      ? state.libraryMediaTotal
      : state.libraryRecordsTotal;
  const selected = selectedLibraryCount();
  const filterText = state.libraryAuthor ? `作者：${state.libraryAuthor}` : (state.librarySearch ? `搜索：${state.librarySearch}` : "全部内容");
  libraryOverviewEl.innerHTML = `
    <div><span>范围</span><strong>${escapeHtml(platformText)} / ${escapeHtml(modeText)}</strong></div>
    <div><span>总量</span><strong>${Number(total || 0)}</strong></div>
    <div><span>筛选</span><strong>${escapeHtml(filterText)}</strong></div>
    <div><span>已选</span><strong>${Number(selected || 0)}</strong></div>
  `;
}

function showLibraryLoading(kind) {
  document.querySelectorAll(`[data-library-page="${kind}"]`).forEach((button) => {
    button.disabled = true;
  });
  if (kind === "authors") {
    libraryAuthorsEl.innerHTML = `<div class="empty library-loading">加载作者中</div>`;
    libraryAuthorsPaginationEl.innerHTML = "";
    return;
  }
  if (kind === "records") {
    libraryRecordsEl.innerHTML = `<tr><td><div class="empty library-loading">加载记录中</div></td></tr>`;
    libraryRecordsPaginationEl.innerHTML = "";
    return;
  }
  setLibraryMediaBusy(true);
  if (!libraryMediaEl.querySelector(".media-page")) {
    libraryMediaEl.innerHTML = `<div class="empty library-loading">加载作品中</div>`;
    libraryMediaPaginationEl.innerHTML = "";
  }
}

function openAuthorMedia(author, type = "") {
  const name = String(author || "").trim();
  if (!name) return;
  state.libraryAuthor = name;
  state.libraryType = type || "";
  setLibraryMode("media");
  state.librarySort = "publish_desc";
  state.libraryMediaPage = 1;
  closeMediaPreviewOnly();
  clearLibraryMediaCache();
  showLibraryLoading("media");
  loadLibraryPage();
}

function renderAuthors() {
  const chips = [`<button class="chip ${state.authorFilter ? "" : "active"}" type="button" data-author="">全部</button>`];
  const visibleAuthors = state.authors.slice(0, 12);
  for (const item of visibleAuthors) {
    const author = item.author || "Unknown";
    chips.push(`
      <button class="chip ${state.authorFilter === author ? "active" : ""}" type="button" data-author="${escapeHtml(author)}">
        <span>${escapeHtml(author)}</span>
        <strong>${item.total || 0}</strong>
      </button>
    `);
  }
  if (state.authors.length > visibleAuthors.length) {
    chips.push(`<button class="chip chip-more" type="button" data-dashboard-authors-more>更多作者 ${state.authors.length - visibleAuthors.length}</button>`);
  }
  authorsEl.innerHTML = chips.join("");
}

function renderLibraryAuthors() {
  const authors = state.libraryAuthors;
  libraryAuthorsEl.innerHTML = authors.length ? authors.map((item) => {
    const author = item.author || "Unknown";
    const selected = state.selectedLibraryAuthors.has(author);
    return `
      <article class="author-card ${state.libraryAuthor === author ? "active" : ""} ${selected ? "selected" : ""}">
        ${state.libraryEditMode ? `
          <label class="library-card-check" title="选择作者">
            <input type="checkbox" data-library-author-select="${escapeHtml(author)}" ${selected ? "checked" : ""}>
          </label>
        ` : ""}
        <button class="author-card-main" type="button" data-library-author="${escapeHtml(author)}">
          ${authorAvatar(item)}
          <strong>${escapeHtml(author)}</strong>
          <span>${item.finished || 0} 完成 / ${fmtBytes(item.bytes || 0)}</span>
          <span>最近：${escapeHtml(fmtDate(item.latest_finished_at || item.latest_created_at))}</span>
          <span>${escapeHtml(authorSyncText(item))}</span>
        </button>
        ${state.libraryEditMode ? "" : `
          <div class="author-card-actions">
            <button class="secondary" type="button" data-library-author="${escapeHtml(author)}">查看作品</button>
          </div>
        `}
      </article>
    `;
  }).join("") : `<div class="empty">暂无作者</div>`;
  renderPagination(libraryAuthorsPaginationEl, "authors", state.libraryAuthorsPage, state.libraryAuthorsTotalPages, state.libraryAuthorsTotal);
}

function renderLibraryAuthorDetail() {
  if (!state.libraryAuthor) {
    libraryAuthorDetailEl.hidden = true;
    libraryAuthorDetailEl.innerHTML = "";
    return;
  }
  const author = state.libraryAuthor;
  const detail = state.libraryAuthorDetail || {};
  const secUid = String(detail.sec_uid || "").trim();
  const syncSource = detail.sync_source || null;
  const updateAction = secUid
    ? `<button class="secondary" type="button" data-author-crawl-sec-uid="${escapeHtml(secUid)}">增量更新作品</button>`
    : "";
  const syncSourceAction = syncSource
    ? `<button class="secondary" type="button" data-open-sync-source="${escapeHtml(syncSource.id)}">同步源：${syncSource.enabled ? "已启用" : "已停用"}</button>`
    : secUid
      ? `<button class="secondary" type="button" data-create-sync-source-author="${escapeHtml(author)}" data-create-sync-source-sec-uid="${escapeHtml(secUid)}">保存为同步源</button>`
      : "";
  const authorItem = { author, ...detail };
  libraryAuthorDetailEl.hidden = false;
  libraryAuthorDetailEl.innerHTML = `
    <div class="author-detail-identity">
      ${authorAvatar(authorItem, "author-avatar large")}
      <span>当前作者</span>
      <strong>${escapeHtml(author)}</strong>
    </div>
    <div class="author-detail-stats">
      <div><span>完成</span><strong>${detail.finished || 0}</strong></div>
      <div><span>视频</span><strong>${detail.videos || 0}</strong></div>
      <div><span>图集</span><strong>${detail.images || 0}</strong></div>
      <div><span>失败</span><strong>${detail.failed || 0}</strong></div>
      <div><span>占用</span><strong>${fmtBytes(detail.bytes || 0)}</strong></div>
      <div><span>最近</span><strong>${fmtDate(detail.latest_finished_at || detail.latest_created_at)}</strong></div>
    </div>
    <div class="author-detail-actions">
      ${updateAction}
      ${syncSourceAction}
      <button class="secondary" type="button" data-library-author-tasks="${escapeHtml(author)}">查看该作者任务</button>
      <button class="secondary" type="button" data-library-clear-author>返回全部作者</button>
    </div>
  `;
}

function renderRecordKindTabs() {
  if (!recordToolsEl) return;
  recordToolsEl.querySelectorAll("[data-record-kind]").forEach((button) => {
    button.classList.toggle("active", button.dataset.recordKind === state.libraryRecordsKind);
  });
  if (recordStatusFilter) {
    recordStatusFilter.hidden = state.libraryRecordsKind === "deleted";
    recordStatusFilter.value = state.recordStatus || "finished";
  }
  if (recordDateField) {
    recordDateField.hidden = state.libraryRecordsKind === "deleted";
    recordDateField.value = state.recordDateField || "download";
  }
  if (recordAuthorFilter) recordAuthorFilter.value = state.recordAuthor || "";
  if (recordDateFrom) recordDateFrom.value = state.recordDateFrom || "";
  if (recordDateTo) recordDateTo.value = state.recordDateTo || "";
  if (recordClearDeletedButton) {
    recordClearDeletedButton.hidden = state.libraryRecordsKind !== "deleted";
    recordClearDeletedButton.disabled = state.libraryRecordsKind !== "deleted" || !state.libraryRecordsTotal;
  }
}

function recordTitle(job) {
  return job.title || job.description || job.video_id || job.url || `#${job.id}`;
}

function renderMediaRecords() {
  libraryRecordsHeadEl.innerHTML = `
    <tr>
      ${state.libraryEditMode ? "<th>选择</th>" : ""}
      <th>作品</th>
      <th>平台</th>
      <th>作者</th>
      <th>清晰度</th>
      <th>大小</th>
      <th>发布时间</th>
      <th>下载时间</th>
      <th>操作</th>
    </tr>
  `;
  libraryRecordsEl.innerHTML = state.libraryRecords.length ? state.libraryRecords.map((job) => `
    <tr>
      ${state.libraryEditMode ? `
        <td>
          <label class="record-check" title="选择记录">
            <input type="checkbox" data-library-record-select="${job.id}" ${state.selectedLibraryJobIds.has(String(job.id)) ? "checked" : ""}>
          </label>
        </td>
      ` : ""}
      <td>
        <button class="record-title" type="button" data-record-preview="${job.id}">
          ${escapeHtml(recordTitle(job))}
        </button>
        <span>${escapeHtml(job.video_id || job.url || "-")}</span>
      </td>
      <td>${platformBadge(job) || "-"}</td>
      <td>${escapeHtml(job.author_name || "Unknown")}</td>
      <td>${escapeHtml(job.resolution || "-")}<span>${escapeHtml(job.codec || "")}</span></td>
      <td>${fmtBytes(job.size_bytes || 0)}</td>
      <td>${publishTimestampValue(job) ? escapeHtml(fmtEpoch(job.metadata.create_time)) : "-"}</td>
      <td>${escapeHtml(fmtDate(job.finished_at || job.created_at))}</td>
      <td>
        <div class="record-actions">
          <button class="secondary" type="button" data-open-detail="${job.id}">详情</button>
          <button class="danger" type="button" data-record-delete="${job.id}">删除</button>
        </div>
      </td>
    </tr>
  `).join("") : `<tr><td colspan="${state.libraryEditMode ? 9 : 8}"><div class="empty compact">暂无媒体记录</div></td></tr>`;
}

function renderDeletedRecords() {
  libraryRecordsHeadEl.innerHTML = `
    <tr>
      ${state.libraryEditMode ? "<th>选择</th>" : ""}
      <th>标题</th>
      <th>平台</th>
      <th>作者</th>
      <th>视频 ID</th>
      <th>原因</th>
      <th>删除时间</th>
      <th>来源</th>
      <th>操作</th>
    </tr>
  `;
  libraryRecordsEl.innerHTML = state.libraryRecords.length ? state.libraryRecords.map((item) => `
    <tr>
      ${state.libraryEditMode ? `
        <td>
          <label class="record-check" title="选择记录">
            <input type="checkbox" data-library-record-select="${item.id}" ${state.selectedLibraryJobIds.has(String(item.id)) ? "checked" : ""}>
          </label>
        </td>
      ` : ""}
      <td>
        <strong>${escapeHtml(item.title || item.url || "-")}</strong>
        <span>${escapeHtml(item.url || "")}</span>
      </td>
      <td>${escapeHtml(platformLabel(item.platform || ""))}</td>
      <td>${escapeHtml(item.author_name || "Unknown")}</td>
      <td>${escapeHtml(item.video_id || "-")}</td>
      <td>${escapeHtml(item.reason || "-")}</td>
      <td>${escapeHtml(fmtDate(item.deleted_at))}</td>
      <td>${item.source_job_id ? `#${escapeHtml(item.source_job_id)}` : "-"}</td>
      <td>
        <div class="record-actions">
          ${item.url ? `<button class="secondary" type="button" data-record-copy="${escapeHtml(item.url)}">复制链接</button>` : ""}
          ${item.video_id ? `<button class="secondary" type="button" data-record-copy="${escapeHtml(item.video_id)}">复制 ID</button>` : ""}
          <button class="secondary" type="button" data-record-restore="${item.id}">恢复同步</button>
        </div>
      </td>
    </tr>
  `).join("") : `<tr><td colspan="${state.libraryEditMode ? 9 : 8}"><div class="empty compact">暂无已删除记录</div></td></tr>`;
}

function renderLibraryRecords() {
  renderRecordKindTabs();
  if (state.libraryRecordsKind === "deleted") renderDeletedRecords();
  else renderMediaRecords();
  renderPagination(
    libraryRecordsPaginationEl,
    "records",
    state.libraryRecordsPage,
    state.libraryRecordsTotalPages,
    state.libraryRecordsTotal,
  );
}

function libraryMediaParams(page = state.libraryMediaPage) {
  const params = new URLSearchParams({
    page: String(Math.max(1, Number(page || 1))),
    page_size: String(libraryMediaPageSize),
    sort: state.librarySort || "publish_desc",
  });
  if (state.librarySearch) params.set("q", state.librarySearch);
  if (state.libraryPlatform) params.set("platform", state.libraryPlatform);
  if (state.libraryAuthor) params.set("author", state.libraryAuthor);
  if (state.libraryType) params.set("type", state.libraryType);
  return params;
}

function fetchLibraryAuthorDetail() {
  if (!state.libraryAuthor) return Promise.resolve(null);
  const params = new URLSearchParams();
  if (state.libraryPlatform) params.set("platform", state.libraryPlatform);
  return api(`/api/library/authors/${encodeURIComponent(state.libraryAuthor)}?${params.toString()}`);
}

function applyLibraryMediaResult(result, fallbackPage = state.libraryMediaPage) {
  state.libraryMediaJobs = result.items || [];
  state.libraryMediaPage = result.page || fallbackPage || 1;
  state.libraryMediaTotal = result.total || 0;
  state.libraryMediaTotalPages = result.total_pages || 1;
}

async function fetchLibraryMediaPage(page = state.libraryMediaPage, options = {}) {
  const params = libraryMediaParams(page);
  const key = params.toString();
  if (!options.force && state.libraryMediaCache.has(key)) {
    return state.libraryMediaCache.get(key);
  }
  if (!options.force && state.libraryMediaPending.has(key)) {
    return state.libraryMediaPending.get(key);
  }
  const request = api(`/api/library/jobs?${key}`).then((result) => {
    const pageData = {
      items: result.items || [],
      page: result.page || page || 1,
      total: result.total || 0,
      total_pages: result.total_pages || 1,
    };
    state.libraryMediaCache.set(key, pageData);
    state.libraryMediaPending.delete(key);
    return pageData;
  }).catch((error) => {
    state.libraryMediaPending.delete(key);
    throw error;
  });
  state.libraryMediaPending.set(key, request);
  return request;
}

function preloadLibraryMediaImages(items) {
  for (const job of (items || []).slice(0, libraryMediaPageSize)) {
    const source = mediaPreviewSource(job);
    if (!source) continue;
    const image = new Image();
    image.decoding = "async";
    image.src = source;
  }
}

function preloadLibraryMediaNeighbors() {
  if (!state.authenticated || state.libraryMode !== "media") return;
  const pages = [state.libraryMediaPage - 1, state.libraryMediaPage + 1]
    .filter((page) => page >= 1 && page <= state.libraryMediaTotalPages);
  for (const page of pages) {
    fetchLibraryMediaPage(page)
      .then((result) => preloadLibraryMediaImages(result.items || []))
      .catch(() => {});
  }
}

function clampLibraryMediaPage(page) {
  const requested = Number(page || 1);
  const maxPage = Math.max(1, state.libraryMediaTotalPages || requested || 1);
  return Math.max(1, Math.min(Number.isFinite(requested) ? requested : 1, maxPage));
}

function activeLibraryMediaPage() {
  return clampLibraryMediaPage(state.libraryMediaQueuedPage || state.libraryMediaTargetPage || state.libraryMediaPage);
}

function queueLibraryMediaPage(page, options = {}) {
  const requestedPage = clampLibraryMediaPage(page);
  const basePage = activeLibraryMediaPage();
  state.libraryMediaQueuedPage = requestedPage;
  state.libraryMediaQueuedDirection = options.direction ?? Math.sign(requestedPage - basePage);
  state.libraryMediaQueuedForce = state.libraryMediaQueuedForce || Boolean(options.force);
  setLibraryMediaBusy(false);
}

function setLibraryMediaBusy(busy) {
  const locked = Boolean(busy) && !state.libraryMediaTransitioning;
  const referencePage = activeLibraryMediaPage();
  libraryMediaPanel.classList.toggle("media-page-busy", Boolean(busy) && !state.libraryMediaTransitioning);
  document.querySelectorAll(`[data-library-page="media"]`).forEach((button) => {
    button.disabled = locked
      || !state.libraryMediaTotal
      || (Number(button.dataset.pageDelta || 0) < 0 && referencePage <= 1)
      || (Number(button.dataset.pageDelta || 0) > 0 && referencePage >= state.libraryMediaTotalPages);
  });
}

function renderLibraryMediaCards(media) {
  return media.length ? media.map((job) => {
    const selected = state.selectedLibraryJobIds.has(String(job.id));
    return `
      <article class="media-card ${mediaType(job)} ${selected ? "selected" : ""}" data-media-job="${job.id}">
        ${state.libraryEditMode ? `
          <label class="library-card-check" title="选择作品">
            <input type="checkbox" data-library-media-select="${job.id}" ${selected ? "checked" : ""}>
          </label>
        ` : ""}
        ${previewFor(job, "media-thumb")}
        <div class="media-body">
          <strong>${escapeHtml(job.title || job.description || job.video_id || job.url)}</strong>
          <span class="media-tag">${escapeHtml(mediaTypeLabel(job))}</span>
          <span class="sub">${escapeHtml(job.author_name || "Unknown")} / ${escapeHtml(job.resolution || "-")} / ${fmtBytes(job.size_bytes || 0)}</span>
          <span class="sub">${publishTimestampValue(job) ? `发布：${escapeHtml(fmtEpoch(job.metadata.create_time))}` : `下载：${escapeHtml(fmtDate(job.finished_at || job.created_at))}`}</span>
        </div>
      </article>
    `;
  }).join("") : `<div class="empty media-empty">暂无作品</div>`;
}

function renderLibraryMediaGrid(options = {}) {
  const media = libraryJobs();
  const cards = renderLibraryMediaCards(media);
  const direction = Number(options.direction || 0);
  libraryClearButton.hidden = !state.libraryAuthor;
  if (libraryPlayModeButton) {
    libraryPlayModeButton.disabled = !media.length;
  }
  renderPagination(libraryMediaPaginationEl, "media", state.libraryMediaPage, state.libraryMediaTotalPages, state.libraryMediaTotal);
  setLibraryMediaBusy(false);
  preloadLibraryMediaImages(media);

  const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const currentPage = libraryMediaEl.querySelector(".media-page");
  if (!direction || !currentPage || reducedMotion) {
    libraryMediaEl.innerHTML = `<div class="media-page">${cards}</div>`;
    return Promise.resolve();
  }

  libraryMediaEl.style.setProperty("--media-grid-height", `${Math.max(180, libraryMediaEl.offsetHeight)}px`);
  libraryMediaEl.classList.add("is-animating");
  currentPage.classList.add(direction > 0 ? "media-page-exit-left" : "media-page-exit-right");
  const nextPage = document.createElement("div");
  nextPage.className = `media-page ${direction > 0 ? "media-page-enter-right" : "media-page-enter-left"}`;
  nextPage.innerHTML = cards;
  libraryMediaEl.appendChild(nextPage);

  return new Promise((resolve) => {
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      currentPage.remove();
      nextPage.className = "media-page";
      libraryMediaEl.classList.remove("is-animating");
      libraryMediaEl.style.removeProperty("--media-grid-height");
      resolve();
    };
    nextPage.addEventListener("animationend", finish, { once: true });
    window.setTimeout(finish, 420);
  });
}

async function loadLibraryMediaPage(page = state.libraryMediaPage, options = {}) {
  if (!state.authenticated || state.libraryMode !== "media") return;
  const requestedPage = clampLibraryMediaPage(page);
  if (state.libraryMediaTransitioning) {
    queueLibraryMediaPage(requestedPage, options);
    return;
  }
  const previousPage = state.libraryMediaPage;
  const direction = options.direction ?? Math.sign(requestedPage - previousPage);
  const scrollX = window.scrollX;
  const scrollY = window.scrollY;
  if (requestedPage === previousPage && !options.force) {
    setLibraryMediaBusy(false);
    return;
  }
  state.libraryMediaTargetPage = requestedPage;
  state.libraryMediaQueuedPage = null;
  state.libraryMediaQueuedDirection = 0;
  state.libraryMediaQueuedForce = false;
  state.libraryMediaTransitioning = true;
  setLibraryMediaBusy(true);
  try {
    const [result, authorDetail] = await Promise.all([
      fetchLibraryMediaPage(requestedPage, { force: Boolean(options.force) }),
      fetchLibraryAuthorDetail(),
    ]);
    applyLibraryMediaResult(result, requestedPage);
    state.libraryAuthorDetail = authorDetail;
    renderLibraryOverview();
    renderLibraryManageActions();
    renderLibraryAuthorDetail();
    renderLibraryFilterLabel();
    await renderLibraryMediaGrid({ direction });
    preloadLibraryMediaNeighbors();
    requestAnimationFrame(() => window.scrollTo(scrollX, scrollY));
  } catch (error) {
    summaryEl.textContent = error.message || "作品加载失败";
    setLibraryMediaBusy(false);
  } finally {
    state.libraryMediaTransitioning = false;
    const queuedPage = state.libraryMediaQueuedPage;
    const queuedDirection = state.libraryMediaQueuedDirection;
    const queuedForce = state.libraryMediaQueuedForce;
    state.libraryMediaTargetPage = null;
    state.libraryMediaQueuedPage = null;
    state.libraryMediaQueuedDirection = 0;
    state.libraryMediaQueuedForce = false;
    setLibraryMediaBusy(false);
    if (queuedPage && state.libraryMode === "media" && (queuedPage !== state.libraryMediaPage || queuedForce)) {
      window.setTimeout(() => {
        loadLibraryMediaPage(queuedPage, {
          direction: queuedDirection || Math.sign(queuedPage - state.libraryMediaPage),
          force: queuedForce,
        });
      }, 0);
    }
  }
}

function renderLibraryFilterLabel() {
  const platformText = state.libraryPlatform ? platformLabel(state.libraryPlatform) : "全部平台";
  const typeText = state.libraryType ? (state.libraryType === "image" ? "图集" : "视频") : "全部类型";
  libraryFilterLabel.textContent = state.libraryAuthor ? `${platformText} / ${state.libraryAuthor} / ${typeText}` : `${platformText} / ${typeText}`;
}

function reloadLibraryMediaPage(options = {}) {
  clearLibraryMediaCache();
  if (state.libraryMode !== "media") {
    return loadLibraryPage();
  }
  if (state.libraryMediaTransitioning) {
    window.setTimeout(() => reloadLibraryMediaPage(options), 260);
    return Promise.resolve();
  }
  return loadLibraryMediaPage(state.libraryMediaPage, {
    force: true,
    direction: options.direction ?? 0,
  });
}

function renderLibrary(options = {}) {
  const showingAuthors = state.libraryMode === "authors";
  const showingMedia = state.libraryMode === "media";
  const showingRecords = state.libraryMode === "records";
  const platformText = state.libraryPlatform ? platformLabel(state.libraryPlatform) : "全部平台";
  renderViewHeader();
  renderLibraryPlatformTabs();
  renderLibraryManageActions();
  renderLibraryOverview();
  libraryAuthorsEl.classList.toggle("library-editing", state.libraryEditMode);
  libraryMediaEl.classList.toggle("library-editing", state.libraryEditMode);
  librarySectionKicker.textContent = showingAuthors
    ? `${platformText} / 作者分组`
    : showingMedia
      ? `${platformText} / 作品浏览`
      : `${platformText} / 记录管理`;
  librarySectionTitle.textContent = showingAuthors ? "作者" : showingMedia ? "作品" : "记录";
  libraryAuthorsPanel.hidden = !showingAuthors;
  libraryMediaPanel.hidden = !showingMedia;
  libraryRecordsPanel.hidden = !showingRecords;
  libraryTypeFilter.hidden = showingAuthors || (showingRecords && state.libraryRecordsKind === "deleted");
  librarySort.hidden = showingAuthors || (showingRecords && state.libraryRecordsKind === "deleted");
  libraryTypeFilter.value = state.libraryType || "";
  librarySort.value = state.librarySort || "publish_desc";
  librarySearchInput.placeholder = showingAuthors
    ? "搜索作者"
    : showingRecords && state.libraryRecordsKind === "deleted"
      ? "搜索已删除标题、作者、视频 ID"
      : "搜索标题、作者或视频 ID";
  document.querySelectorAll("[data-library-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.libraryMode === state.libraryMode);
  });
  renderLibraryAuthors();
  renderLibraryAuthorDetail();
  renderLibraryRecords();
  const typeText = state.libraryType ? (state.libraryType === "image" ? "图集" : "视频") : "全部类型";
  libraryFilterLabel.textContent = state.libraryAuthor ? `${platformText} / ${state.libraryAuthor} / ${typeText}` : `${platformText} / ${typeText}`;
  if (showingMedia && !options.skipMediaGrid) {
    renderLibraryMediaGrid();
    preloadLibraryMediaNeighbors();
  }
}

function syncMaxItems() {
  return persistAuthorMaxItems(syncMaxItemsInput.value, true);
}

function syncPageSize() {
  const parsed = Number(state.syncPageSize || syncPageSizeSelect?.value || 12);
  return [12, 24, 48].includes(parsed) ? parsed : 12;
}

function enabledSyncSources() {
  return (state.syncSources || []).filter((item) => item.enabled);
}

function visibleSyncSourceIds() {
  return (state.syncSources || []).map((item) => String(item.id));
}

function cleanupSyncSelection() {
  const visible = new Set(visibleSyncSourceIds());
  for (const id of Array.from(state.selectedSyncSourceIds)) {
    if (!visible.has(String(id))) state.selectedSyncSourceIds.delete(id);
  }
}

function toggleSyncSourceSelection(id, checked) {
  const value = String(id || "");
  if (!value) return;
  if (checked === undefined) {
    if (state.selectedSyncSourceIds.has(value)) state.selectedSyncSourceIds.delete(value);
    else state.selectedSyncSourceIds.add(value);
  } else if (checked) {
    state.selectedSyncSourceIds.add(value);
  } else {
    state.selectedSyncSourceIds.delete(value);
  }
  renderSync();
}

function renderSyncBulkActions() {
  if (!syncBulkActionsEl) return;
  cleanupSyncSelection();
  const count = state.selectedSyncSourceIds.size;
  syncBulkCountEl.textContent = `已选择 ${count} 个作者`;
  if (syncSelectPageButton) syncSelectPageButton.disabled = visibleSyncSourceIds().length === 0;
  if (syncInvertPageButton) syncInvertPageButton.disabled = visibleSyncSourceIds().length === 0;
  if (syncClearSelectionButton) syncClearSelectionButton.disabled = count === 0;
  [
    syncApplyDefaultsButton,
    syncEnableSelectedButton,
    syncDisableSelectedButton,
    syncRunSelectedButton,
    syncRunSelectedFullButton,
    syncDeleteSelectedButton,
  ].forEach((button) => {
    if (button) button.disabled = count === 0;
  });
}

function renderSyncOverview() {
  const enabled = enabledSyncSources().length;
  const stats = state.syncSourceStats || {};
  const filterLabel = {
    enabled: "启用",
    disabled: "停用",
  }[state.syncEnabledFilter] || "全部";
  const activeCrawls = (state.authorCrawls || []).filter((job) => (
    ["queued", "running", "pausing", "cancelling", "paused"].includes(job.status)
  )).length;
  syncOverviewEl.innerHTML = `
    <div class="sync-stat"><span>${escapeHtml(filterLabel)}同步源</span><strong>${state.syncSourcesTotal || 0}</strong></div>
    <div class="sync-stat"><span>全局启用 / 停用</span><strong>${Number(stats.enabled || enabled)} / ${Number(stats.disabled || 0)}</strong></div>
    <div class="sync-stat"><span>批量最多作品</span><strong>${syncMaxItems()}</strong></div>
    <div class="sync-stat"><span>队列 / 缺主页 ID</span><strong>${activeCrawls} / ${Number(stats.missing_identity || 0)}</strong></div>
  `;
}

function renderSyncAuthors() {
  const sources = state.syncSources || [];
  syncAuthorsEl.innerHTML = sources.length ? sources.map((item) => {
    const author = item.author_name || item.sec_uid || "Unknown";
    const secUid = String(item.sec_uid || "").trim();
    const canSync = Boolean(secUid);
    const status = item.last_sync_status ? crawlStatusLabel(item.last_sync_status) : "未同步";
    const mode = item.sync_mode === "full" ? "full" : "incremental";
    const selected = state.selectedSyncSourceIds.has(String(item.id));
    const issueBadges = [];
    if (!item.enabled) issueBadges.push("已停用");
    if (!canSync) issueBadges.push("缺主页 ID");
    if (["failed", "cancelled"].includes(String(item.last_sync_status || ""))) issueBadges.push(status);
    return `
      <article class="sync-author-card ${item.enabled ? "" : "disabled"} ${selected ? "selected" : ""}">
        <label class="sync-source-check" title="选择作者">
          <input type="checkbox" data-sync-source-select="${item.id}" ${selected ? "checked" : ""}>
        </label>
        ${authorAvatar({ author, avatar_url: item.avatar_url, avatar_path: item.avatar_path })}
        <div class="sync-author-main">
          <strong>${escapeHtml(author)}</strong>
          ${issueBadges.length ? `<div class="sync-source-badges">${issueBadges.map((badge) => `<span>${escapeHtml(badge)}</span>`).join("")}</div>` : ""}
          <span>${platformLabel(item.platform)} / ${item.media_finished || 0} 个作品 / ${fmtBytes(item.media_bytes || 0)}</span>
          <span>图集：${item.include_images ? "下载" : "跳过"}</span>
          <span>最近同步：${escapeHtml(fmtDate(item.last_sync_at || item.last_finished_at))} / ${escapeHtml(status)} / 新增 ${Number(item.last_created_count || 0)}</span>
          ${item.last_sync_message ? `<span>结果：${escapeHtml(item.last_sync_message)}</span>` : ""}
          ${item.last_stop_reason ? `<span>停止原因：${escapeHtml(syncStopReasonLabel(item.last_stop_reason))}${item.last_has_more ? " / 还有更多" : ""}</span>` : ""}
          <span class="${canSync ? "sync-ready" : "sync-missing"}">${canSync ? `主页 ID：${escapeHtml(secUid)}` : "缺少作者主页 ID"}</span>
          <div class="sync-source-fields">
            <label>
              <span>模式</span>
              <select data-sync-source-field="sync_mode" data-sync-source-id="${item.id}">
                <option value="incremental" ${mode === "incremental" ? "selected" : ""}>增量</option>
                <option value="full" ${mode === "full" ? "selected" : ""}>全量</option>
              </select>
            </label>
            <label>
              <span>最多作品</span>
              <input type="number" min="1" max="1000" step="1" value="${Number(item.max_items || 200)}" data-sync-source-field="max_items" data-sync-source-id="${item.id}">
            </label>
            <label>
              <span>旧页停止</span>
              <input type="number" min="1" max="20" step="1" value="${Number(item.stop_after_existing_pages || 2)}" data-sync-source-field="stop_after_existing_pages" data-sync-source-id="${item.id}">
            </label>
            <label class="sync-source-toggle-field">
              <span>下载图集</span>
              <input type="checkbox" data-sync-source-field="include_images" data-sync-source-id="${item.id}" ${item.include_images ? "checked" : ""}>
            </label>
          </div>
        </div>
        <div class="sync-author-actions">
          <button class="secondary" type="button" data-sync-source-detail="${item.id}">详情</button>
          <button class="secondary" type="button" data-sync-author="${escapeHtml(author)}">查看作品</button>
          <button class="secondary" type="button" data-sync-source-toggle="${item.id}">${item.enabled ? "停用" : "启用"}</button>
          <button class="secondary" type="button" data-sync-source-run="${item.id}" data-sync-source-mode="incremental" ${canSync && item.enabled ? "" : "disabled"}>增量</button>
          <button type="button" data-sync-source-run="${item.id}" data-sync-source-mode="full" ${canSync && item.enabled ? "" : "disabled"}>全量</button>
          <button class="danger" type="button" data-sync-source-delete="${item.id}">删除源</button>
        </div>
      </article>
    `;
  }).join("") : `<div class="empty">暂无同步源。可以添加作者主页，或从媒体库导入已有作者。</div>`;
  renderPagination(syncAuthorsPaginationEl, "sync-authors", state.syncAuthorsPage, state.syncSourcesTotalPages, state.syncSourcesTotal);
}

function syncStopReasonLabel(value) {
  return {
    incremental_known_cutoff: "增量命中本地库",
    max_pages_reached: "达到最大页数",
    max_items_reached: "达到最多作品数",
    source_exhausted: "作者主页已扫完",
    finished: "正常完成",
    error: "执行失败",
  }[String(value || "")] || "未记录";
}

function renderSyncDetail() {
  if (!syncDetailEl) return;
  const detail = state.syncDetail;
  if (!detail || !detail.source) {
    syncDetailEl.hidden = true;
    syncDetailEl.parentElement?.classList.remove("has-detail");
    syncDetailEl.innerHTML = "";
    return;
  }
  const source = detail.source || {};
  const summary = detail.summary || {};
  const history = Array.isArray(detail.history) ? detail.history : [];
  const author = source.author_name || source.sec_uid || "Unknown";
  syncDetailEl.hidden = false;
  syncDetailEl.parentElement?.classList.add("has-detail");
  syncDetailEl.innerHTML = `
    <header class="sync-detail-head">
      <div>
        <p>同步源详情</p>
        <h3>${escapeHtml(author)}</h3>
      </div>
      <button class="secondary" type="button" data-sync-detail-close>关闭</button>
    </header>
    <div class="sync-detail-metrics">
      <div><span>历史</span><strong>${Number(summary.history_count || 0)}</strong></div>
      <div><span>成功</span><strong>${Number(summary.finished_count || 0)}</strong></div>
      <div><span>失败</span><strong>${Number(summary.failed_count || 0)}</strong></div>
      <div><span>最近停止</span><strong>${escapeHtml(syncStopReasonLabel(summary.latest_stop_reason))}</strong></div>
    </div>
    <div class="sync-detail-info">
      <span>${escapeHtml(platformLabel(source.platform))} / ${source.enabled ? "已启用" : "已停用"} / ${escapeHtml(source.sync_mode === "full" ? "全量" : "增量")}</span>
      <span>最多 ${Number(source.max_items || 0)} 个 / 最多 ${Number(source.max_pages || 0)} 页 / 旧页停止 ${Number(source.stop_after_existing_pages || 0)} 页</span>
      <span>主页 ID：${escapeHtml(source.sec_uid || "-")}</span>
      ${summary.latest_has_more ? `<span class="sync-has-more">最近一次还有更多作品，可用任务里的续抓继续扫。</span>` : ""}
    </div>
    <section class="sync-history-list">
      ${history.length ? history.map((job) => `
        <article class="sync-history-item ${escapeHtml(job.status || "")}">
          <div>
            <strong>#${job.id} / ${escapeHtml(crawlStatusLabel(job.status))} / ${escapeHtml(job.sync_mode === "incremental" ? "增量" : "全量")}</strong>
            <span>${escapeHtml(fmtDate(job.finished_at || job.updated_at || job.created_at))}</span>
          </div>
          <div class="sync-history-counts">
            <span>发现 ${Number(job.found_count || 0)}</span>
            <span>新增 ${Number(job.created_count || 0)}</span>
            <span>已存在 ${Number(job.reused_count || 0)}</span>
            <span>页 ${Number(job.pages_scanned || 0)}</span>
          </div>
          <p>${escapeHtml(job.message || "")}</p>
          <span class="sync-history-reason">${escapeHtml(syncStopReasonLabel(job.stop_reason))}${job.has_more ? " / 还有更多" : ""}</span>
          ${job.error ? `<em>${escapeHtml(friendlyError(job.error, source.platform))}</em>` : ""}
        </article>
      `).join("") : `<div class="empty compact">暂无同步历史</div>`}
    </section>
  `;
}

function renderSync() {
  renderSyncOverview();
  renderSyncAuthors();
  renderSyncDetail();
  renderSyncBulkActions();
  const crawls = state.authorCrawls || [];
  syncCrawlJobsEl.innerHTML = authorCrawlJobsHtml(crawls.slice(0, 20));
  if (crawls.length > 20) {
    syncCrawlJobsEl.insertAdjacentHTML(
      "beforeend",
      `<div class="sync-more-note">仅显示最近 20 条同步任务，完整记录请到任务页查看。</div>`,
    );
  }
  if (syncRunEnabledButton) {
    syncRunEnabledButton.disabled = enabledSyncSources().length === 0;
  }
}

function platformLabel(value) {
  const platform = String(value || "").toLowerCase();
  if (!platform) return "全部";
  if (platform === "douyin") return "抖音";
  if (platform === "tiktok") return "TikTok";
  if (platform === "unknown") return "未知";
  return value || "未知";
}

function renderTaskPlatformTabs() {
  taskPlatformTabsEl.querySelectorAll("[data-task-platform]").forEach((button) => {
    button.classList.toggle("active", (button.dataset.taskPlatform || "") === state.taskPlatform);
  });
}

function renderTaskSections() {
  renderTaskPlatformTabs();
  downloadTaskTitleEl.textContent = `${platformLabel(state.taskPlatform)}下载任务`;
  downloadTaskCountEl.textContent = `${state.tasksTotal || 0} 个任务`;
  authorCrawlTaskCountEl.textContent = `${(state.authorCrawls || []).length} 个任务`;
  taskAuthorCrawlsEl.innerHTML = authorCrawlJobsHtml(state.authorCrawls || []);
}

function renderLogTypeOptions() {
  if (!logsTypeFilter) return;
  const current = state.logsType || "";
  const types = Array.isArray(state.logsEventTypes) ? state.logsEventTypes : [];
  logsTypeFilter.innerHTML = `
    <option value="">全部事件</option>
    ${types.map((item) => {
      const value = String(item.event_type || "");
      return `<option value="${escapeHtml(value)}" ${value === current ? "selected" : ""}>${escapeHtml(eventLabel(value))} (${Number(item.count || 0)})</option>`;
    }).join("")}
  `;
}

function groupLogEvents(rows) {
  const groups = new Map();
  for (const event of rows) {
    const key = event.job_id ? `job:${event.job_id}` : `event:${event.id || event.created_at || groups.size}`;
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        jobId: event.job_id || "",
        title: event.title || event.description || event.url || `任务 #${event.job_id || "-"}`,
        author: event.author_name || "Unknown",
        platform: event.platform || "",
        status: event.job_status || "",
        latestAt: event.created_at || "",
        events: [],
      });
    }
    const group = groups.get(key);
    group.events.push(event);
    if (!group.latestAt || timestampValue(event.created_at) > timestampValue(group.latestAt)) group.latestAt = event.created_at;
    if (event.job_status) group.status = event.job_status;
    if (event.title || event.description || event.url) group.title = event.title || event.description || event.url;
  }
  return Array.from(groups.values());
}

function compactEventMessage(event) {
  const message = String(event.message || "").trim();
  if (message) return message;
  const data = event.data && typeof event.data === "object" ? event.data : {};
  const summary = Object.entries(data)
    .slice(0, 3)
    .map(([key, value]) => `${key}=${eventValueText(key, value)}`)
    .filter(Boolean)
    .join(" / ");
  return summary || "-";
}

function renderLogGroup(group) {
  const visibleEvents = group.events.slice(0, 6);
  const hiddenCount = Math.max(0, group.events.length - visibleEvents.length);
  const meta = [
    group.jobId ? `#${group.jobId}` : "系统事件",
    platformLabel(group.platform || ""),
    statusLabel(group.status || ""),
    `${group.events.length} 条`,
    fmtDate(group.latestAt),
  ].filter((item) => item && item !== "-");
  return `
    <article class="log-task-card ${escapeHtml(group.status || "")}">
      <header class="log-task-head">
        <div>
          <strong>${escapeHtml(group.title)}</strong>
          <span>${escapeHtml(group.author || "Unknown")}</span>
        </div>
        <div class="log-task-actions">
          <span>${escapeHtml(meta.join(" / "))}</span>
          ${group.jobId ? `<button class="secondary" type="button" data-log-open-job="${group.jobId}">详情</button>` : ""}
        </div>
      </header>
      <div class="log-event-list">
        ${visibleEvents.map((event) => `
          <div class="log-event-row">
            <time>${escapeHtml(fmtDate(event.created_at))}</time>
            <span class="log-event-type">${escapeHtml(eventLabel(event.event_type))}</span>
            <p>${escapeHtml(compactEventMessage(event))}</p>
          </div>
        `).join("")}
        ${hiddenCount ? `<div class="log-event-more">还有 ${hiddenCount} 条步骤在当前筛选中已收拢</div>` : ""}
      </div>
    </article>
  `;
}

function renderLogs() {
  if (!logsEventsEl) return;
  renderLogTypeOptions();
  const rows = state.logs || [];
  const groups = groupLogEvents(rows);
  if (logsOverviewEl) logsOverviewEl.innerHTML = `
    <div><span>日志总量</span><strong>${Number(state.logsTotal || 0)}</strong></div>
    <div><span>当前页</span><strong>${groups.length} 组 / ${Number(rows.length || 0)} 条</strong></div>
    <div><span>事件类型</span><strong>${state.logsType ? eventLabel(state.logsType) : "全部"}</strong></div>
    <div><span>平台</span><strong>${state.logsPlatform ? platformLabel(state.logsPlatform) : "全部平台"}</strong></div>
  `;
  logsEventsEl.innerHTML = groups.length ? groups.map(renderLogGroup).join("") : `<div class="empty compact">暂无日志</div>`;
  renderPagination(logsPaginationEl, "logs", state.logsPage, state.logsTotalPages, state.logsTotal);
}

function renderAll(options = {}) {
  renderStats(state.stats || {});
  renderAuthors();
  renderAuthorCrawls();
  renderLibrary({ skipMediaGrid: Boolean(options.skipLibraryMediaGrid) });
  renderSync();
  renderTaskSections();
  if (state.currentView === "logs") renderLogs();
  renderBulkActions();
  renderJobList(jobsEl, filteredTasks());
  renderPagination(tasksPaginationEl, "tasks", state.tasksPage, state.tasksTotalPages, state.tasksTotal);
  renderJobList(activeJobsEl, state.activeJobs, true);
}

function qualitySubline(option) {
  const parts = [];
  if (option.data_size) parts.push(fmtBytes(option.data_size));
  if (option.bit_rate) parts.push(`${Math.round(option.bit_rate / 1000)} kbps`);
  if (option.value === "best") parts.push("自动选择最高候选");
  return parts.join(" / ") || "点击后加入下载队列";
}

function setSubmitBusy(busy, label = "添加") {
  submitButton.disabled = busy;
  submitButton.textContent = busy ? label : "添加";
}

function setAuthorCrawlBusy(busy) {
  authorCrawlButton.disabled = busy;
  authorCrawlButton.textContent = busy ? "抓取中" : "抓取并加入队列";
}

function authorCrawlMaxItems() {
  return persistAuthorMaxItems(authorCrawlMaxInput.value, true);
}

function renderAuthorCrawlCreated(result) {
  const job = result && result.job ? result.job : {};
  authorCrawlResultEl.hidden = false;
  const authorName = job.author_name ? ` / ${job.author_name}` : "";
  authorCrawlResultEl.innerHTML = `<p>${escapeHtml(result.message || "作者抓取任务已创建")} #${escapeHtml(job.id || "-")}${escapeHtml(authorName)}</p>`;
}

function renderAuthorCrawlResult(result) {
  const samples = [...(result.created || []), ...(result.preview || []), ...(result.reused || [])].slice(0, 5);
  authorCrawlResultEl.hidden = false;
  authorCrawlResultEl.innerHTML = `
    <div class="author-crawl-metrics">
      <span>发现 <strong>${Number(result.found_count || 0)}</strong></span>
      <span>新增 <strong>${Number(result.created_count || result.would_create_count || 0)}</strong></span>
      <span>已存在 <strong>${Number(result.reused_count || 0)}</strong></span>
      <span>页数 <strong>${Number(result.pages || 0)}</strong></span>
    </div>
    <p>${escapeHtml(result.message || "抓取完成")}</p>
    ${result.has_more ? `<p>还有更多作品未抓完，可以从任务卡片继续续抓。</p>` : ""}
    ${samples.length ? `
      <div class="author-crawl-samples">
        ${samples.map((item) => `<span>${escapeHtml(item.title || item.url || item.video_id || "-")}</span>`).join("")}
      </div>
    ` : ""}
  `;
}

function authorCrawlJobsHtml(crawls) {
  if (!crawls.length) {
    return `<div class="empty compact">暂无作者抓取任务</div>`;
  }
  return crawls.map((job) => {
    const running = ["running", "pausing", "cancelling"].includes(job.status);
    const canPause = ["queued", "running"].includes(job.status);
    const canResume = ["paused", "failed"].includes(job.status);
    const canCancel = ["queued", "running", "pausing", "paused", "failed"].includes(job.status);
    const canContinue = job.status === "finished" && Number(job.cursor || 0) > 0 && String(job.message || "").includes("更多");
    const authorName = String(job.author_name || "").trim();
    const modeLabel = job.sync_mode === "incremental" ? "增量" : "全量";
    const identity = authorName ? `作者：${authorName}` : `主页 ID：${job.sec_uid || job.url || "-"}`;
    const actions = [];
    if (canPause) actions.push(`<button class="secondary" type="button" data-author-crawl-action="pause" data-author-crawl-id="${job.id}">暂停</button>`);
    if (canResume) actions.push(`<button class="secondary" type="button" data-author-crawl-action="resume" data-author-crawl-id="${job.id}">继续</button>`);
    if (canContinue) actions.push(`<button class="secondary" type="button" data-author-crawl-action="continue" data-author-crawl-id="${job.id}">续抓</button>`);
    if (canCancel) actions.push(`<button class="danger" type="button" data-author-crawl-action="cancel" data-author-crawl-id="${job.id}">取消</button>`);
    return `
      <article class="author-crawl-job ${escapeHtml(job.status || "")}">
        <div>
          <strong>#${job.id} / ${escapeHtml(crawlStatusLabel(job.status))} / ${modeLabel}${authorName ? ` / ${escapeHtml(authorName)}` : ""}</strong>
          <span>${escapeHtml(identity)}</span>
          ${job.sec_uid && authorName ? `<span>主页 ID：${escapeHtml(job.sec_uid)}</span>` : ""}
          <span>发现 ${Number(job.found_count || 0)} / 新增 ${Number(job.created_count || 0)} / 已存在 ${Number(job.reused_count || 0)} / 页 ${Number(job.pages_scanned || 0)}</span>
          ${job.error ? `<span class="error-text">${escapeHtml(String(job.error).split("\n")[0])}</span>` : ""}
        </div>
        <div class="crawl-job-side">
          <div class="progress"><div class="bar" style="width:${Math.max(0, Math.min(100, job.progress || 0))}%"></div></div>
          <span>${escapeHtml(job.message || "")}</span>
          <div class="actions">${actions.join("")}</div>
        </div>
      </article>
    `;
  }).join("");
}

function authorCrawlDashboardHtml(crawls) {
  if (!crawls.length) {
    return `<div class="dashboard-crawl-empty">暂无作者抓取任务</div>`;
  }
  const rows = crawls.slice(0, 3).map((job) => {
    const authorName = String(job.author_name || "").trim();
    const label = authorName || `#${job.id}`;
    const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
    const progressLabel = `${Math.round(progress)}%`;
    return `
      <article class="crawl-strip-item ${escapeHtml(job.status || "")}">
        <div class="crawl-strip-copy">
          <strong>#${job.id} / ${escapeHtml(crawlStatusLabel(job.status))} / ${escapeHtml(label)}</strong>
          <span>
            发现 ${Number(job.found_count || 0)}
            <i>新增 ${Number(job.created_count || 0)}</i>
            <i>已有 ${Number(job.reused_count || 0)}</i>
            <i>页 ${Number(job.pages_scanned || 0)}</i>
          </span>
        </div>
        <div class="crawl-strip-progress">
          <div class="progress"><div class="bar" style="width:${progress}%"></div></div>
          <span>${escapeHtml(job.message || progressLabel)}</span>
        </div>
      </article>
    `;
  }).join("");
  const more = crawls.length > 3
    ? `<button class="secondary dashboard-crawl-more" type="button" data-dashboard-crawl-more>查看全部 ${crawls.length} 个</button>`
    : `<button class="secondary dashboard-crawl-more" type="button" data-dashboard-crawl-more>管理同步任务</button>`;
  return `<div class="dashboard-crawl-strip-inner">${rows}${more}</div>`;
}

function renderAuthorCrawls() {
  authorCrawlJobsEl.innerHTML = authorCrawlDashboardHtml(state.authorCrawls || []);
}

function setQualityBusy(busy) {
  qualityOptionsEl.querySelectorAll("button").forEach((button) => {
    button.disabled = busy;
  });
  qualityCloseButton.disabled = busy;
}

function renderQualityDialog(preview, action = { type: "create" }) {
  state.pendingQualityPreview = preview;
  state.pendingQualityAction = action;
  closeDetailOnly();
  qualityDialogEl.hidden = false;
  drawerScrimEl.hidden = false;
  qualityPlatformEl.textContent = `${preview.platform || "-"} / ${preview.video_id || "-"}`;
  qualityTitleEl.textContent = action.title || preview.title || "选择清晰度";
  qualityAuthorEl.textContent = preview.author_name || "Unknown";
  qualityVideoIdEl.textContent = preview.url || "";
  if (preview.cover_url) {
    qualityCoverEl.src = preview.cover_url;
    qualityCoverEl.hidden = false;
  } else {
    qualityCoverEl.removeAttribute("src");
    qualityCoverEl.hidden = true;
  }
  const options = preview.qualities && preview.qualities.length
    ? preview.qualities
    : [{ value: "best", label: "最高" }];
  qualityOptionsEl.innerHTML = options.map((option) => `
    <button class="quality-option" type="button" data-quality="${escapeHtml(option.value || "best")}">
      <strong>${escapeHtml(option.label || "最高")}</strong>
      <span>${escapeHtml(qualitySubline(option))}</span>
    </button>
  `).join("");
}

async function jobFromState(jobId) {
  const found = state.jobs.find((job) => String(job.id) === String(jobId))
    || state.activeJobs.find((job) => String(job.id) === String(jobId))
    || state.libraryMediaJobs.find((job) => String(job.id) === String(jobId));
  return found || api(`/api/jobs/${jobId}`);
}

async function openRetryQualityDialog(jobId, force) {
  const job = await jobFromState(jobId);
  if (force && !confirm("重新下载会删除当前文件，继续吗？")) return;
  summaryEl.textContent = force ? "解析重下清晰度中" : "解析重试清晰度中";
  const preview = await api("/api/parse-preview", {
    method: "POST",
    body: JSON.stringify({ url: job.url }),
  });
  renderQualityDialog(preview, {
    type: "retry",
    jobId: job.id,
    force,
    title: force ? "选择重下清晰度" : "选择重试清晰度",
  });
  summaryEl.textContent = "请选择清晰度";
}

function detailRow(label, value) {
  return `
    <div class="detail-row">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value || "-")}</strong>
    </div>
  `;
}

function candidateLabel(item) {
  const width = Number(item.width || 0);
  const height = Number(item.height || 0);
  const fps = Number(item.fps || 0);
  const codec = item.is_h265 ? "H.265" : "H.264";
  const parts = [];
  if (width && height) parts.push(`${width}x${height}`);
  if (fps) parts.push(`${fps}fps`);
  parts.push(codec);
  if (item.data_size) parts.push(fmtBytes(item.data_size));
  if (item.bit_rate) parts.push(`${Math.round(Number(item.bit_rate) / 1000)} kbps`);
  return parts.join(" / ");
}

function renderParseSummary(job) {
  const metadata = job.metadata || {};
  const videoData = metadata.video_data || {};
  const candidates = Array.isArray(videoData.bit_rate_candidates) ? videoData.bit_rate_candidates : [];
  const visible = candidates.slice(0, 6);
  const warning = metadata.parser_warning ? `<p>${escapeHtml(metadata.parser_warning)}</p>` : "";
  return `
    <section class="parse-summary">
      <div>
        <span>解析源</span>
        <strong>${escapeHtml(metadata.parser_source || "-")}</strong>
      </div>
      <div>
        <span>清晰度候选</span>
        <strong>${candidates.length}</strong>
      </div>
      <div>
        <span>当前下载</span>
        <strong>${escapeHtml(job.download_label || job.quality_preference || "-")}</strong>
      </div>
      ${warning}
      ${visible.length ? `
        <div class="parse-candidates">
          ${visible.map((item, index) => `<span>${index + 1}. ${escapeHtml(candidateLabel(item))}</span>`).join("")}
        </div>
      ` : ""}
    </section>
  `;
}

function refreshSummaryText(result) {
  const diagnostics = result && result.diagnostics ? result.diagnostics : {};
  const best = diagnostics.best_quality || {};
  const count = diagnostics.bit_rate_candidates || 0;
  const label = best.label || best.resolution || "-";
  return `解析已刷新：${count} 个候选，最高 ${label}`;
}

function limitedJson(value) {
  const text = JSON.stringify(value || {}, null, 2);
  if (text.length <= 12000) return text;
  return `${text.slice(0, 12000)}\n...`;
}

function eventLabel(type) {
  if (String(type || "").startsWith("status:")) return `状态：${statusLabel(String(type).slice(7))}`;
  return {
    created: "创建",
    retry: "重试",
    redownload: "重下",
    "parse:cache": "解析缓存",
    "parse:success": "解析结果",
    "parse:refresh": "刷新解析",
    "parse:refresh_failed": "刷新失败",
    "download:candidates": "下载候选",
    "download:attempt": "下载尝试",
    "download:success": "下载成功",
    "download:failed": "下载失败",
    auto_retry: "自动重试",
    cancel: "取消",
    cancelled: "已取消",
    duplicate: "重复复用",
  }[type] || type || "-";
}

function eventValueText(key, value) {
  if (value === null || value === undefined || value === "") return "";
  if (key === "bytes" || key === "size_bytes") return fmtBytes(value);
  if (Array.isArray(value)) {
    return value.map((item) => {
      if (!item || typeof item !== "object") return String(item);
      return Object.entries(item)
        .filter(([, nestedValue]) => nestedValue !== null && nestedValue !== undefined && nestedValue !== "")
        .map(([nestedKey, nestedValue]) => `${nestedKey}=${nestedValue}`)
        .join(", ");
    }).filter(Boolean).join("\n");
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function renderEventData(data) {
  const entries = Object.entries(data || {})
    .map(([key, value]) => [key, eventValueText(key, value)])
    .filter(([, value]) => value);
  if (!entries.length) return "";
  return `
    <div class="event-data">
      ${entries.map(([key, value]) => `
        <div class="event-data-row">
          <span>${escapeHtml(key)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function renderEvents(events) {
  if (!events || !events.length) return `<section class="timeline"><h2>记录</h2><div class="empty">暂无记录</div></section>`;
  return `
    <section class="timeline">
      <h2>记录</h2>
      ${events.map((event) => `
        <div class="event">
          <span>${escapeHtml(fmtDate(event.created_at))}</span>
          <strong>${escapeHtml(eventLabel(event.event_type))}</strong>
          <p>${escapeHtml(event.message || "")}</p>
          ${renderEventData(event.data)}
        </div>
      `).join("")}
    </section>
  `;
}

function mediaSourceFor(job) {
  const canDownload = job.status === "finished" && job.file_path;
  if (canDownload) return mediaUrl(job, "file");
  return assetUrl(job.cover_path) || job.cover_url || (job.preview_path ? mediaUrl(job, "preview") : "");
}

function renderMediaPreview(job) {
  const title = job.title || job.description || job.video_id || job.url || `#${job.id}`;
  const source = mediaSourceFor(job);
  const isVideo = String(job.file_path || "").toLowerCase().endsWith(".mp4");
  const authorName = String(job.author_name || "").trim();
  const canViewAuthor = authorName && authorName !== "Unknown";
  mediaPreviewTitleEl.textContent = title;
  mediaPreviewKickerEl.textContent = `${authorName || "Unknown"} / ${mediaTypeLabel(job)}`;
  const media = source
    ? isVideo
      ? `<video class="media-preview-player" controls preload="metadata" src="${source}"></video>`
      : `<img class="media-preview-image" src="${escapeHtml(source)}" alt="">`
    : `<div class="media-preview-empty">暂无预览</div>`;
  const canDownload = job.status === "finished" && job.file_path;
  const canReel = canDownload && isVideo;
  mediaPreviewBodyEl.innerHTML = `
    ${media}
    <div class="media-preview-meta">
      <span>${escapeHtml(job.resolution || "-")} / ${escapeHtml(job.codec || "-")}</span>
      <span>${fmtBytes(job.size_bytes || 0)} / ${escapeHtml(fmtDate(job.finished_at || job.created_at))}</span>
    </div>
    <div class="media-preview-actions">
      ${canReel ? `<button type="button" data-reel-start="${job.id}">从这里播放</button>` : ""}
      ${canDownload ? `<a href="${mediaUrl(job, "file")}"><button type="button">打开文件</button></a>` : ""}
      ${canViewAuthor ? `<button class="secondary" type="button" data-view-author-media="${escapeHtml(authorName)}" data-view-author-platform="${escapeHtml(job.platform || "")}">查看作者视频</button>` : ""}
      <button class="secondary" type="button" data-open-detail="${job.id}">详细信息</button>
    </div>
  `;
}

async function openMediaPreview(jobId) {
  const job = await jobFromState(jobId);
  closeDetailOnly();
  qualityDialogEl.hidden = true;
  mediaPreviewDialogEl.hidden = false;
  drawerScrimEl.hidden = false;
  renderMediaPreview(job);
}

function currentLibraryParams(pageSize = 100) {
  const params = new URLSearchParams({
    page: "1",
    page_size: String(pageSize),
    sort: state.librarySort || "publish_desc",
  });
  if (state.libraryPlatform) params.set("platform", state.libraryPlatform);
  if (state.librarySearch) params.set("q", state.librarySearch);
  if (state.libraryAuthor) params.set("author", state.libraryAuthor);
  if (state.libraryType) params.set("type", state.libraryType);
  return params;
}

function reelJobs() {
  return (state.reelJobs || []).filter((job) => mediaType(job) === "video" && job.status === "finished" && job.file_path);
}

function reelSource(job) {
  return job && job.file_path ? mediaUrl(job, "file") : "";
}

function resolutionDimensions(value) {
  const match = String(value || "").match(/(\d+)\s*x\s*(\d+)/i);
  if (!match) return [9, 16];
  const width = Number(match[1]);
  const height = Number(match[2]);
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return [9, 16];
  }
  return [width, height];
}

function fitReelStage(width = state.reelVideoWidth, height = state.reelVideoHeight) {
  if (!reelStageEl || reelViewerEl.hidden) return;
  const maxWidth = Math.max(280, window.innerWidth);
  const maxHeight = Math.max(320, window.innerHeight);
  let ratio = Number(width) / Number(height);
  if (!Number.isFinite(ratio) || ratio <= 0) ratio = 9 / 16;
  let targetWidth = maxWidth;
  let targetHeight = targetWidth / ratio;
  if (targetHeight > maxHeight) {
    targetHeight = maxHeight;
    targetWidth = targetHeight * ratio;
  }
  reelStageEl.style.width = `${Math.round(targetWidth)}px`;
  reelStageEl.style.height = `${Math.round(targetHeight)}px`;
}

function renderReel() {
  const jobs = reelJobs();
  if (!jobs.length) {
    closeReel();
    return;
  }
  state.reelIndex = Math.max(0, Math.min(jobs.length - 1, state.reelIndex));
  const job = jobs[state.reelIndex];
  const title = job.title || job.description || job.video_id || job.url || `#${job.id}`;
  const source = reelSource(job);
  const [fallbackWidth, fallbackHeight] = resolutionDimensions(job.resolution);
  state.reelVideoWidth = fallbackWidth;
  state.reelVideoHeight = fallbackHeight;
  fitReelStage(fallbackWidth, fallbackHeight);
  reelStageEl.innerHTML = `
    <video class="reel-video" controls autoplay playsinline preload="metadata" src="${source}"></video>
  `;
  reelInfoEl.innerHTML = `
    <span>${state.reelIndex + 1} / ${jobs.length}</span>
    <strong>${escapeHtml(title)}</strong>
    <span>${escapeHtml(job.author_name || "Unknown")} / ${escapeHtml(job.resolution || "-")} / ${fmtBytes(job.size_bytes || 0)}</span>
  `;
  reelPrevButton.disabled = state.reelIndex <= 0;
  reelNextButton.disabled = state.reelIndex >= jobs.length - 1;
  reelDeleteButton.disabled = false;
  reelDeleteButton.textContent = "删除";
  const video = reelStageEl.querySelector("video");
  if (video) {
    video.volume = state.reelVolume;
    video.muted = state.reelMuted;
    video.addEventListener("loadedmetadata", () => {
      if (video.videoWidth && video.videoHeight) {
        state.reelVideoWidth = video.videoWidth;
        state.reelVideoHeight = video.videoHeight;
        fitReelStage(video.videoWidth, video.videoHeight);
      }
    }, { once: true });
    video.addEventListener("volumechange", () => {
      state.reelVolume = Math.max(0, Math.min(1, Number(video.volume) || 0));
      state.reelMuted = Boolean(video.muted);
      localStorage.setItem("clipnest-reel-volume", String(state.reelVolume));
      localStorage.setItem("clipnest-reel-muted", String(state.reelMuted));
    });
    video.play().catch(() => {});
  }
}

function showReelLoading() {
  state.reelVideoWidth = 9;
  state.reelVideoHeight = 16;
  fitReelStage();
  reelStageEl.innerHTML = `<div class="reel-loading">加载视频中</div>`;
  reelInfoEl.innerHTML = "";
  reelPrevButton.disabled = true;
  reelNextButton.disabled = true;
  reelDeleteButton.disabled = true;
}

async function loadReelJobs() {
  const all = [];
  let page = 1;
  let totalPages = 1;
  do {
    const params = currentLibraryParams(100);
    params.set("page", String(page));
    params.set("type", "video");
    const result = await api(`/api/library/jobs?${params.toString()}`);
    all.push(...(result.items || []));
    totalPages = Math.max(1, Number(result.total_pages || 1));
    page += 1;
  } while (page <= totalPages);
  state.reelJobs = all;
  return reelJobs();
}

async function openReel(startJobId) {
  drawerScrimEl.hidden = true;
  reelViewerEl.hidden = false;
  document.body.classList.add("reel-open");
  showReelLoading();
  const jobs = await loadReelJobs();
  if (!jobs.length) {
    summaryEl.textContent = "当前筛选结果里没有可播放视频";
    closeReel();
    return;
  }
  const index = startJobId ? jobs.findIndex((job) => String(job.id) === String(startJobId)) : 0;
  state.reelIndex = index >= 0 ? index : 0;
  renderReel();
}

function closeReel() {
  if (!reelViewerEl) return;
  reelStageEl.querySelectorAll("video").forEach((video) => video.pause());
  reelViewerEl.hidden = true;
  state.reelJobs = [];
  reelStageEl.removeAttribute("style");
  document.body.classList.remove("reel-open");
  closeScrimIfIdle();
}

function stepReel(delta) {
  if (reelViewerEl.hidden) return;
  const jobs = reelJobs();
  if (!jobs.length) {
    closeReel();
    return;
  }
  const next = Math.max(0, Math.min(jobs.length - 1, state.reelIndex + delta));
  if (next === state.reelIndex) return;
  state.reelIndex = next;
  reelStageEl.classList.remove("reel-swap");
  void reelStageEl.offsetWidth;
  reelStageEl.classList.add("reel-swap");
  renderReel();
}

async function deleteCurrentReelJob() {
  if (reelViewerEl.hidden || reelDeleteButton.disabled) return;
  const jobs = reelJobs();
  const job = jobs[state.reelIndex];
  if (!job) return;
  const title = job.title || job.description || job.video_id || `#${job.id}`;
  if (!confirm(`删除当前视频和本地文件？\n${title}`)) return;
  try {
    reelDeleteButton.disabled = true;
    reelDeleteButton.textContent = "删除中";
    reelStageEl.querySelectorAll("video").forEach((video) => video.pause());
    await api(`/api/jobs/${job.id}?delete_file=true`, { method: "DELETE" });
    state.reelJobs = (state.reelJobs || []).filter((item) => String(item.id) !== String(job.id));
    state.libraryMediaJobs = state.libraryMediaJobs.filter((item) => String(item.id) !== String(job.id));
    state.selectedLibraryJobIds.delete(String(job.id));
    clearLibraryMediaCache();
    const remaining = reelJobs();
    if (!remaining.length) {
      closeReel();
      await loadLibraryPage();
      summaryEl.textContent = "当前视频已删除，播放列表已清空";
      return;
    }
    if (state.reelIndex >= remaining.length) {
      state.reelIndex = remaining.length - 1;
    }
    reelStageEl.classList.remove("reel-swap");
    void reelStageEl.offsetWidth;
    reelStageEl.classList.add("reel-swap");
    renderReel();
    await loadLibraryPage();
    summaryEl.textContent = "当前视频已删除";
  } catch (error) {
    summaryEl.textContent = error.message || "删除当前视频失败";
    reelDeleteButton.disabled = false;
    reelDeleteButton.textContent = "删除";
  }
}

function renderJobDetail(job, media, events) {
  const title = job.title || job.description || job.url || `#${job.id}`;
  drawerTitleEl.textContent = title;
  drawerKickerEl.textContent = `#${job.id} / ${statusLabel(job.status)}`;
  const isRunning = runningStatuses.has(job.status);
  const canDownload = job.status === "finished" && job.file_path;
  const statistics = (job.metadata && job.metadata.statistics) || {};
  const actions = [];
  if (canDownload) actions.push(`<a href="${mediaUrl(job, "file")}"><button type="button">打开文件</button></a>`);
  if (job.file_path) actions.push(`<button class="secondary" type="button" data-copy-value="${escapeHtml(job.file_path)}">复制路径</button>`);
  if (!isRunning) actions.push(`<button class="secondary" type="button" data-refresh-metadata="${job.id}">刷新解析</button>`);
  if (canDownload) actions.push(`<button class="secondary" type="button" data-force="${job.id}">重新下载</button>`);
  if (job.status === "failed" || job.status === "cancelled") actions.push(`<button class="secondary" type="button" data-retry="${job.id}">重试</button>`);
  drawerBodyEl.innerHTML = `
    <div class="detail-actions">${actions.join("")}</div>
    ${renderParseSummary(job)}
    <div class="detail-grid">
      ${detailRow("作者", job.author_name || "Unknown")}
      ${detailRow("状态", statusLabel(job.status))}
      ${detailRow("分辨率", job.resolution)}
      ${detailRow("编码", job.codec)}
      ${detailRow("大小", fmtBytes(job.size_bytes || 0))}
      ${detailRow("时长", fmtDuration(job.duration_seconds))}
      ${detailRow("完成时间", fmtDate(job.finished_at || job.updated_at))}
      ${detailRow("下载来源", job.download_label)}
      ${detailRow("本地文件", job.file_path)}
    </div>
    <details>
      <summary>更多任务信息</summary>
      <div class="detail-grid compact">
        ${detailRow("平台", job.platform)}
        ${detailRow("视频 ID", job.video_id)}
        ${detailRow("发布时间", fmtEpoch(job.metadata && job.metadata.create_time))}
        ${detailRow("请求清晰度", job.quality_preference)}
        ${detailRow("预期大小", fmtBytes(job.expected_size_bytes || 0))}
        ${detailRow("下载 Host", job.download_host)}
        ${detailRow("失败类型", job.error_type)}
        ${detailRow("重试次数", job.attempt_count)}
        ${detailRow("下次重试", fmtDate(job.next_attempt_at))}
        ${detailRow("创建时间", fmtDate(job.created_at))}
        ${detailRow("开始时间", fmtDate(job.started_at))}
        ${detailRow("原始链接", job.url)}
        ${detailRow("相对文件", media.file)}
        ${detailRow("相对预览", media.preview)}
      </div>
    </details>
    <details>
      <summary>互动数据</summary>
      <div class="detail-grid compact">
        ${detailRow("点赞", statistics.digg_count)}
        ${detailRow("评论", statistics.comment_count)}
        ${detailRow("收藏", statistics.collect_count)}
        ${detailRow("分享", statistics.share_count)}
      </div>
    </details>
    ${renderEvents(events)}
    ${job.error ? `<h2>错误</h2><pre class="detail-error">${escapeHtml(job.error)}</pre>` : ""}
    <details>
      <summary>解析元数据</summary>
      <pre class="detail-json">${escapeHtml(limitedJson(job.metadata))}</pre>
    </details>
  `;
}

async function openJobDetail(jobId) {
  drawerEl.hidden = false;
  drawerScrimEl.hidden = false;
  drawerTitleEl.textContent = "-";
  drawerKickerEl.textContent = "任务详情";
  drawerBodyEl.innerHTML = `<div class="empty">加载中</div>`;
  try {
    const [job, media, events] = await Promise.all([
      api(`/api/jobs/${jobId}`),
      api(`/api/jobs/${jobId}/media`),
      api(`/api/jobs/${jobId}/events`),
    ]);
    renderJobDetail(job, media, events);
  } catch (error) {
    drawerBodyEl.innerHTML = `<div class="empty">${escapeHtml(error.message || "加载失败")}</div>`;
  }
}

function closeDetailOnly() {
  drawerEl.hidden = true;
}

function closeMediaPreviewOnly() {
  mediaPreviewBodyEl.querySelectorAll("video").forEach((video) => video.pause());
  mediaPreviewDialogEl.hidden = true;
  closeScrimIfIdle();
}

function closeScrimIfIdle() {
  if (drawerEl.hidden && mediaPreviewDialogEl.hidden && qualityDialogEl.hidden) {
    drawerScrimEl.hidden = true;
  }
}

function closeOverlay() {
  drawerEl.hidden = true;
  closeMediaPreviewOnly();
  closeReel();
  qualityDialogEl.hidden = true;
  drawerScrimEl.hidden = true;
  state.pendingQualityPreview = null;
  state.pendingQualityAction = null;
  setQualityBusy(false);
}

function renderSettings(values) {
  settingSkipExisting.checked = Boolean(values.skip_existing);
  settingQueuePaused.checked = Boolean(values.queue_paused);
  settingMaxConcurrent.value = values.max_concurrent_downloads || 1;
  settingAutoRetryAttempts.value = values.auto_retry_attempts ?? 1;
  settingAutoRetryDelay.value = values.auto_retry_delay_seconds ?? 60;
  settingAuthorFolders.checked = Boolean(values.author_folders);
  settingFilenameTemplate.value = values.filename_template || "{author}：{desc}";
  settingTelegramEnabled.checked = Boolean(values.telegram_enabled);
  settingTelegramToken.value = "";
  settingTelegramStatus.textContent = values.telegram_bot_configured ? "Telegram Bot Token 已配置" : "Telegram Bot Token 未配置";
  settingTelegramChatId.value = values.telegram_chat_id || "";
  settingTelegramSuccess.checked = values.telegram_notify_success !== false;
  settingTelegramFailure.checked = Boolean(values.telegram_notify_failure);
}

function renderParserSettings(values) {
  settingParserAdapter.value = values.parser_adapter || "native_douyin";
  settingDouyinCookie.value = "";
  settingDouyinCookieStatus.textContent = values.douyin_cookie_configured
    ? `Cookie 已配置：${values.douyin_cookie_source || "database"}`
    : "Cookie 未配置";
  settingTikTokCookie.value = "";
  settingTikTokCookieStatus.textContent = values.tiktok_cookie_configured
    ? `Cookie 已配置：${values.tiktok_cookie_source || "database"}`
    : "Cookie 未配置";
  settingDouyinUserAgent.value = values.douyin_user_agent || "";
}

function renderParserInfo(info) {
  const parts = [info.adapter || "-"];
  if (info.dependency_mode) parts.push(info.dependency_mode);
  if (info.signer) parts.push(`signer:${info.signer}`);
  if (info.cookie_configured) parts.push("cookie");
  if (info.ok === true) parts.push("正常");
  if (info.ok === false) parts.push("异常");
  parserInfoEl.textContent = parts.join(" / ");
}

function setSettingsBusy(busy) {
  settingsSaveButton.disabled = busy;
  telegramTestButton.disabled = busy;
  settingsSaveButton.textContent = busy ? "保存中" : "保存设置";
}

function setTelegramTestBusy(busy) {
  telegramTestButton.disabled = busy;
  settingsSaveButton.disabled = busy;
  telegramTestButton.textContent = busy ? "发送中" : "发送 TG 测试";
}

async function loadSettings() {
  if (!state.authenticated) return;
  try {
    const [values, parserSettings, parser] = await Promise.all([
      api("/api/settings"),
      api("/api/parser/settings"),
      api("/api/parser"),
    ]);
    renderSettings(values);
    renderParserSettings(parserSettings);
    renderParserInfo(parser);
    maintenanceOutputEl.hidden = true;
  } catch (error) {
    summaryEl.textContent = error.message || "加载设置失败";
  }
}

async function loadLibraryPage() {
  if (!state.authenticated) return;
  try {
    if (state.libraryMode === "authors") {
      const params = new URLSearchParams({
        page: String(state.libraryAuthorsPage),
        page_size: String(libraryAuthorsPageSize),
      });
      if (state.libraryPlatform) params.set("platform", state.libraryPlatform);
      if (state.librarySearch) params.set("q", state.librarySearch);
      const result = await api(`/api/library/authors?${params.toString()}`);
      state.libraryAuthors = result.items || [];
      state.libraryAuthorsPage = result.page || 1;
      state.libraryAuthorsTotal = result.total || 0;
      state.libraryAuthorsTotalPages = result.total_pages || 1;
    } else if (state.libraryMode === "media") {
      const [media, authorDetail] = await Promise.all([
        fetchLibraryMediaPage(state.libraryMediaPage),
        fetchLibraryAuthorDetail(),
      ]);
      applyLibraryMediaResult(media, state.libraryMediaPage);
      state.libraryAuthorDetail = authorDetail;
    } else {
      const params = new URLSearchParams({
        page: String(state.libraryRecordsPage),
        page_size: state.libraryRecordsKind === "deleted" ? "20" : "18",
        sort: state.librarySort || "publish_desc",
      });
      if (state.librarySearch) params.set("q", state.librarySearch);
      if (state.libraryPlatform) params.set("platform", state.libraryPlatform);
      if (state.libraryType && state.libraryRecordsKind === "media") params.set("type", state.libraryType);
      if (state.recordAuthor) params.set("author", state.recordAuthor);
      if (state.recordDateFrom) params.set("date_from", state.recordDateFrom);
      if (state.recordDateTo) params.set("date_to", state.recordDateTo);
      if (state.libraryRecordsKind === "media") {
        params.set("status", state.recordStatus || "finished");
        params.set("date_field", state.recordDateField || "download");
      }
      const endpoint = state.libraryRecordsKind === "deleted" ? "/api/library/deleted" : "/api/library/jobs";
      const result = await api(`${endpoint}?${params.toString()}`);
      state.libraryRecords = result.items || [];
      state.libraryRecordsPage = result.page || 1;
      state.libraryRecordsTotal = result.total || 0;
      state.libraryRecordsTotalPages = result.total_pages || 1;
    }
    renderLibrary();
  } catch (error) {
    summaryEl.textContent = error.message || "媒体库加载失败";
  }
}

async function deleteSelectedLibraryItems() {
  const mode = state.libraryMode;
  const selected = selectedLibrarySet();
  const selectedKeys = Array.from(selected);
  if (!selectedKeys.length) {
    summaryEl.textContent = "请先选择要删除的内容";
    return;
  }
  const selectedVisibleCount = visibleLibraryKeys().filter((key) => selected.has(String(key))).length;
  const currentVisibleCount = visibleLibraryKeys().length;
  if (mode === "authors") {
    if (!confirm(`删除已选 ${selectedKeys.length} 个作者的全部作品和本地文件？\n正在下载中的任务会跳过。`)) return;
    libraryDeleteSelectedButton.disabled = true;
    summaryEl.textContent = "正在删除已选作者作品";
    let deleted = 0;
    let skipped = 0;
    for (const author of selectedKeys) {
      const params = new URLSearchParams({ author, delete_file: "true" });
      if (state.libraryPlatform) params.set("platform", state.libraryPlatform);
      const result = await api(`/api/library/author?${params.toString()}`, { method: "DELETE" });
      deleted += result.deleted_count || (result.deleted || []).length || 0;
      skipped += (result.skipped || []).length;
    }
    clearLibrarySelection();
    clearLibraryMediaCache();
    if (selectedVisibleCount >= currentVisibleCount && state.libraryAuthorsPage > 1) {
      state.libraryAuthorsPage -= 1;
    }
    await loadLibraryPage();
    summaryEl.textContent = skipped
      ? `已删除 ${deleted} 条，跳过 ${skipped} 条运行中的任务`
      : `已删除 ${deleted} 条作者作品`;
    return;
  }
  if (mode === "records" && state.libraryRecordsKind === "deleted") {
    const recordIds = selectedKeys.map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0);
    if (!recordIds.length) {
      summaryEl.textContent = "没有可恢复的已删除记录";
      return;
    }
    if (!confirm(`恢复已选 ${recordIds.length} 条已删除记录？恢复后同步可能会重新加入这些作品。`)) return;
    libraryDeleteSelectedButton.disabled = true;
    summaryEl.textContent = "正在恢复已删除记录";
    let restored = 0;
    for (const recordId of recordIds) {
      await api(`/api/library/deleted/${recordId}`, { method: "DELETE" });
      restored += 1;
    }
    clearLibrarySelection();
    clearLibraryMediaCache();
    if (selectedVisibleCount >= currentVisibleCount && state.libraryRecordsPage > 1) {
      state.libraryRecordsPage -= 1;
    }
    await loadLibraryPage();
    summaryEl.textContent = `已恢复 ${restored} 条记录`;
    return;
  }
  const jobIds = selectedKeys.map((id) => Number(id)).filter((id) => Number.isFinite(id) && id > 0);
  if (!jobIds.length) {
    summaryEl.textContent = "没有可删除的作品";
    return;
  }
  if (!confirm(`删除已选 ${jobIds.length} 个作品和本地文件？`)) return;
  libraryDeleteSelectedButton.disabled = true;
  summaryEl.textContent = "正在删除已选作品";
  const result = await api("/api/jobs/bulk/delete", {
    method: "POST",
    body: JSON.stringify({ job_ids: jobIds, delete_file: true }),
  });
  clearLibrarySelection();
  clearLibraryMediaCache();
  if (mode === "records" && selectedVisibleCount >= currentVisibleCount && state.libraryRecordsPage > 1) {
    state.libraryRecordsPage -= 1;
  } else if (selectedVisibleCount >= currentVisibleCount && state.libraryMediaPage > 1) {
    state.libraryMediaPage -= 1;
  }
  await loadLibraryPage();
  const deleted = (result.deleted || []).length;
  const skipped = (result.skipped || []).length;
  summaryEl.textContent = skipped
    ? `已删除 ${deleted} 个作品，跳过 ${skipped} 个运行中的任务`
    : `已删除 ${deleted} 个作品`;
}

async function loadSyncPage() {
  if (!state.authenticated) return;
  try {
    const params = new URLSearchParams({
      page: String(state.syncAuthorsPage),
      page_size: String(syncPageSize()),
      platform: "douyin",
    });
    if (state.syncSearch) params.set("q", state.syncSearch);
    if (state.syncEnabledFilter === "enabled") params.set("enabled", "true");
    if (state.syncEnabledFilter === "disabled") params.set("enabled", "false");
    const [sources] = await Promise.all([
      api(`/api/author-sync-sources?${params.toString()}`),
      loadAuthorCrawls(),
    ]);
    state.syncSources = sources.items || [];
    state.syncAuthorsPage = sources.page || 1;
    state.syncSourcesTotal = sources.total || 0;
    state.syncSourcesTotalPages = sources.total_pages || 1;
    state.syncSourceStats = sources.stats || { total: state.syncSourcesTotal, enabled: 0, disabled: 0, missing_identity: 0 };
    state.syncAuthors = state.syncSources;
    state.syncAuthorsTotal = state.syncSourcesTotal;
    state.syncAuthorsTotalPages = state.syncSourcesTotalPages;
    renderSync();
  } catch (error) {
    summaryEl.textContent = error.message || "同步页加载失败";
  }
}

async function loadTasksPage() {
  if (!state.authenticated) return;
  const params = new URLSearchParams({
    page: String(state.tasksPage),
    page_size: String(tasksPageSize),
  });
  if (state.statusFilter) params.set("status", state.statusFilter);
  if (state.authorFilter) params.set("author", state.authorFilter);
  if (state.taskPlatform) params.set("platform", state.taskPlatform);
  if (state.taskSearch) params.set("q", state.taskSearch);
  const result = await api(`/api/jobs?${params.toString()}`);
  state.jobs = result.items || [];
  state.tasksPage = result.page || 1;
  state.tasksTotal = result.total || 0;
  state.tasksTotalPages = result.total_pages || 1;
}

async function loadLogsPage() {
  if (!state.authenticated) return;
  const params = new URLSearchParams({
    page: String(state.logsPage),
    page_size: "30",
  });
  if (state.logsSearch) params.set("q", state.logsSearch);
  if (state.logsType) params.set("event_type", state.logsType);
  if (state.logsPlatform) params.set("platform", state.logsPlatform);
  if (state.logsStatus) params.set("status", state.logsStatus);
  if (state.logsDateFrom) params.set("date_from", state.logsDateFrom);
  if (state.logsDateTo) params.set("date_to", state.logsDateTo);
  const result = await api(`/api/logs/events?${params.toString()}`);
  state.logs = result.items || [];
  state.logsPage = result.page || 1;
  state.logsTotal = result.total || 0;
  state.logsTotalPages = result.total_pages || 1;
  state.logsEventTypes = result.event_types || [];
  renderLogs();
}

async function loadAuthorCrawls() {
  if (!state.authenticated) return;
  state.authorCrawls = await api("/api/author-crawls?limit=20");
}

async function refreshTasksInPlace() {
  if (!state.authenticated) return;
  try {
    tasksRefreshButton.disabled = true;
    tasksRefreshButton.textContent = "刷新中";
    const [stats, activeJobs, authors] = await Promise.all([
      api("/api/stats"),
      api("/api/jobs?limit=20&status=active"),
      api("/api/library/authors?limit=200"),
      loadTasksPage(),
      loadAuthorCrawls(),
    ]);
    state.stats = stats;
    state.activeJobs = activeJobs;
    state.authors = authors;
    renderAll();
    summaryEl.textContent = "任务已刷新";
  } catch (error) {
    summaryEl.textContent = error.message || "刷新任务失败";
  } finally {
    tasksRefreshButton.disabled = false;
    tasksRefreshButton.textContent = "刷新任务";
  }
}

async function refreshLibraryInPlace() {
  if (!state.authenticated) return;
  try {
    libraryRefreshButton.disabled = true;
    libraryRefreshButton.textContent = "刷新中";
    if (state.libraryMode === "media") {
      clearLibraryMediaCache();
      await loadLibraryMediaPage(state.libraryMediaPage, { force: true, direction: 0 });
    } else {
      await loadLibraryPage();
    }
    summaryEl.textContent = state.libraryMode === "authors" ? "作者已刷新" : "作品已刷新";
  } catch (error) {
    summaryEl.textContent = error.message || "刷新媒体库失败";
  } finally {
    libraryRefreshButton.disabled = false;
    libraryRefreshButton.textContent = "刷新";
  }
}

async function refreshSyncInPlace() {
  if (!state.authenticated) return;
  try {
    syncRefreshButton.disabled = true;
    syncRefreshButton.textContent = "刷新中";
    await loadSyncPage();
    summaryEl.textContent = "作者同步页已刷新";
  } catch (error) {
    summaryEl.textContent = error.message || "刷新同步页失败";
  } finally {
    syncRefreshButton.disabled = false;
    syncRefreshButton.textContent = "刷新";
  }
}

async function refresh() {
  if (!state.authenticated) {
    summaryEl.textContent = "请登录";
    statsEl.innerHTML = "";
    activeJobsEl.innerHTML = `<div class="empty">暂无任务</div>`;
    jobsEl.innerHTML = `<div class="empty">暂无任务</div>`;
    taskAuthorCrawlsEl.innerHTML = `<div class="empty compact">暂无作者同步任务</div>`;
    downloadTaskCountEl.textContent = "0 个任务";
    authorCrawlTaskCountEl.textContent = "0 个任务";
    libraryAuthorsEl.innerHTML = `<div class="empty">暂无作者</div>`;
    libraryMediaEl.innerHTML = `<div class="empty">暂无作品</div>`;
    libraryRecordsEl.innerHTML = `<tr><td><div class="empty compact">暂无记录</div></td></tr>`;
    libraryRecordsPaginationEl.innerHTML = "";
    syncAuthorsEl.innerHTML = `<div class="empty">暂无作者</div>`;
    syncCrawlJobsEl.innerHTML = `<div class="empty compact">暂无作者抓取任务</div>`;
    syncOverviewEl.innerHTML = "";
    if (logsEventsEl) logsEventsEl.innerHTML = `<div class="empty compact">暂无日志</div>`;
    if (logsOverviewEl) logsOverviewEl.innerHTML = "";
    if (logsPaginationEl) logsPaginationEl.innerHTML = "";
    authorsEl.innerHTML = "";
    return;
  }
  try {
    const [stats, activeJobs, authors] = await Promise.all([
      api("/api/stats"),
      api("/api/jobs?limit=20&status=active"),
      api("/api/library/authors?limit=200"),
      loadAuthorCrawls(),
    ]);
    await loadTasksPage();
    state.stats = stats;
    state.activeJobs = activeJobs;
    state.authors = authors;
    const onLibraryMedia = state.currentView === "library" && state.libraryMode === "media";
    const hasLibraryMediaGrid = Boolean(libraryMediaEl.querySelector(".media-page")) || state.libraryMediaTransitioning;
    const skipLibraryMediaGrid = onLibraryMedia && hasLibraryMediaGrid;
    renderAll({ skipLibraryMediaGrid });
    if (state.currentView === "library" && (!onLibraryMedia || !skipLibraryMediaGrid)) {
      await loadLibraryPage();
    }
    if (state.currentView === "sync") {
      await loadSyncPage();
    }
    if (state.currentView === "logs") {
      await loadLogsPage();
    }
    if (state.currentView === "dashboard") {
      summaryEl.textContent = `${stats.finished || 0} 完成 / ${stats.running || 0} 运行 / ${stats.queued || 0} 排队`;
    }
  } catch (error) {
    if (String(error.message || "").includes("Invalid API token")) {
      state.authenticated = false;
      renderSession();
    }
    summaryEl.textContent = error.message || "加载失败";
  }
}

async function saveSettings() {
  const payload = {
    skip_existing: settingSkipExisting.checked,
    queue_paused: settingQueuePaused.checked,
    max_concurrent_downloads: Number(settingMaxConcurrent.value || 1),
    auto_retry_attempts: Number(settingAutoRetryAttempts.value || 0),
    auto_retry_delay_seconds: Number(settingAutoRetryDelay.value || 0),
    author_folders: settingAuthorFolders.checked,
    filename_template: settingFilenameTemplate.value.trim(),
    telegram_enabled: settingTelegramEnabled.checked,
    telegram_chat_id: settingTelegramChatId.value.trim(),
    telegram_notify_success: settingTelegramSuccess.checked,
    telegram_notify_failure: settingTelegramFailure.checked,
  };
  const telegramToken = settingTelegramToken.value.trim();
  if (telegramToken) payload.telegram_bot_token = telegramToken;
  const parserPayload = {
    parser_adapter: settingParserAdapter.value,
    douyin_user_agent: settingDouyinUserAgent.value.trim(),
  };
  const cookie = settingDouyinCookie.value.trim();
  if (cookie) parserPayload.douyin_cookie = cookie;
  const tiktokCookie = settingTikTokCookie.value.trim();
  if (tiktokCookie) parserPayload.tiktok_cookie = tiktokCookie;
  try {
    setSettingsBusy(true);
    settingsSaveStatus.textContent = "正在保存设置";
    summaryEl.textContent = "正在保存设置";
    const [savedSettings, savedParserSettings] = await Promise.all([
      api("/api/settings", { method: "PATCH", body: JSON.stringify(payload) }),
      api("/api/parser/settings", { method: "PATCH", body: JSON.stringify(parserPayload) }),
    ]);
    renderSettings(savedSettings);
    renderParserSettings(savedParserSettings);
    renderParserInfo(await api("/api/parser"));
    settingsSaveStatus.textContent = "设置已保存";
    summaryEl.textContent = "配置已保存";
  } catch (error) {
    settingsSaveStatus.textContent = error.message || "保存失败";
    summaryEl.textContent = error.message || "保存失败";
  } finally {
    setSettingsBusy(false);
  }
}

async function testTelegramSettings() {
  const chatId = settingTelegramChatId.value.trim();
  const telegramToken = settingTelegramToken.value.trim();
  if (!chatId) {
    settingTelegramStatus.textContent = "请先填写 Telegram Chat ID";
    return;
  }
  const payload = { telegram_chat_id: chatId };
  if (telegramToken) payload.telegram_bot_token = telegramToken;
  try {
    setTelegramTestBusy(true);
    settingTelegramStatus.textContent = "正在发送 Telegram 测试消息";
    summaryEl.textContent = "正在发送 Telegram 测试消息";
    const result = await api("/api/settings/telegram/test", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    settingTelegramStatus.textContent = result.message || "Telegram 测试消息已发送";
    summaryEl.textContent = result.message || "Telegram 测试消息已发送";
  } catch (error) {
    settingTelegramStatus.textContent = error.message || "Telegram 测试发送失败";
    summaryEl.textContent = error.message || "Telegram 测试发送失败";
  } finally {
    setTelegramTestBusy(false);
  }
}

function maintenanceMetric(label, value) {
  return `
    <div class="maintenance-metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value ?? "-")}</strong>
    </div>
  `;
}

function rawDetails(value) {
  return `
    <details class="raw-details">
      <summary>原始数据</summary>
      <pre>${escapeHtml(JSON.stringify(value || {}, null, 2))}</pre>
    </details>
  `;
}

function showMaintenanceResult({ title, status, tone = "ok", summary, metrics = [], body = "", raw = null }) {
  maintenanceOutputEl.hidden = false;
  maintenanceOutputEl.className = `maintenance-output ${tone}`;
  maintenanceOutputEl.innerHTML = `
    <div class="maintenance-result-head">
      <div>
        <span>检查结果</span>
        <strong>${escapeHtml(title)}</strong>
      </div>
      <span class="result-badge">${escapeHtml(status)}</span>
    </div>
    <p class="maintenance-summary">${escapeHtml(summary || "")}</p>
    ${metrics.length ? `<div class="maintenance-metrics">${metrics.join("")}</div>` : ""}
    ${body}
    ${raw !== null ? rawDetails(raw) : ""}
  `;
}

function showHealthOutput(health) {
  const stats = health.stats || {};
  const parser = health.parser || {};
  const database = health.database || {};
  const appSettings = health.settings || {};
  const ok = Boolean(health.ok);
  const summary = ok
    ? "系统运行正常。网页进程没有承担下载工作，下载由独立后台进程处理，数据库也处于可并发读写的 WAL 模式。"
    : "系统状态异常，需要查看原始数据里的错误字段。";
  const authors = (stats.authors || []).slice(0, 5);
  const body = authors.length
    ? `
      <div class="maintenance-list">
        <h3>作者占用排行</h3>
        ${authors.map((item) => `
          <div class="maintenance-list-row">
            <span>${escapeHtml(item.author || "Unknown")}</span>
            <strong>${item.count || 0} 个 / ${fmtBytes(item.bytes || 0)}</strong>
          </div>
        `).join("")}
      </div>
    `
    : "";
  showMaintenanceResult({
    title: "系统健康",
    status: ok ? "正常" : "异常",
    tone: ok ? "ok" : "bad",
    summary,
    metrics: [
      maintenanceMetric("总任务", stats.total || 0),
      maintenanceMetric("已完成", stats.finished || 0),
      maintenanceMetric("运行中", stats.running || 0),
      maintenanceMetric("失败", stats.failed || 0),
      maintenanceMetric("文件占用", fmtBytes(stats.bytes || 0)),
      maintenanceMetric("解析器", parser.adapter || "-"),
      maintenanceMetric("Cookie", parser.cookie_configured ? "已配置" : "未配置"),
      maintenanceMetric("数据库", `${database.journal_mode || "-"} / ${database.busy_timeout || 0}ms`),
      maintenanceMetric("队列", appSettings.queue_paused ? "已暂停" : "正常领取"),
      maintenanceMetric("并发下载", appSettings.max_concurrent_downloads || 1),
    ],
    body,
    raw: health,
  });
}

function showCookieOutput(info) {
  const configured = Boolean(info.cookie_configured);
  const failure = info.latest_parse_failure || null;
  const hasFailure = Boolean(failure);
  const summary = configured
    ? `Cookie 已配置，来源是 ${info.cookie_source || "未知"}。${info.latest_parse_success_at ? `最近一次解析成功在 ${fmtDate(info.latest_parse_success_at)}。` : "暂时还没有成功解析记录。"}`
    : "Cookie 还没有配置，部分视频可能只能拿到低清或无法解析。";
  const body = hasFailure
    ? `
      <div class="maintenance-note bad">
        最近解析失败：${escapeHtml(failure.error || failure.error_type || "未知错误")}
      </div>
    `
    : "";
  showMaintenanceResult({
    title: "Cookie 状态",
    status: configured ? (hasFailure ? "需留意" : "正常") : "未配置",
    tone: configured ? (hasFailure ? "warn" : "ok") : "warn",
    summary,
    metrics: [
      maintenanceMetric("Cookie", configured ? "已配置" : "未配置"),
      maintenanceMetric("来源", info.cookie_source || "-"),
      maintenanceMetric("最近成功", fmtDate(info.latest_parse_success_at)),
      maintenanceMetric("最近失败", fmtDate(info.latest_parse_failure_at)),
    ],
    body,
    raw: info,
  });
}

function showTikTokDiagnostics(info) {
  const failures = Array.isArray(info.recent_failures) ? info.recent_failures : [];
  const suggestions = Array.isArray(info.suggestions) ? info.suggestions : [];
  const body = `
    ${suggestions.length ? `
      <div class="maintenance-note warn">
        ${suggestions.map((item) => `<p>${escapeHtml(item)}</p>`).join("")}
      </div>
    ` : ""}
    ${failures.length ? `
      <div class="maintenance-list">
        <h3>最近 TikTok 失败</h3>
        ${failures.map((item) => `
          <div class="maintenance-list-row stacked">
            <span>#${item.id} / ${escapeHtml(fmtDate(item.updated_at || item.created_at))}</span>
            <strong>${escapeHtml((item.diagnosis && item.diagnosis.message) || item.message || "失败")}</strong>
            <em>${escapeHtml((item.diagnosis && item.diagnosis.suggestion) || "")}</em>
          </div>
        `).join("")}
      </div>
    ` : `<div class="maintenance-note ok">最近没有 TikTok 失败任务。</div>`}
  `;
  showMaintenanceResult({
    title: "TikTok 诊断",
    status: info.cookie_configured ? "Cookie 已配置" : "Cookie 未配置",
    tone: failures.length ? "warn" : "ok",
    summary: info.cookie_configured
      ? `TikTok Cookie 已配置，来源是 ${info.cookie_source || "未知"}。`
      : "TikTok Cookie 未配置，公开视频可能可用，但受地区/登录态限制的视频更容易失败。",
    metrics: [
      maintenanceMetric("Cookie", info.cookie_configured ? "已配置" : "未配置"),
      maintenanceMetric("来源", info.cookie_source || "-"),
      maintenanceMetric("适配器", (info.adapter && info.adapter.adapter) || "native_tiktok"),
      maintenanceMetric("最近失败", failures.length),
    ],
    body,
    raw: info,
  });
}

function showEventsOutput(events) {
  const rows = Array.isArray(events) ? events : [];
  const body = rows.length
    ? `
      <div class="maintenance-events">
        ${rows.slice(0, 30).map((event) => `
          <div class="maintenance-event">
            <span>${escapeHtml(fmtDate(event.created_at))}</span>
            <strong>${escapeHtml(eventLabel(event.event_type))}</strong>
            <p>${escapeHtml(event.title || event.author_name || `任务 #${event.job_id || "-"}`)}：${escapeHtml(event.message || "")}</p>
          </div>
        `).join("")}
      </div>
    `
    : `<div class="maintenance-note">暂时没有运行记录。</div>`;
  showMaintenanceResult({
    title: "最近事件",
    status: rows.length ? `${rows.length} 条` : "无记录",
    tone: "ok",
    summary: rows.length ? "这里按时间倒序显示最近的解析、下载、重试、取消等运行记录。" : "后台还没有产生事件记录。",
    metrics: [
      maintenanceMetric("显示数量", rows.length),
      maintenanceMetric("最新事件", rows[0] ? fmtDate(rows[0].created_at) : "-"),
    ],
    body,
    raw: events,
  });
}

function showOrphansOutput(result, cleaned = false) {
  const orphans = result.orphans || [];
  const removed = result.removed || [];
  const orphanBytes = orphans.reduce((total, item) => total + Number(item.size_bytes || 0), 0);
  const tone = orphans.length ? "warn" : "ok";
  const summary = cleaned
    ? (removed.length ? `已经清理 ${removed.length} 个数据库没有引用的文件。` : "没有需要清理的孤儿文件。")
    : (orphans.length ? `发现 ${orphans.length} 个数据库没有引用的文件，可以确认后清理。` : "没有发现孤儿文件，下载目录和数据库记录是对齐的。");
  const bodyItems = cleaned ? removed.map((path) => ({ path })) : orphans;
  const body = bodyItems.length
    ? `
      <div class="maintenance-list">
        <h3>${cleaned ? "已清理文件" : "待处理文件"}</h3>
        ${bodyItems.slice(0, 20).map((item) => `
          <div class="maintenance-file">
            <span>${escapeHtml(item.path)}</span>
            ${item.size_bytes ? `<strong>${fmtBytes(item.size_bytes)}</strong>` : ""}
            ${item.error ? `<em>${escapeHtml(item.error)}</em>` : ""}
          </div>
        `).join("")}
      </div>
    `
    : "";
  showMaintenanceResult({
    title: cleaned ? "孤儿文件清理" : "孤儿文件扫描",
    status: cleaned ? `已清理 ${removed.length} 个` : (orphans.length ? `发现 ${orphans.length} 个` : "干净"),
    tone,
    summary,
    metrics: [
      maintenanceMetric("扫描目录", result.root || "-"),
      maintenanceMetric("待处理", orphans.length),
      maintenanceMetric("已清理", removed.length),
      maintenanceMetric("待处理大小", fmtBytes(orphanBytes)),
      maintenanceMetric("结果截断", result.truncated ? "是" : "否"),
    ],
    body,
    raw: result,
  });
}

function duplicateJobLabel(job) {
  const title = job.title || job.description || job.video_id || job.url || `任务 #${job.id}`;
  return `${title} / #${job.id}`;
}

function showDuplicatesOutput(result, cleaned = false) {
  const groups = result.groups || [];
  const duplicateCount = result.duplicate_count || 0;
  const deletedCount = result.deleted_count || 0;
  const tone = duplicateCount ? "warn" : "ok";
  const summary = cleaned
    ? (deletedCount ? `已经清理 ${deletedCount} 条重复任务记录，本地视频文件没有删除。` : "没有需要清理的重复任务记录。")
    : (duplicateCount ? `发现 ${duplicateCount} 条重复任务记录。清理只删除重复任务记录，不删除本地视频文件。` : "没有发现重复作品记录，媒体库是干净的。");
  const body = groups.length
    ? `
      <div class="maintenance-list">
        <h3>${cleaned ? "本次处理的重复作品" : "重复作品"}</h3>
        ${groups.slice(0, 20).map((group) => `
          <div class="maintenance-file">
            <span>保留：${escapeHtml(duplicateJobLabel(group.keep_job || {}))}</span>
            <strong>重复 ${group.duplicate_count || 0} 条</strong>
            ${(group.duplicates || []).slice(0, 5).map((job) => `
              <em>重复：${escapeHtml(duplicateJobLabel(job))}</em>
            `).join("")}
          </div>
        `).join("")}
      </div>
    `
    : "";
  showMaintenanceResult({
    title: cleaned ? "重复记录清理" : "重复作品扫描",
    status: cleaned ? `已清理 ${deletedCount} 条` : (duplicateCount ? `发现 ${duplicateCount} 条` : "干净"),
    tone,
    summary,
    metrics: [
      maintenanceMetric("重复作品组", result.group_count || 0),
      maintenanceMetric("重复记录", duplicateCount),
      maintenanceMetric("已清理", deletedCount),
      maintenanceMetric("重复占用估算", fmtBytes(result.duplicate_bytes || 0)),
      maintenanceMetric("结果截断", result.truncated ? "是" : "否"),
    ],
    body,
    raw: result,
  });
}

function showConfigOutput(config) {
  const appSettings = config.app_settings || {};
  const parserSettings = config.parser_settings || {};
  showMaintenanceResult({
    title: "配置导出",
    status: "已生成",
    tone: "ok",
    summary: "配置文件已经下载到浏览器，同时这里显示当前关键配置摘要。",
    metrics: [
      maintenanceMetric("解析器", parserSettings.parser_adapter || "-"),
      maintenanceMetric("Cookie", parserSettings.douyin_cookie_configured ? "已配置" : "未配置"),
      maintenanceMetric("签名器", parserSettings.douyin_signer_kind || "-"),
      maintenanceMetric("队列", appSettings.queue_paused ? "已暂停" : "正常领取"),
      maintenanceMetric("并发下载", appSettings.max_concurrent_downloads || 1),
      maintenanceMetric("文件名模板", appSettings.filename_template || "-"),
    ],
    raw: config,
  });
}

function showAssetCacheOutput(result) {
  showMaintenanceResult({
    title: "封面头像缓存",
    status: result.failed_count ? "部分失败" : "完成",
    tone: result.failed_count ? "warn" : "ok",
    summary: `已缓存 ${result.cached_covers || 0} 个封面、${result.cached_avatars || 0} 个作者头像。`,
    metrics: [
      maintenanceMetric("封面", result.cached_covers || 0),
      maintenanceMetric("头像", result.cached_avatars || 0),
      maintenanceMetric("失败", result.failed_count || 0),
    ],
    raw: result,
  });
}

function downloadJson(filename, value) {
  const blob = new Blob([JSON.stringify(value || {}, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function reloadRecordsFromFilters() {
  state.libraryRecordsPage = 1;
  if (state.libraryMode === "records") {
    showLibraryLoading("records");
    loadLibraryPage();
  }
}

async function runBulkAction(endpoint, payload, doneLabel) {
  const ids = Array.from(state.selectedJobIds).map((id) => Number(id));
  if (!ids.length) return;
  const result = await api(endpoint, {
    method: "POST",
    body: JSON.stringify({ job_ids: ids, ...payload }),
  });
  state.selectedJobIds.clear();
  const changed = (result.updated || result.deleted || []).length;
  const skipped = (result.skipped || []).length;
  summaryEl.textContent = `${doneLabel}：${changed} 个，跳过 ${skipped} 个`;
  refresh();
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.view));
});

document.querySelectorAll("[data-view-jump]").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.viewJump));
});

function reloadLogsFromFilters() {
  state.logsPage = 1;
  loadLogsPage().catch((error) => {
    summaryEl.textContent = error.message || "日志加载失败";
  });
}

if (logsSearchInput) {
  logsSearchInput.addEventListener("input", () => {
    state.logsSearch = logsSearchInput.value.trim();
    window.clearTimeout(logsSearchTimer);
    logsSearchTimer = window.setTimeout(reloadLogsFromFilters, 260);
  });
}

if (logsTypeFilter) {
  logsTypeFilter.addEventListener("change", () => {
    state.logsType = logsTypeFilter.value || "";
    reloadLogsFromFilters();
  });
}

if (logsPlatformFilter) {
  logsPlatformFilter.addEventListener("change", () => {
    state.logsPlatform = logsPlatformFilter.value || "";
    reloadLogsFromFilters();
  });
}

if (logsStatusFilter) {
  logsStatusFilter.addEventListener("change", () => {
    state.logsStatus = logsStatusFilter.value || "";
    reloadLogsFromFilters();
  });
}

if (logsDateFrom) {
  logsDateFrom.addEventListener("change", () => {
    state.logsDateFrom = logsDateFrom.value || "";
    reloadLogsFromFilters();
  });
}

if (logsDateTo) {
  logsDateTo.addEventListener("change", () => {
    state.logsDateTo = logsDateTo.value || "";
    reloadLogsFromFilters();
  });
}

if (logsClearFilterButton) {
  logsClearFilterButton.addEventListener("click", () => {
    state.logsSearch = "";
    state.logsType = "";
    state.logsPlatform = "";
    state.logsStatus = "";
    state.logsDateFrom = "";
    state.logsDateTo = "";
    if (logsSearchInput) logsSearchInput.value = "";
    if (logsTypeFilter) logsTypeFilter.value = "";
    if (logsPlatformFilter) logsPlatformFilter.value = "";
    if (logsStatusFilter) logsStatusFilter.value = "";
    if (logsDateFrom) logsDateFrom.value = "";
    if (logsDateTo) logsDateTo.value = "";
    window.clearTimeout(logsSearchTimer);
    reloadLogsFromFilters();
  });
}

if (logsRefreshButton) {
  logsRefreshButton.addEventListener("click", async () => {
    const originalText = logsRefreshButton.textContent;
    try {
      logsRefreshButton.disabled = true;
      logsRefreshButton.textContent = "刷新中";
      await loadLogsPage();
      summaryEl.textContent = "日志已刷新";
    } catch (error) {
      summaryEl.textContent = error.message || "刷新日志失败";
    } finally {
      logsRefreshButton.disabled = false;
      logsRefreshButton.textContent = originalText;
    }
  });
}

if (logsEventsEl) {
  logsEventsEl.addEventListener("click", (event) => {
    const button = event.target.closest("[data-log-open-job]");
    if (!button) return;
    openJobDetail(button.dataset.logOpenJob);
  });
}

document.querySelectorAll("[data-library-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    setLibraryMode(button.dataset.libraryMode || "authors");
    state.libraryAuthorsPage = 1;
    state.libraryMediaPage = 1;
    state.libraryRecordsPage = 1;
    loadLibraryPage();
  });
});

libraryPlatformTabsEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-library-platform]");
  if (!button) return;
  setLibraryPlatform(button.dataset.libraryPlatform || "");
  loadLibraryPage();
});

if (recordToolsEl) {
  recordToolsEl.addEventListener("click", (event) => {
    const button = event.target.closest("[data-record-kind]");
    if (!button) return;
    state.libraryRecordsKind = button.dataset.recordKind === "deleted" ? "deleted" : "media";
    localStorage.setItem("clipnest-library-record-kind", state.libraryRecordsKind);
    state.libraryRecordsPage = 1;
    clearLibrarySelection();
    showLibraryLoading("records");
    loadLibraryPage();
  });
}

if (recordClearDeletedButton) {
  recordClearDeletedButton.addEventListener("click", async () => {
    const platformText = state.libraryPlatform ? platformLabel(state.libraryPlatform) : "全部平台";
    const searchText = state.librarySearch ? `，搜索：${state.librarySearch}` : "";
    const authorText = state.recordAuthor ? `，作者：${state.recordAuthor}` : "";
    const dateText = state.recordDateFrom || state.recordDateTo
      ? `，日期：${state.recordDateFrom || "不限"} 至 ${state.recordDateTo || "不限"}`
      : "";
    if (!confirm(`清空已删除记录？\n范围：${platformText}${searchText}${authorText}${dateText}\n这些作品之后可能会被同步重新加入。`)) return;
    try {
      recordClearDeletedButton.disabled = true;
      recordClearDeletedButton.textContent = "清理中";
      const params = new URLSearchParams();
      if (state.libraryPlatform) params.set("platform", state.libraryPlatform);
      if (state.librarySearch) params.set("q", state.librarySearch);
      if (state.recordAuthor) params.set("author", state.recordAuthor);
      if (state.recordDateFrom) params.set("date_from", state.recordDateFrom);
      if (state.recordDateTo) params.set("date_to", state.recordDateTo);
      const result = await api(`/api/library/deleted?${params.toString()}`, { method: "DELETE" });
      state.libraryRecordsPage = 1;
      await loadLibraryPage();
      summaryEl.textContent = `已清空 ${result.deleted_count || 0} 条已删除记录`;
    } catch (error) {
      summaryEl.textContent = error.message || "清空已删除记录失败";
    } finally {
      recordClearDeletedButton.disabled = false;
      recordClearDeletedButton.textContent = "清空已删除记录";
    }
  });
}

if (recordStatusFilter) {
  recordStatusFilter.addEventListener("change", () => {
    state.recordStatus = recordStatusFilter.value || "finished";
    localStorage.setItem("clipnest-record-status", state.recordStatus);
    reloadRecordsFromFilters();
  });
}

if (recordAuthorFilter) {
  recordAuthorFilter.addEventListener("input", () => {
    state.recordAuthor = recordAuthorFilter.value.trim();
    reloadRecordsFromFilters();
  });
}

if (recordDateField) {
  recordDateField.addEventListener("change", () => {
    state.recordDateField = recordDateField.value || "download";
    localStorage.setItem("clipnest-record-date-field", state.recordDateField);
    reloadRecordsFromFilters();
  });
}

if (recordDateFrom) {
  recordDateFrom.addEventListener("change", () => {
    state.recordDateFrom = recordDateFrom.value;
    reloadRecordsFromFilters();
  });
}

if (recordDateTo) {
  recordDateTo.addEventListener("change", () => {
    state.recordDateTo = recordDateTo.value;
    reloadRecordsFromFilters();
  });
}

if (recordFilterClearButton) {
  recordFilterClearButton.addEventListener("click", () => {
    state.recordStatus = "finished";
    state.recordAuthor = "";
    state.recordDateField = "download";
    state.recordDateFrom = "";
    state.recordDateTo = "";
    localStorage.setItem("clipnest-record-status", state.recordStatus);
    localStorage.setItem("clipnest-record-date-field", state.recordDateField);
    reloadRecordsFromFilters();
  });
}

libraryRefreshButton.addEventListener("click", refreshLibraryInPlace);
libraryEditToggleButton.addEventListener("click", toggleLibraryEditMode);
librarySelectPageButton.addEventListener("click", selectVisibleLibraryItems);
libraryInvertPageButton.addEventListener("click", invertVisibleLibraryItems);
libraryDeleteSelectedButton.addEventListener("click", () => {
  deleteSelectedLibraryItems().catch((error) => {
    summaryEl.textContent = error.message || "删除所选失败";
    renderLibraryManageActions();
  });
});
tasksRefreshButton.addEventListener("click", refreshTasksInPlace);

document.querySelector("#login").addEventListener("click", async () => {
  const token = tokenInput.value.trim();
  if (!token) {
    summaryEl.textContent = "请输入 API Token";
    return;
  }
  try {
    await loginWithToken(token);
    summaryEl.textContent = "已登录";
    refresh();
  } catch (error) {
    summaryEl.textContent = error.message || "登录失败";
  }
});

logoutButton.addEventListener("click", async () => {
  await fetch("/api/session", { method: "DELETE", credentials: "same-origin" });
  state.authenticated = false;
  renderSession();
  summaryEl.textContent = "已退出";
  refresh();
});

tokenInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") document.querySelector("#login").click();
});

submitButton.addEventListener("click", async () => {
  const urls = extractUrls(urlsInput.value);
  if (!state.authenticated) {
    summaryEl.textContent = "请登录";
    return;
  }
  if (!urls.length) {
    summaryEl.textContent = "没有找到链接";
    return;
  }
  try {
    if (urls.length === 1) {
      setSubmitBusy(true, "解析中");
      summaryEl.textContent = "解析清晰度中";
      const preview = await api("/api/parse-preview", {
        method: "POST",
        body: JSON.stringify({ url: urls[0] }),
      });
      renderQualityDialog(preview, { type: "create" });
      summaryEl.textContent = "请选择清晰度";
    } else {
      setSubmitBusy(true, "添加中");
      const result = await api("/api/jobs/batch", {
        method: "POST",
        body: JSON.stringify({ urls }),
      });
      urlsInput.value = "";
      summaryEl.textContent = `${result.count || urls.length} 个任务已加入队列，默认最高清`;
      setView("tasks");
      refresh();
    }
  } catch (error) {
    summaryEl.textContent = error.message || "提交失败";
  } finally {
    setSubmitBusy(false);
  }
});

authorCrawlButton.addEventListener("click", async () => {
  const url = cleanUrl(authorCrawlUrlInput.value);
  const maxItems = authorCrawlMaxItems();
  if (!state.authenticated) {
    summaryEl.textContent = "请登录";
    return;
  }
  if (!url) {
    summaryEl.textContent = "请输入作者主页链接";
    return;
  }
  try {
    setAuthorCrawlBusy(true);
    authorCrawlResultEl.hidden = true;
    summaryEl.textContent = "正在抓取作者作品";
    const result = await api("/api/author-crawls", {
      method: "POST",
      body: JSON.stringify({ url, max_items: maxItems, max_pages: authorCrawlMaxPages(maxItems) }),
    });
    renderAuthorCrawlCreated(result);
    await refresh();
    summaryEl.textContent = result.message || "作者抓取任务已创建";
  } catch (error) {
    summaryEl.textContent = error.message || "抓取作者作品失败";
  } finally {
    setAuthorCrawlBusy(false);
  }
});

async function handleAuthorCrawlAction(event) {
  const moreButton = event.target.closest("[data-dashboard-crawl-more]");
  if (moreButton) {
    setView("sync");
    return;
  }
  const button = event.target.closest("[data-author-crawl-action]");
  if (!button) return;
  const action = button.dataset.authorCrawlAction;
  const crawlId = button.dataset.authorCrawlId;
  if (!action || !crawlId) return;
  const actionLabel = { pause: "暂停", resume: "继续", continue: "续抓", cancel: "取消" }[action] || action;
  try {
    button.disabled = true;
    summaryEl.textContent = `正在${actionLabel}作者抓取任务 #${crawlId}`;
    await api(`/api/author-crawls/${crawlId}/${action}`, { method: "POST" });
    await loadAuthorCrawls();
    renderAuthorCrawls();
    renderSync();
    renderTaskSections();
    summaryEl.textContent = `作者抓取任务 #${crawlId} 已${actionLabel}`;
  } catch (error) {
    summaryEl.textContent = error.message || `${actionLabel}作者抓取任务失败`;
  } finally {
    button.disabled = false;
  }
}

authorCrawlJobsEl.addEventListener("click", handleAuthorCrawlAction);
syncCrawlJobsEl.addEventListener("click", handleAuthorCrawlAction);
taskAuthorCrawlsEl.addEventListener("click", handleAuthorCrawlAction);

urlsInput.addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.key === "Enter") submitButton.click();
});

searchInput.addEventListener("input", () => {
  state.taskSearch = searchInput.value.trim();
  state.tasksPage = 1;
  refresh();
});

statusFilter.addEventListener("change", () => {
  state.statusFilter = statusFilter.value;
  state.tasksPage = 1;
  refresh();
});

taskPlatformTabsEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-task-platform]");
  if (!button) return;
  state.taskPlatform = button.dataset.taskPlatform || "";
  state.tasksPage = 1;
  state.selectedJobIds.clear();
  refreshTasksInPlace();
});

async function cleanupTaskRecords(status, button) {
  const label = status === "failed" ? "失败" : "取消";
  const platformText = state.taskPlatform ? platformLabel(state.taskPlatform) : "全部平台";
  if (!confirm(`清理${platformText}的${label}任务记录？不会删除本地文件。`)) return;
  const originalText = button.textContent;
  try {
    button.disabled = true;
    button.textContent = "清理中";
    const params = new URLSearchParams({ status, delete_file: "false" });
    if (state.taskPlatform) params.set("platform", state.taskPlatform);
    const result = await api(`/api/jobs/cleanup?${params.toString()}`, { method: "POST" });
    state.tasksPage = 1;
    state.selectedJobIds.clear();
    await refreshTasksInPlace();
    summaryEl.textContent = `已清理 ${result.deleted?.length || 0} 条${label}记录`;
  } catch (error) {
    summaryEl.textContent = error.message || `清理${label}记录失败`;
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

tasksClearFailedButton.addEventListener("click", () => cleanupTaskRecords("failed", tasksClearFailedButton));
tasksClearCancelledButton.addEventListener("click", () => cleanupTaskRecords("cancelled", tasksClearCancelledButton));

librarySearchInput.addEventListener("input", () => {
  state.librarySearch = librarySearchInput.value.trim();
  if (state.libraryMode === "authors") {
    state.libraryAuthorsPage = 1;
    loadLibraryPage();
  } else if (state.libraryMode === "records") {
    state.libraryRecordsPage = 1;
    loadLibraryPage();
  } else {
    state.libraryMediaPage = 1;
    reloadLibraryMediaPage();
  }
});

libraryTypeFilter.addEventListener("change", () => {
  state.libraryType = libraryTypeFilter.value;
  state.libraryMediaPage = 1;
  state.libraryRecordsPage = 1;
  if (state.libraryMode === "media") reloadLibraryMediaPage();
  else loadLibraryPage();
});

librarySort.addEventListener("change", () => {
  state.librarySort = librarySort.value || "publish_desc";
  state.libraryMediaPage = 1;
  state.libraryRecordsPage = 1;
  if (state.libraryMode === "media") reloadLibraryMediaPage();
  else loadLibraryPage();
});

syncSearchInput.addEventListener("input", () => {
  state.syncSearch = syncSearchInput.value.trim();
  state.syncAuthorsPage = 1;
  loadSyncPage();
});

if (syncEnabledFilterSelect) {
  syncEnabledFilterSelect.addEventListener("change", () => {
    state.syncEnabledFilter = syncEnabledFilterSelect.value || "";
    localStorage.setItem("clipnest-sync-enabled-filter", state.syncEnabledFilter);
    state.syncAuthorsPage = 1;
    state.selectedSyncSourceIds.clear();
    loadSyncPage();
  });
}

if (syncPageSizeSelect) {
  syncPageSizeSelect.addEventListener("change", () => {
    const parsed = Number(syncPageSizeSelect.value || 12);
    state.syncPageSize = [12, 24, 48].includes(parsed) ? parsed : 12;
    localStorage.setItem("clipnest-sync-page-size", String(state.syncPageSize));
    state.syncAuthorsPage = 1;
    state.selectedSyncSourceIds.clear();
    loadSyncPage();
  });
}

authorCrawlMaxInput.addEventListener("input", () => {
  persistAuthorMaxItems(authorCrawlMaxInput.value);
});

authorCrawlMaxInput.addEventListener("change", () => {
  persistAuthorMaxItems(authorCrawlMaxInput.value, true);
});

syncMaxItemsInput.addEventListener("input", () => {
  persistAuthorMaxItems(syncMaxItemsInput.value);
  renderSyncOverview();
});

syncMaxItemsInput.addEventListener("change", () => {
  persistAuthorMaxItems(syncMaxItemsInput.value, true);
  renderSyncOverview();
});
syncRefreshButton.addEventListener("click", refreshSyncInPlace);
syncJobsRefreshButton.addEventListener("click", async () => {
  try {
    syncJobsRefreshButton.disabled = true;
    syncJobsRefreshButton.textContent = "刷新中";
    await loadAuthorCrawls();
    renderSync();
    summaryEl.textContent = "同步任务已刷新";
  } catch (error) {
    summaryEl.textContent = error.message || "刷新同步任务失败";
  } finally {
    syncJobsRefreshButton.disabled = false;
    syncJobsRefreshButton.textContent = "刷新任务";
  }
});

if (syncJobsCleanupButton) {
  syncJobsCleanupButton.addEventListener("click", async () => {
    if (!confirm("清理已完成、失败、取消的同步任务记录？不会删除媒体库作品。")) return;
    const originalText = syncJobsCleanupButton.textContent;
    try {
      syncJobsCleanupButton.disabled = true;
      syncJobsCleanupButton.textContent = "清理中";
      const result = await api("/api/author-crawls/cleanup?status=finished,failed,cancelled", { method: "POST" });
      await loadAuthorCrawls();
      renderSync();
      renderTaskSections();
      summaryEl.textContent = `已清理 ${result.deleted?.length || 0} 条同步任务记录`;
    } catch (error) {
      summaryEl.textContent = error.message || "清理同步任务失败";
    } finally {
      syncJobsCleanupButton.disabled = false;
      syncJobsCleanupButton.textContent = originalText;
    }
  });
}

async function createSyncSourceTask(sourceId, syncMode = "incremental") {
  return api(`/api/author-sync-sources/${sourceId}/crawl?sync_mode=${encodeURIComponent(syncMode)}`, {
    method: "POST",
  });
}

async function updateSyncSource(sourceId, payload) {
  return api(`/api/author-sync-sources/${sourceId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

async function bulkUpdateSyncSources(payload) {
  return api("/api/author-sync-sources/bulk", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function createAuthorSyncTask(secUid, maxItems, authorName = "", syncMode = "full", sourceId = null) {
  const payload = {
    url: `https://www.douyin.com/user/${secUid}`,
    author_name: authorName,
    sec_uid: secUid,
    max_items: maxItems,
    max_pages: authorCrawlMaxPages(maxItems),
    sync_mode: syncMode,
  };
  if (sourceId) payload.sync_source_id = sourceId;
  return api("/api/author-crawls", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

async function createSyncTasksForSources(button, sources, mode = "incremental") {
  if (!state.authenticated) {
    summaryEl.textContent = "请登录";
    return;
  }
  if (!sources.length) {
    summaryEl.textContent = "没有可同步的作者";
    return;
  }
  if (mode === "full" && !confirm(`全量同步已选 ${sources.length} 个作者？会从作者主页重新扫描更多历史作品。`)) {
    return;
  }
  const originalText = button.textContent;
  try {
    button.disabled = true;
    button.textContent = "创建中";
    const result = await api("/api/author-sync-sources/crawl", {
      method: "POST",
      body: JSON.stringify({
        source_ids: sources.map((item) => Number(item.id)),
        sync_mode: mode,
        enabled_only: true,
      }),
    });
    await loadAuthorCrawls();
    renderSync();
    summaryEl.textContent = result.message || `已创建 ${sources.length} 个同步任务`;
  } catch (error) {
    summaryEl.textContent = error.message || "创建同步任务失败";
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

async function createAllEnabledSyncTasks(button) {
  if (!state.authenticated) {
    summaryEl.textContent = "请登录";
    return;
  }
  const originalText = button.textContent;
  const enabledTotal = Number((state.syncSourceStats || {}).enabled || enabledSyncSources().length || 0);
  if (enabledTotal >= 50 && !confirm(`将为 ${enabledTotal} 个启用作者创建增量同步任务，确定继续？`)) {
    return;
  }
  try {
    button.disabled = true;
    button.textContent = "创建中";
    const result = await api("/api/author-sync-sources/crawl", {
      method: "POST",
      body: JSON.stringify({ source_ids: [], sync_mode: "incremental", enabled_only: true }),
    });
    await loadAuthorCrawls();
    renderSync();
    summaryEl.textContent = result.message || "已创建全部启用作者的同步任务";
  } catch (error) {
    summaryEl.textContent = error.message || "同步全部启用作者失败";
  } finally {
    button.disabled = false;
    button.textContent = originalText;
  }
}

syncRunEnabledButton.addEventListener("click", () => createAllEnabledSyncTasks(syncRunEnabledButton));

syncSelectPageButton.addEventListener("click", () => {
  for (const id of visibleSyncSourceIds()) state.selectedSyncSourceIds.add(String(id));
  renderSync();
});

syncInvertPageButton.addEventListener("click", () => {
  for (const id of visibleSyncSourceIds()) {
    if (state.selectedSyncSourceIds.has(String(id))) state.selectedSyncSourceIds.delete(String(id));
    else state.selectedSyncSourceIds.add(String(id));
  }
  renderSync();
});

if (syncClearSelectionButton) {
  syncClearSelectionButton.addEventListener("click", () => {
    state.selectedSyncSourceIds.clear();
    renderSync();
  });
}

if (syncApplyDefaultsButton) {
  syncApplyDefaultsButton.addEventListener("click", async () => {
    const ids = Array.from(state.selectedSyncSourceIds).map(Number);
    if (!ids.length) return;
    const maxItems = syncMaxItems();
    if (!confirm(`将默认同步参数应用到已选 ${ids.length} 个作者？\n最多作品：${maxItems}\n模式：增量\n图集：不下载`)) return;
    const originalText = syncApplyDefaultsButton.textContent;
    try {
      syncApplyDefaultsButton.disabled = true;
      syncApplyDefaultsButton.textContent = "应用中";
      const result = await bulkUpdateSyncSources({
        source_ids: ids,
        sync_mode: "incremental",
        max_items: maxItems,
        include_images: false,
      });
      await loadSyncPage();
      summaryEl.textContent = `已更新 ${result.updated?.length || 0} 个作者的默认同步参数`;
    } catch (error) {
      summaryEl.textContent = error.message || "应用默认参数失败";
    } finally {
      syncApplyDefaultsButton.disabled = false;
      syncApplyDefaultsButton.textContent = originalText;
    }
  });
}

syncEnableSelectedButton.addEventListener("click", async () => {
  const ids = Array.from(state.selectedSyncSourceIds).map(Number);
  if (!ids.length) return;
  try {
    syncEnableSelectedButton.disabled = true;
    const result = await bulkUpdateSyncSources({ source_ids: ids, enabled: true });
    await loadSyncPage();
    summaryEl.textContent = `已启用 ${result.updated?.length || 0} 个作者`;
  } catch (error) {
    summaryEl.textContent = error.message || "批量启用失败";
  }
});

syncDisableSelectedButton.addEventListener("click", async () => {
  const ids = Array.from(state.selectedSyncSourceIds).map(Number);
  if (!ids.length) return;
  try {
    syncDisableSelectedButton.disabled = true;
    const result = await bulkUpdateSyncSources({ source_ids: ids, enabled: false });
    await loadSyncPage();
    summaryEl.textContent = `已停用 ${result.updated?.length || 0} 个作者`;
  } catch (error) {
    summaryEl.textContent = error.message || "批量停用失败";
  }
});

syncRunSelectedButton.addEventListener("click", () => {
  const selected = new Set(Array.from(state.selectedSyncSourceIds).map(String));
  const sources = (state.syncSources || []).filter((item) => selected.has(String(item.id)) && item.enabled);
  createSyncTasksForSources(syncRunSelectedButton, sources, "incremental");
});

if (syncRunSelectedFullButton) {
  syncRunSelectedFullButton.addEventListener("click", () => {
    const selected = new Set(Array.from(state.selectedSyncSourceIds).map(String));
    const sources = (state.syncSources || []).filter((item) => selected.has(String(item.id)) && item.enabled);
    createSyncTasksForSources(syncRunSelectedFullButton, sources, "full");
  });
}

syncDeleteSelectedButton.addEventListener("click", async () => {
  const ids = Array.from(state.selectedSyncSourceIds).map(Number);
  if (!ids.length || !confirm(`删除已选 ${ids.length} 个同步源？不会删除媒体库作品。`)) return;
  try {
    syncDeleteSelectedButton.disabled = true;
    const result = await bulkUpdateSyncSources({ source_ids: ids, delete: true });
    state.selectedSyncSourceIds.clear();
    await loadSyncPage();
    summaryEl.textContent = `已删除 ${result.deleted?.length || 0} 个同步源`;
  } catch (error) {
    summaryEl.textContent = error.message || "批量删除同步源失败";
  }
});

syncImportLibraryButton.addEventListener("click", async () => {
  try {
    syncImportLibraryButton.disabled = true;
    syncImportLibraryButton.textContent = "导入中";
    const result = await api("/api/author-sync-sources/import-library?platform=douyin", { method: "POST" });
    await loadSyncPage();
    summaryEl.textContent = `导入完成：新增 ${result.created || 0}，更新 ${result.updated || 0}，跳过 ${result.skipped || 0}`;
  } catch (error) {
    summaryEl.textContent = error.message || "导入媒体库作者失败";
  } finally {
    syncImportLibraryButton.disabled = false;
    syncImportLibraryButton.textContent = "导入媒体库作者";
  }
});

syncSourceAddButton.addEventListener("click", async () => {
  const url = syncSourceUrlInput.value.trim();
  const authorName = syncSourceNameInput.value.trim();
  if (!url) {
    summaryEl.textContent = "请先填写作者主页链接";
    return;
  }
  try {
    syncSourceAddButton.disabled = true;
    syncSourceAddButton.textContent = "保存中";
    const maxItems = syncMaxItems();
    const result = await api("/api/author-sync-sources", {
      method: "POST",
      body: JSON.stringify({
        url,
        author_name: authorName,
        platform: "douyin",
        enabled: true,
        sync_mode: "incremental",
        max_items: maxItems,
        max_pages: authorCrawlMaxPages(maxItems),
        include_images: false,
      }),
    });
    syncSourceUrlInput.value = "";
    syncSourceNameInput.value = "";
    state.syncAuthorsPage = 1;
    await loadSyncPage();
    summaryEl.textContent = result.message || "作者同步源已保存";
  } catch (error) {
    summaryEl.textContent = error.message || "保存作者同步源失败";
  } finally {
    syncSourceAddButton.disabled = false;
    syncSourceAddButton.textContent = "添加";
  }
});

syncAuthorsEl.addEventListener("click", async (event) => {
  const selector = event.target.closest("[data-sync-source-select]");
  if (selector) {
    toggleSyncSourceSelection(selector.dataset.syncSourceSelect, selector.checked);
    return;
  }
  const detailButton = event.target.closest("[data-sync-source-detail]");
  if (detailButton) {
    const sourceId = Number(detailButton.dataset.syncSourceDetail || 0);
    if (!sourceId) return;
    const originalText = detailButton.textContent;
    try {
      detailButton.disabled = true;
      detailButton.textContent = "加载中";
      state.syncDetail = await api(`/api/author-sync-sources/${sourceId}?history_limit=30`);
      renderSyncDetail();
      summaryEl.textContent = "同步历史已加载";
    } catch (error) {
      summaryEl.textContent = error.message || "加载同步历史失败";
    } finally {
      detailButton.disabled = false;
      detailButton.textContent = originalText;
    }
    return;
  }
  const viewButton = event.target.closest("[data-sync-author]");
  if (viewButton) {
    setLibraryPlatform("douyin");
    state.libraryAuthor = viewButton.dataset.syncAuthor || "";
    setLibraryMode("media");
    state.librarySort = "publish_desc";
    state.libraryMediaPage = 1;
    setView("library");
    return;
  }
  const toggleButton = event.target.closest("[data-sync-source-toggle]");
  if (toggleButton) {
    const sourceId = Number(toggleButton.dataset.syncSourceToggle || 0);
    const source = state.syncSources.find((item) => Number(item.id) === sourceId);
    if (!source) return;
    const originalText = toggleButton.textContent;
    try {
      toggleButton.disabled = true;
      toggleButton.textContent = "保存中";
      const result = await updateSyncSource(sourceId, { enabled: !source.enabled });
      await loadSyncPage();
      summaryEl.textContent = result.message || "同步源已更新";
    } catch (error) {
      summaryEl.textContent = error.message || "更新同步源失败";
    } finally {
      toggleButton.disabled = false;
      toggleButton.textContent = originalText;
    }
    return;
  }
  const deleteButton = event.target.closest("[data-sync-source-delete]");
  if (deleteButton) {
    const sourceId = Number(deleteButton.dataset.syncSourceDelete || 0);
    if (!sourceId || !confirm("删除这个同步源？不会删除媒体库作品。")) return;
    try {
      deleteButton.disabled = true;
      await api(`/api/author-sync-sources/${sourceId}`, { method: "DELETE" });
      await loadSyncPage();
      summaryEl.textContent = "同步源已删除";
    } catch (error) {
      summaryEl.textContent = error.message || "删除同步源失败";
    } finally {
      deleteButton.disabled = false;
    }
    return;
  }
  const syncButton = event.target.closest("[data-sync-source-run]");
  if (!syncButton || syncButton.disabled) return;
  const sourceId = Number(syncButton.dataset.syncSourceRun || 0);
  const source = state.syncSources.find((item) => Number(item.id) === sourceId) || {};
  const author = source.author_name || "该作者";
  const syncMode = syncButton.dataset.syncSourceMode || "incremental";
  const modeLabel = syncMode === "incremental" ? "增量" : "全量";
  const originalText = syncButton.textContent;
  try {
    syncButton.disabled = true;
    syncButton.textContent = "创建中";
    const result = await createSyncSourceTask(sourceId, syncMode);
    await loadAuthorCrawls();
    renderSync();
    summaryEl.textContent = result.message || `${author} 的${modeLabel}同步任务已创建`;
  } catch (error) {
    summaryEl.textContent = error.message || `创建${modeLabel}同步任务失败`;
  } finally {
    syncButton.disabled = false;
    syncButton.textContent = originalText;
  }
});

if (syncDetailEl) {
  syncDetailEl.addEventListener("click", (event) => {
    if (!event.target.closest("[data-sync-detail-close]")) return;
    state.syncDetail = null;
    renderSyncDetail();
  });
}

syncAuthorsEl.addEventListener("change", async (event) => {
  const field = event.target.closest("[data-sync-source-field]");
  if (!field) return;
  const sourceId = Number(field.dataset.syncSourceId || 0);
  const name = field.dataset.syncSourceField || "";
  if (!sourceId || !name) return;
  const value = field.type === "checkbox" ? field.checked : field.type === "number" ? Number(field.value || 0) : field.value;
  try {
    field.disabled = true;
    await updateSyncSource(sourceId, { [name]: value });
    await loadSyncPage();
    summaryEl.textContent = "同步源配置已保存";
  } catch (error) {
    summaryEl.textContent = error.message || "保存同步源配置失败";
  } finally {
    field.disabled = false;
  }
});

libraryClearButton.addEventListener("click", () => {
  state.libraryAuthor = "";
  state.libraryAuthorDetail = null;
  state.libraryMediaPage = 1;
  reloadLibraryMediaPage();
});

if (libraryPlayModeButton) {
  libraryPlayModeButton.addEventListener("click", async () => {
    try {
      libraryPlayModeButton.disabled = true;
      libraryPlayModeButton.textContent = "加载中";
      await openReel();
    } catch (error) {
      summaryEl.textContent = error.message || "播放模式加载失败";
    } finally {
      libraryPlayModeButton.disabled = false;
      libraryPlayModeButton.textContent = "播放模式";
    }
  });
}

authorsEl.addEventListener("click", (event) => {
  const moreButton = event.target.closest("[data-dashboard-authors-more]");
  if (moreButton) {
    setLibraryMode("authors");
    state.libraryAuthorsPage = 1;
    setView("library");
    return;
  }
  const button = event.target.closest("[data-author]");
  if (!button) return;
  state.authorFilter = button.dataset.author || "";
  state.tasksPage = 1;
  refresh();
});

if (dashboardRecentEl) {
  dashboardRecentEl.addEventListener("click", (event) => {
    const button = event.target.closest("[data-dashboard-job]");
    if (!button) return;
    openJobDetail(button.dataset.dashboardJob);
  });
}

libraryAuthorsEl.addEventListener("click", (event) => {
  const selector = event.target.closest("[data-library-author-select]");
  if (selector) {
    toggleLibrarySelection(selector.dataset.libraryAuthorSelect, selector.checked);
    return;
  }
  const button = event.target.closest("[data-library-author]");
  if (!button) return;
  if (state.libraryEditMode) {
    toggleLibrarySelection(button.dataset.libraryAuthor || "");
    return;
  }
  state.libraryAuthor = button.dataset.libraryAuthor || "";
  setLibraryMode("media");
  state.librarySort = "publish_desc";
  state.libraryMediaPage = 1;
  loadLibraryPage();
});

libraryAuthorDetailEl.addEventListener("click", async (event) => {
  const createSyncSourceButton = event.target.closest("[data-create-sync-source-author]");
  if (createSyncSourceButton) {
    const author = createSyncSourceButton.dataset.createSyncSourceAuthor || state.libraryAuthor || "";
    const secUid = createSyncSourceButton.dataset.createSyncSourceSecUid || "";
    if (!secUid) {
      summaryEl.textContent = "该作者缺少主页 ID，暂时不能保存同步源";
      return;
    }
    try {
      createSyncSourceButton.disabled = true;
      createSyncSourceButton.textContent = "保存中";
      const maxItems = syncMaxItems();
      await api("/api/author-sync-sources", {
        method: "POST",
        body: JSON.stringify({
          url: `https://www.douyin.com/user/${secUid}`,
          author_name: author,
          sec_uid: secUid,
          platform: "douyin",
          enabled: true,
          sync_mode: "incremental",
          max_items: maxItems,
          max_pages: authorCrawlMaxPages(maxItems),
          include_images: false,
        }),
      });
      await loadLibraryPage();
      summaryEl.textContent = `${author} 已保存为同步源`;
    } catch (error) {
      summaryEl.textContent = error.message || "保存同步源失败";
    } finally {
      createSyncSourceButton.disabled = false;
      createSyncSourceButton.textContent = "保存为同步源";
    }
    return;
  }
  const openSyncSourceButton = event.target.closest("[data-open-sync-source]");
  if (openSyncSourceButton) {
    state.syncSearch = state.libraryAuthor || "";
    syncSearchInput.value = state.syncSearch;
    state.syncAuthorsPage = 1;
    setView("sync");
    return;
  }
  const authorCrawlButton = event.target.closest("[data-author-crawl-sec-uid]");
  if (authorCrawlButton) {
    const secUid = authorCrawlButton.dataset.authorCrawlSecUid || "";
    if (!secUid) return;
    try {
      authorCrawlButton.disabled = true;
      summaryEl.textContent = "正在创建作者更新任务";
      const maxItems = authorCrawlMaxItems();
      const result = await api("/api/author-crawls", {
        method: "POST",
        body: JSON.stringify({
          url: `https://www.douyin.com/user/${secUid}`,
          author_name: state.libraryAuthor || "",
          max_items: maxItems,
          max_pages: authorCrawlMaxPages(maxItems),
          sync_mode: "incremental",
        }),
      });
      renderAuthorCrawlCreated(result);
      await loadAuthorCrawls();
      renderAuthorCrawls();
      summaryEl.textContent = result.message || "作者更新任务已创建，可在工作台查看进度";
    } catch (error) {
      summaryEl.textContent = error.message || "创建作者更新任务失败";
    } finally {
      authorCrawlButton.disabled = false;
    }
    return;
  }
  const authorTaskButton = event.target.closest("[data-library-author-tasks]");
  if (authorTaskButton) {
    state.authorFilter = authorTaskButton.dataset.libraryAuthorTasks || "";
    state.taskPlatform = state.libraryPlatform || "";
    state.tasksPage = 1;
    setView("tasks");
    refresh();
    return;
  }
  if (event.target.closest("[data-library-clear-author]")) {
    state.libraryAuthor = "";
    state.libraryAuthorDetail = null;
    state.libraryMediaPage = 1;
    reloadLibraryMediaPage();
  }
});

async function handleLibraryPageClick(event) {
  const button = event.target.closest("[data-library-page]");
  if (!button || button.disabled) return;
  const delta = Number(button.dataset.pageDelta || 0);
  const kind = ["authors", "records"].includes(button.dataset.libraryPage) ? button.dataset.libraryPage : "media";
  if (kind === "authors") {
    state.libraryAuthorsPage += delta;
  } else if (kind === "records") {
    state.libraryRecordsPage += delta;
  } else {
    const targetPage = activeLibraryMediaPage() + delta;
    await loadLibraryMediaPage(targetPage, { direction: delta });
    return;
  }
  showLibraryLoading(kind);
  await loadLibraryPage();
}

libraryAuthorsPaginationEl.addEventListener("click", handleLibraryPageClick);
libraryMediaPaginationEl.addEventListener("click", handleLibraryPageClick);
libraryRecordsPaginationEl.addEventListener("click", handleLibraryPageClick);
document.querySelectorAll(".gallery-page[data-library-page='media']").forEach((button) => {
  button.addEventListener("click", handleLibraryPageClick);
});
syncAuthorsPaginationEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-library-page]");
  if (!button || button.disabled) return;
  state.syncAuthorsPage += Number(button.dataset.pageDelta || 0);
  loadSyncPage();
});
tasksPaginationEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-library-page]");
  if (!button || button.disabled) return;
  state.tasksPage += Number(button.dataset.pageDelta || 0);
  refresh();
});
if (logsPaginationEl) {
  logsPaginationEl.addEventListener("click", (event) => {
    const button = event.target.closest("[data-library-page]");
    if (!button || button.disabled) return;
    state.logsPage += Number(button.dataset.pageDelta || 0);
    loadLogsPage();
  });
}

libraryMediaEl.addEventListener("click", (event) => {
  const selector = event.target.closest("[data-library-media-select]");
  if (selector) {
    toggleLibrarySelection(selector.dataset.libraryMediaSelect, selector.checked);
    return;
  }
  const card = event.target.closest("[data-media-job]");
  if (!card) return;
  if (state.libraryEditMode) {
    toggleLibrarySelection(card.dataset.mediaJob);
    return;
  }
  openMediaPreview(card.dataset.mediaJob);
});

libraryRecordsEl.addEventListener("click", async (event) => {
  const selector = event.target.closest("[data-library-record-select]");
  if (selector) {
    toggleLibrarySelection(selector.dataset.libraryRecordSelect, selector.checked);
    return;
  }
  const previewButton = event.target.closest("[data-record-preview]");
  if (previewButton) {
    openMediaPreview(previewButton.dataset.recordPreview);
    return;
  }
  const detailButton = event.target.closest("[data-open-detail]");
  if (detailButton) {
    openJobDetail(detailButton.dataset.openDetail);
    return;
  }
  const copyButton = event.target.closest("[data-record-copy]");
  if (copyButton) {
    try {
      const ok = await copyText(copyButton.dataset.recordCopy || "");
      summaryEl.textContent = ok ? "已复制" : "复制失败，请手动复制";
    } catch (error) {
      summaryEl.textContent = error.message || "复制失败";
    }
    return;
  }
  const restoreButton = event.target.closest("[data-record-restore]");
  if (restoreButton) {
    const recordId = restoreButton.dataset.recordRestore;
    if (!recordId || !confirm("恢复这条已删除记录？恢复后作者同步可能会重新加入该作品。")) return;
    try {
      restoreButton.disabled = true;
      restoreButton.textContent = "恢复中";
      await api(`/api/library/deleted/${recordId}`, { method: "DELETE" });
      clearLibraryMediaCache();
      await loadLibraryPage();
      summaryEl.textContent = "已恢复同步，不再跳过该作品";
    } catch (error) {
      summaryEl.textContent = error.message || "恢复同步失败";
    } finally {
      restoreButton.disabled = false;
      restoreButton.textContent = "恢复同步";
    }
    return;
  }
  const deleteButton = event.target.closest("[data-record-delete]");
  if (!deleteButton) return;
  const jobId = deleteButton.dataset.recordDelete;
  if (!confirm("删除这个作品和本地文件？删除后同步会跳过该视频。")) return;
  try {
    deleteButton.disabled = true;
    deleteButton.textContent = "删除中";
    await api(`/api/jobs/${jobId}?delete_file=true`, { method: "DELETE" });
    clearLibraryMediaCache();
    await loadLibraryPage();
    summaryEl.textContent = "作品已删除，并加入已删除记录";
  } catch (error) {
    summaryEl.textContent = error.message || "删除作品失败";
    deleteButton.disabled = false;
    deleteButton.textContent = "删除";
  }
});

async function handleJobAction(event) {
  const selector = event.target.closest("[data-select]");
  if (selector) {
    const id = String(selector.getAttribute("data-select"));
    if (selector.checked) state.selectedJobIds.add(id);
    else state.selectedJobIds.delete(id);
    renderBulkActions();
    return;
  }
  const button = event.target.closest("button");
  if (!button) {
    if (event.target.closest("a")) return;
    const card = event.target.closest("[data-job-id]");
    if (card) openJobDetail(card.dataset.jobId);
    return;
  }
  const retry = button.getAttribute("data-retry");
  const force = button.getAttribute("data-force");
  const cancelId = button.getAttribute("data-cancel");
  const deleteId = button.getAttribute("data-delete");
  if (!retry && !force && !cancelId && !deleteId) return;
  try {
    if (retry) {
      await openRetryQualityDialog(retry, false);
      return;
    }
    if (force) {
      await openRetryQualityDialog(force, true);
      return;
    }
    if (cancelId) {
      if (!confirm("取消这个正在运行的任务？")) return;
      await api(`/api/jobs/${cancelId}/cancel`, { method: "POST" });
      summaryEl.textContent = "已请求取消";
    }
    if (deleteId) {
      if (!confirm("只删除这个任务记录？本地文件不会删除。")) return;
      await api(`/api/jobs/${deleteId}`, { method: "DELETE" });
      summaryEl.textContent = "任务记录已删除";
    }
    refresh();
  } catch (error) {
    summaryEl.textContent = error.message || "操作失败";
  }
}

jobsEl.addEventListener("click", handleJobAction);
activeJobsEl.addEventListener("click", handleJobAction);

tasksSelectAllButton.addEventListener("click", selectVisibleTasks);
tasksInvertSelectionButton.addEventListener("click", invertVisibleTasks);
tasksClearSelectionButton.addEventListener("click", clearTaskSelection);

bulkRetryButton.addEventListener("click", async () => {
  try {
    await runBulkAction("/api/jobs/bulk/retry", { force: false }, "批量重试已提交");
  } catch (error) {
    summaryEl.textContent = error.message || "批量重试失败";
  }
});

bulkRedownloadButton.addEventListener("click", async () => {
  if (!confirm("批量重下会删除已选任务的当前文件，继续吗？")) return;
  try {
    await runBulkAction("/api/jobs/bulk/retry", { force: true }, "批量重下已提交");
  } catch (error) {
    summaryEl.textContent = error.message || "批量重下失败";
  }
});

bulkCancelButton.addEventListener("click", async () => {
  if (!confirm("取消已选任务？")) return;
  try {
    await runBulkAction("/api/jobs/bulk/cancel", {}, "批量取消已提交");
  } catch (error) {
    summaryEl.textContent = error.message || "批量取消失败";
  }
});

bulkDeleteButton.addEventListener("click", async () => {
  if (!confirm("只删除已选任务记录？本地文件不会删除。")) return;
  try {
    await runBulkAction("/api/jobs/bulk/delete", { delete_file: false }, "批量任务记录已删除");
  } catch (error) {
    summaryEl.textContent = error.message || "批量删除失败";
  }
});

qualityCloseButton.addEventListener("click", closeOverlay);
mediaPreviewCloseButton.addEventListener("click", closeOverlay);
drawerScrimEl.addEventListener("click", closeOverlay);
document.querySelector("#drawer-close").addEventListener("click", closeOverlay);

qualityOptionsEl.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-quality]");
  if (!button || !state.pendingQualityPreview) return;
  const quality = button.getAttribute("data-quality") || "best";
  const action = state.pendingQualityAction || { type: "create" };
  try {
    setQualityBusy(true);
    summaryEl.textContent = action.type === "retry" ? "加入重试队列中" : "加入下载队列中";
    if (action.type === "retry") {
      await api(`/api/jobs/${action.jobId}/retry`, {
        method: "POST",
        body: JSON.stringify({
          force: Boolean(action.force),
          quality_preference: quality,
          parse_cache_id: state.pendingQualityPreview.parse_cache_id,
        }),
      });
    } else {
      await api("/api/jobs", {
        method: "POST",
        body: JSON.stringify({
          url: state.pendingQualityPreview.url,
          quality_preference: quality,
          parse_cache_id: state.pendingQualityPreview.parse_cache_id,
        }),
      });
    }
    urlsInput.value = "";
    closeOverlay();
    const qualityText = quality === "best" ? "最高" : `${quality}P`;
    summaryEl.textContent = action.type === "retry"
      ? `已按 ${qualityText} 加入重试队列`
      : `已按 ${qualityText} 加入队列`;
    setView("tasks");
    refresh();
  } catch (error) {
    setQualityBusy(false);
    summaryEl.textContent = error.message || "加入队列失败";
  }
});

drawerBodyEl.addEventListener("click", async (event) => {
  const copyButton = event.target.closest("[data-copy-value]");
  const refreshButton = event.target.closest("[data-refresh-metadata]");
  const retryButton = event.target.closest("[data-retry]");
  const forceButton = event.target.closest("[data-force]");
  if (copyButton) {
    try {
      await navigator.clipboard.writeText(copyButton.getAttribute("data-copy-value") || "");
      summaryEl.textContent = "路径已复制";
    } catch (_) {
      summaryEl.textContent = "复制失败";
    }
    return;
  }
  if (refreshButton) {
    const jobId = refreshButton.getAttribute("data-refresh-metadata");
    try {
      refreshButton.disabled = true;
      refreshButton.textContent = "刷新中";
      summaryEl.textContent = "正在重新解析";
      const result = await api(`/api/jobs/${jobId}/refresh-metadata`, { method: "POST" });
      const [job, media, events] = await Promise.all([
        api(`/api/jobs/${jobId}`),
        api(`/api/jobs/${jobId}/media`),
        api(`/api/jobs/${jobId}/events`),
      ]);
      renderJobDetail(job, media, events);
      summaryEl.textContent = refreshSummaryText(result);
      refresh();
    } catch (error) {
      refreshButton.disabled = false;
      refreshButton.textContent = "刷新解析";
      summaryEl.textContent = error.message || "刷新解析失败";
    }
    return;
  }
  if (retryButton) {
    await openRetryQualityDialog(retryButton.getAttribute("data-retry"), false);
    return;
  }
  if (forceButton) {
    await openRetryQualityDialog(forceButton.getAttribute("data-force"), true);
  }
});

mediaPreviewBodyEl.addEventListener("click", async (event) => {
  const reelButton = event.target.closest("[data-reel-start]");
  if (reelButton) {
    const jobId = reelButton.dataset.reelStart;
    closeMediaPreviewOnly();
    openReel(jobId).catch((error) => {
      summaryEl.textContent = error.message || "播放模式加载失败";
    });
    return;
  }
  const authorButton = event.target.closest("[data-view-author-media]");
  if (authorButton) {
    if (authorButton.dataset.viewAuthorPlatform) {
      setLibraryPlatform(authorButton.dataset.viewAuthorPlatform);
    }
    openAuthorMedia(authorButton.dataset.viewAuthorMedia, "video");
    return;
  }
  const button = event.target.closest("[data-open-detail]");
  if (!button) return;
  closeMediaPreviewOnly();
  openJobDetail(button.dataset.openDetail);
});

reelCloseButton.addEventListener("click", closeReel);
reelPrevButton.addEventListener("click", () => stepReel(-1));
reelNextButton.addEventListener("click", () => stepReel(1));
reelDeleteButton.addEventListener("click", () => {
  deleteCurrentReelJob().catch((error) => {
    summaryEl.textContent = error.message || "删除当前视频失败";
  });
});
reelViewerEl.addEventListener("wheel", (event) => {
  if (reelViewerEl.hidden) return;
  event.preventDefault();
  if (Math.abs(event.deltaY) < 16) return;
  stepReel(event.deltaY > 0 ? 1 : -1);
}, { passive: false });
reelViewerEl.addEventListener("touchstart", (event) => {
  state.reelTouchStartY = event.touches && event.touches[0] ? event.touches[0].clientY : 0;
}, { passive: true });
reelViewerEl.addEventListener("touchend", (event) => {
  const endY = event.changedTouches && event.changedTouches[0] ? event.changedTouches[0].clientY : state.reelTouchStartY;
  const delta = state.reelTouchStartY - endY;
  if (Math.abs(delta) > 40) stepReel(delta > 0 ? 1 : -1);
}, { passive: true });
window.addEventListener("resize", () => {
  if (!reelViewerEl.hidden) fitReelStage();
});

settingsSaveButton.addEventListener("click", saveSettings);
telegramTestButton.addEventListener("click", testTelegramSettings);
parserHealthButton.addEventListener("click", async () => {
  try {
    parserInfoEl.textContent = "检查中";
    const health = await api("/api/parser/health");
    renderParserInfo(health);
    summaryEl.textContent = health.ok ? "解析器正常" : (health.error || "解析器异常");
  } catch (error) {
    summaryEl.textContent = error.message || "检查失败";
  }
});

maintenanceHealthButton.addEventListener("click", async () => {
  try {
    showHealthOutput(await api("/api/health"));
  } catch (error) {
    summaryEl.textContent = error.message || "健康检查失败";
  }
});

maintenanceCookieButton.addEventListener("click", async () => {
  try {
    showCookieOutput(await api("/api/cookie/health"));
  } catch (error) {
    summaryEl.textContent = error.message || "Cookie 状态检查失败";
  }
});

if (maintenanceTikTokButton) {
  maintenanceTikTokButton.addEventListener("click", async () => {
    try {
      showTikTokDiagnostics(await api("/api/tiktok/diagnostics"));
    } catch (error) {
      summaryEl.textContent = error.message || "TikTok 诊断失败";
    }
  });
}

maintenanceEventsButton.addEventListener("click", async () => {
  try {
    showEventsOutput(await api("/api/maintenance/events?limit=80"));
  } catch (error) {
    summaryEl.textContent = error.message || "最近事件加载失败";
  }
});

maintenanceExportButton.addEventListener("click", async () => {
  try {
    const config = await api("/api/maintenance/config");
    downloadJson(`clipnest-config-${Date.now()}.json`, config);
    showConfigOutput(config);
  } catch (error) {
    summaryEl.textContent = error.message || "配置导出失败";
  }
});

maintenanceBackupButton.addEventListener("click", () => {
  const tokenQuery = state.token ? `?token=${encodeURIComponent(state.token)}` : "";
  window.open(`/api/maintenance/backup${tokenQuery}`, "_blank");
});

maintenanceCacheAssetsButton.addEventListener("click", async () => {
  try {
    summaryEl.textContent = "正在缓存封面和头像";
    showAssetCacheOutput(await api("/api/maintenance/cache-assets?limit=500", { method: "POST" }));
    refresh();
  } catch (error) {
    summaryEl.textContent = error.message || "缓存封面头像失败";
  }
});

maintenanceDuplicatesButton.addEventListener("click", async () => {
  try {
    showDuplicatesOutput(await api("/api/maintenance/duplicates?limit=100"));
  } catch (error) {
    summaryEl.textContent = error.message || "扫描重复作品失败";
  }
});

maintenanceCleanDuplicatesButton.addEventListener("click", async () => {
  if (!confirm("清理重复任务记录？本地视频文件不会删除。")) return;
  try {
    showDuplicatesOutput(await api("/api/maintenance/duplicates/cleanup?limit=500", { method: "POST" }), true);
    refresh();
  } catch (error) {
    summaryEl.textContent = error.message || "清理重复记录失败";
  }
});

maintenanceOrphansButton.addEventListener("click", async () => {
  try {
    showOrphansOutput(await api("/api/maintenance/orphans"));
  } catch (error) {
    summaryEl.textContent = error.message || "扫描孤儿文件失败";
  }
});

maintenanceCleanOrphansButton.addEventListener("click", async () => {
  if (!confirm("清理数据库未引用的下载目录文件？")) return;
  try {
    showOrphansOutput(await api("/api/maintenance/orphans?delete=true"), true);
  } catch (error) {
    summaryEl.textContent = error.message || "清理孤儿文件失败";
  }
});

document.addEventListener("keydown", (event) => {
  if (!reelViewerEl.hidden) {
    if (event.key === "Escape") {
      closeReel();
      return;
    }
    if (event.key === "ArrowDown" || event.key === "PageDown") {
      event.preventDefault();
      stepReel(1);
      return;
    }
    if (event.key === "ArrowUp" || event.key === "PageUp") {
      event.preventDefault();
      stepReel(-1);
      return;
    }
    if (event.key === "Delete") {
      event.preventDefault();
      deleteCurrentReelJob().catch((error) => {
        summaryEl.textContent = error.message || "删除当前视频失败";
      });
      return;
    }
  }
  if (event.key === "Escape" && (!drawerEl.hidden || !qualityDialogEl.hidden || !mediaPreviewDialogEl.hidden)) closeOverlay();
});

async function bootstrap() {
  setView(state.currentView);
  const sessionOk = await checkSession();
  if (!sessionOk && state.token) {
    try {
      await loginWithToken(state.token);
      summaryEl.textContent = "已登录";
    } catch (_) {
      state.authenticated = false;
      renderSession();
    }
  }
  refresh();
}

setInterval(refresh, 2500);
bootstrap();
