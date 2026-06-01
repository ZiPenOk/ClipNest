const state = {
  token: localStorage.getItem("clipnest-token") || document.querySelector("#token").value || "",
  authenticated: false,
  currentView: ["dashboard", "library", "tasks", "settings"].includes(localStorage.getItem("clipnest-view"))
    ? localStorage.getItem("clipnest-view")
    : "dashboard",
  jobs: [],
  activeJobs: [],
  authorCrawls: [],
  tasksPage: 1,
  tasksTotal: 0,
  tasksTotalPages: 1,
  stats: null,
  authors: [],
  libraryAuthors: [],
  libraryAuthorsTotal: 0,
  libraryAuthorsTotalPages: 1,
  libraryMediaJobs: [],
  libraryMediaTotal: 0,
  libraryMediaTotalPages: 1,
  libraryAuthorDetail: null,
  selectedJobIds: new Set(),
  taskSearch: "",
  statusFilter: "",
  authorFilter: "",
  librarySearch: "",
  libraryMode: ["authors", "media"].includes(localStorage.getItem("clipnest-library-mode"))
    ? localStorage.getItem("clipnest-library-mode")
    : "authors",
  libraryAuthor: "",
  libraryType: "",
  librarySort: "newest",
  libraryAuthorsPage: 1,
  libraryMediaPage: 1,
  pendingQualityPreview: null,
  pendingQualityAction: null,
};

const libraryAuthorsPageSize = 24;
const libraryMediaPageSize = 30;
const tasksPageSize = 50;

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
const activeJobsEl = document.querySelector("#active-jobs");
const librarySectionTitle = document.querySelector("#library-section-title");
const libraryAuthorsPanel = document.querySelector("#library-authors-panel");
const libraryMediaPanel = document.querySelector("#library-media-panel");
const libraryAuthorsEl = document.querySelector("#library-authors");
const libraryAuthorsPaginationEl = document.querySelector("#library-authors-pagination");
const libraryAuthorDetailEl = document.querySelector("#library-author-detail");
const libraryMediaEl = document.querySelector("#library-media");
const libraryMediaPaginationEl = document.querySelector("#library-media-pagination");
const librarySearchInput = document.querySelector("#library-search");
const libraryTypeFilter = document.querySelector("#library-type-filter");
const librarySort = document.querySelector("#library-sort");
const libraryClearButton = document.querySelector("#library-clear");
const libraryRefreshButton = document.querySelector("#library-refresh");
const libraryFilterLabel = document.querySelector("#library-filter-label");
const searchInput = document.querySelector("#search");
const statusFilter = document.querySelector("#status-filter");
const tasksRefreshButton = document.querySelector("#tasks-refresh");
const authorsEl = document.querySelector("#authors");
const jobsEl = document.querySelector("#jobs");
const tasksPaginationEl = document.querySelector("#tasks-pagination");
const bulkActionsEl = document.querySelector("#bulk-actions");
const bulkCountEl = document.querySelector("#bulk-count");
const bulkRetryButton = document.querySelector("#bulk-retry");
const bulkRedownloadButton = document.querySelector("#bulk-redownload");
const bulkCancelButton = document.querySelector("#bulk-cancel");
const bulkDeleteButton = document.querySelector("#bulk-delete");
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
const settingDouyinUserAgent = document.querySelector("#setting-douyin-user-agent");
const parserInfoEl = document.querySelector("#parser-info");
const parserHealthButton = document.querySelector("#parser-health");
const settingsSaveButton = document.querySelector("#settings-save");
const settingsSaveStatus = document.querySelector("#settings-save-status");
const maintenanceHealthButton = document.querySelector("#maintenance-health");
const maintenanceCookieButton = document.querySelector("#maintenance-cookie");
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

function cleanUrl(value) {
  return String(value || "").trim().replace(/[.,;)\uFF0C\u3002\uFF1B]+$/g, "");
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

function setView(view) {
  if (!["dashboard", "library", "tasks", "settings"].includes(view)) view = "dashboard";
  state.currentView = view;
  localStorage.setItem("clipnest-view", view);
  document.querySelectorAll(".view").forEach((item) => {
    item.hidden = item.id !== `view-${view}`;
    item.classList.toggle("active", item.id === `view-${view}`);
  });
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === view);
  });
  const titles = {
    dashboard: ["工作台", "下载工作台"],
    library: ["媒体库", "按作者管理作品"],
    tasks: ["任务", "队列和历史"],
    settings: ["设置", "规则和维护"],
  };
  document.querySelector("#view-kicker").textContent = titles[view][0];
  document.querySelector("#view-title").textContent = titles[view][1];
  if (view === "settings" && state.authenticated) loadSettings();
  if (view === "library" && state.authenticated) loadLibraryPage();
}

function setLibraryMode(mode) {
  state.libraryMode = mode === "media" ? "media" : "authors";
  localStorage.setItem("clipnest-library-mode", state.libraryMode);
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
    <div class="stat"><span>总数</span><strong>${stats.total || 0}</strong></div>
    <div class="stat"><span>运行</span><strong>${stats.running || 0}</strong></div>
    <div class="stat"><span>排队</span><strong>${stats.queued || 0}</strong></div>
    <div class="stat"><span>完成</span><strong>${stats.finished || 0}</strong></div>
    <div class="stat"><span>失败</span><strong>${stats.failed || 0}</strong></div>
    <div class="stat"><span>取消</span><strong>${stats.cancelled || 0}</strong></div>
    <div class="stat"><span>占用</span><strong>${fmtBytes(stats.bytes || 0)}</strong></div>
  `;
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

function filteredTasks() {
  return state.jobs.filter((job) => {
    if (state.statusFilter && job.status !== state.statusFilter) return false;
    if (state.authorFilter && (job.author_name || "Unknown") !== state.authorFilter) return false;
    return jobMatchesSearch(job, state.taskSearch);
  });
}

function libraryJobs() {
  const items = state.libraryMediaJobs.filter((job) => {
    if (job.status !== "finished") return false;
    if (state.libraryAuthor && (job.author_name || "Unknown") !== state.libraryAuthor) return false;
    if (state.libraryType && mediaType(job) !== state.libraryType) return false;
    return jobMatchesSearch(job, state.librarySearch);
  });
  return items.sort((left, right) => {
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
  const source = job.preview_path ? mediaUrl(job, "preview") : (assetUrl(job.cover_path) || job.cover_url);
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
      actions.push(`<button class="danger" type="button" data-delete="${job.id}">删除</button>`);
    }
    return `
      <article class="job" data-job-id="${job.id}">
        <input class="job-select" type="checkbox" data-select="${job.id}" ${state.selectedJobIds.has(String(job.id)) ? "checked" : ""} />
        ${previewFor(job)}
        <div class="meta">
          <div class="title">${escapeHtml(title)}</div>
          <div class="sub">${escapeHtml(job.author_name || "Unknown")} / ${escapeHtml(job.resolution || "-")} / ${fmtBytes(job.size_bytes || 0)}</div>
          <div>
            <span class="pill ${job.status}">${escapeHtml(statusLabel(job.status))}</span>
            <span class="sub">${escapeHtml(job.message || "")}</span>
          </div>
          <div class="progress"><div class="bar" style="width:${Math.max(0, Math.min(100, job.progress || 0))}%"></div></div>
          ${job.error ? `<div class="sub">${escapeHtml(String(job.error).split("\n")[0])}</div>` : ""}
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

function renderAuthors() {
  const chips = [`<button class="chip ${state.authorFilter ? "" : "active"}" type="button" data-author="">全部</button>`];
  for (const item of state.authors.slice(0, 24)) {
    const author = item.author || "Unknown";
    chips.push(`
      <button class="chip ${state.authorFilter === author ? "active" : ""}" type="button" data-author="${escapeHtml(author)}">
        <span>${escapeHtml(author)}</span>
        <strong>${item.total || 0}</strong>
      </button>
    `);
  }
  authorsEl.innerHTML = chips.join("");
}

function renderLibraryAuthors() {
  const authors = state.libraryAuthors;
  libraryAuthorsEl.innerHTML = authors.length ? authors.map((item) => {
    const author = item.author || "Unknown";
    return `
      <button class="author-card ${state.libraryAuthor === author ? "active" : ""}" type="button" data-library-author="${escapeHtml(author)}">
        ${authorAvatar(item)}
        <strong>${escapeHtml(author)}</strong>
        <span>${item.finished || 0} 完成 / ${fmtBytes(item.bytes || 0)}</span>
        <span>最近：${escapeHtml(fmtDate(item.latest_finished_at || item.latest_created_at))}</span>
      </button>
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
  const updateAction = secUid
    ? `<button class="secondary" type="button" data-author-crawl-sec-uid="${escapeHtml(secUid)}">更新该作者作品</button>`
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
      <button class="secondary" type="button" data-library-author-tasks="${escapeHtml(author)}">查看该作者任务</button>
      <button class="secondary" type="button" data-library-clear-author>返回全部作者</button>
    </div>
  `;
}

function renderLibrary() {
  const showingAuthors = state.libraryMode === "authors";
  librarySectionTitle.textContent = showingAuthors ? "作者" : "作品";
  libraryAuthorsPanel.hidden = !showingAuthors;
  libraryMediaPanel.hidden = showingAuthors;
  libraryTypeFilter.hidden = showingAuthors;
  librarySort.hidden = showingAuthors;
  librarySearchInput.placeholder = showingAuthors ? "搜索作者" : "搜索标题、作者或视频 ID";
  document.querySelectorAll("[data-library-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.libraryMode === state.libraryMode);
  });
  renderLibraryAuthors();
  renderLibraryAuthorDetail();
  const typeText = state.libraryType ? (state.libraryType === "image" ? "图集" : "视频") : "全部类型";
  libraryFilterLabel.textContent = state.libraryAuthor ? `${state.libraryAuthor} / ${typeText}` : typeText;
  const media = libraryJobs();
  libraryClearButton.hidden = !state.libraryAuthor;
  libraryMediaEl.innerHTML = media.length ? media.map((job) => `
    <article class="media-card ${mediaType(job)}" data-media-job="${job.id}">
      ${previewFor(job, "media-thumb")}
      <div class="media-body">
        <strong>${escapeHtml(job.title || job.description || job.video_id || job.url)}</strong>
        <span class="media-tag">${escapeHtml(mediaTypeLabel(job))}</span>
        <span class="sub">${escapeHtml(job.author_name || "Unknown")} / ${escapeHtml(job.resolution || "-")} / ${fmtBytes(job.size_bytes || 0)}</span>
        <span class="sub">下载：${escapeHtml(fmtDate(job.finished_at || job.created_at))}</span>
      </div>
    </article>
  `).join("") : `<div class="empty">暂无作品</div>`;
  renderPagination(libraryMediaPaginationEl, "media", state.libraryMediaPage, state.libraryMediaTotalPages, state.libraryMediaTotal);
}

function renderAll() {
  renderStats(state.stats || {});
  renderAuthors();
  renderAuthorCrawls();
  renderLibrary();
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
  return Math.max(1, Math.min(1000, Number(authorCrawlMaxInput.value || 200)));
}

function renderAuthorCrawlCreated(result) {
  const job = result && result.job ? result.job : {};
  authorCrawlResultEl.hidden = false;
  authorCrawlResultEl.innerHTML = `<p>${escapeHtml(result.message || "作者抓取任务已创建")} #${escapeHtml(job.id || "-")}</p>`;
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
    ${result.has_more ? `<p>还有更多作品未抓完，可以把“最多抓取”调大后再运行。</p>` : ""}
    ${samples.length ? `
      <div class="author-crawl-samples">
        ${samples.map((item) => `<span>${escapeHtml(item.title || item.url || item.video_id || "-")}</span>`).join("")}
      </div>
    ` : ""}
  `;
}

function renderAuthorCrawls() {
  const crawls = state.authorCrawls || [];
  if (!crawls.length) {
    authorCrawlJobsEl.innerHTML = `<div class="empty compact">暂无作者抓取任务</div>`;
    return;
  }
  authorCrawlJobsEl.innerHTML = crawls.map((job) => {
    const running = ["running", "pausing", "cancelling"].includes(job.status);
    const canPause = ["queued", "running"].includes(job.status);
    const canResume = ["paused", "failed"].includes(job.status);
    const canCancel = ["queued", "running", "pausing", "paused", "failed"].includes(job.status);
    const actions = [];
    if (canPause) actions.push(`<button class="secondary" type="button" data-author-crawl-action="pause" data-author-crawl-id="${job.id}">暂停</button>`);
    if (canResume) actions.push(`<button class="secondary" type="button" data-author-crawl-action="resume" data-author-crawl-id="${job.id}">继续</button>`);
    if (canCancel) actions.push(`<button class="danger" type="button" data-author-crawl-action="cancel" data-author-crawl-id="${job.id}">取消</button>`);
    return `
      <article class="author-crawl-job ${escapeHtml(job.status || "")}">
        <div>
          <strong>#${job.id} / ${escapeHtml(crawlStatusLabel(job.status))}</strong>
          <span>${escapeHtml(job.sec_uid || job.url || "-")}</span>
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
  if (job.preview_path) return mediaUrl(job, "preview");
  return assetUrl(job.cover_path) || job.cover_url || "";
}

function renderMediaPreview(job) {
  const title = job.title || job.description || job.video_id || job.url || `#${job.id}`;
  const source = mediaSourceFor(job);
  const isVideo = String(job.file_path || "").toLowerCase().endsWith(".mp4");
  mediaPreviewTitleEl.textContent = title;
  mediaPreviewKickerEl.textContent = `${job.author_name || "Unknown"} / ${mediaTypeLabel(job)}`;
  const media = source
    ? isVideo
      ? `<video class="media-preview-player" controls preload="metadata" src="${source}"></video>`
      : `<img class="media-preview-image" src="${escapeHtml(source)}" alt="">`
    : `<div class="media-preview-empty">暂无预览</div>`;
  const canDownload = job.status === "finished" && job.file_path;
  mediaPreviewBodyEl.innerHTML = `
    ${media}
    <div class="media-preview-meta">
      <span>${escapeHtml(job.resolution || "-")} / ${escapeHtml(job.codec || "-")}</span>
      <span>${fmtBytes(job.size_bytes || 0)} / ${escapeHtml(fmtDate(job.finished_at || job.created_at))}</span>
    </div>
    <div class="media-preview-actions">
      ${canDownload ? `<a href="${mediaUrl(job, "file")}"><button type="button">打开文件</button></a>` : ""}
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
}

function closeOverlay() {
  drawerEl.hidden = true;
  closeMediaPreviewOnly();
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
      if (state.librarySearch) params.set("q", state.librarySearch);
      const result = await api(`/api/library/authors?${params.toString()}`);
      state.libraryAuthors = result.items || [];
      state.libraryAuthorsPage = result.page || 1;
      state.libraryAuthorsTotal = result.total || 0;
      state.libraryAuthorsTotalPages = result.total_pages || 1;
    } else {
      const params = new URLSearchParams({
        page: String(state.libraryMediaPage),
        page_size: String(libraryMediaPageSize),
        sort: state.librarySort || "newest",
      });
      if (state.librarySearch) params.set("q", state.librarySearch);
      if (state.libraryAuthor) params.set("author", state.libraryAuthor);
      if (state.libraryType) params.set("type", state.libraryType);
      const [media, authorDetail] = await Promise.all([
        api(`/api/library/jobs?${params.toString()}`),
        state.libraryAuthor ? api(`/api/library/authors/${encodeURIComponent(state.libraryAuthor)}`) : Promise.resolve(null),
      ]);
      state.libraryMediaJobs = media.items || [];
      state.libraryMediaPage = media.page || 1;
      state.libraryMediaTotal = media.total || 0;
      state.libraryMediaTotalPages = media.total_pages || 1;
      state.libraryAuthorDetail = authorDetail;
    }
    renderLibrary();
  } catch (error) {
    summaryEl.textContent = error.message || "媒体库加载失败";
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
  if (state.taskSearch) params.set("q", state.taskSearch);
  const result = await api(`/api/jobs?${params.toString()}`);
  state.jobs = result.items || [];
  state.tasksPage = result.page || 1;
  state.tasksTotal = result.total || 0;
  state.tasksTotalPages = result.total_pages || 1;
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
    await loadLibraryPage();
    summaryEl.textContent = state.libraryMode === "authors" ? "作者已刷新" : "作品已刷新";
  } catch (error) {
    summaryEl.textContent = error.message || "刷新媒体库失败";
  } finally {
    libraryRefreshButton.disabled = false;
    libraryRefreshButton.textContent = "刷新";
  }
}

async function refresh() {
  if (!state.authenticated) {
    summaryEl.textContent = "请登录";
    statsEl.innerHTML = "";
    activeJobsEl.innerHTML = `<div class="empty">暂无任务</div>`;
    jobsEl.innerHTML = `<div class="empty">暂无任务</div>`;
    libraryAuthorsEl.innerHTML = `<div class="empty">暂无作者</div>`;
    libraryMediaEl.innerHTML = `<div class="empty">暂无作品</div>`;
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
    renderAll();
    if (state.currentView === "library") {
      await loadLibraryPage();
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

document.querySelectorAll("[data-library-mode]").forEach((button) => {
  button.addEventListener("click", () => {
    setLibraryMode(button.dataset.libraryMode || "authors");
    state.libraryAuthorsPage = 1;
    state.libraryMediaPage = 1;
    loadLibraryPage();
  });
});

libraryRefreshButton.addEventListener("click", refreshLibraryInPlace);
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
      body: JSON.stringify({ url, max_items: maxItems }),
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

authorCrawlJobsEl.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-author-crawl-action]");
  if (!button) return;
  const action = button.dataset.authorCrawlAction;
  const crawlId = button.dataset.authorCrawlId;
  if (!action || !crawlId) return;
  const actionLabel = { pause: "暂停", resume: "继续", cancel: "取消" }[action] || action;
  try {
    button.disabled = true;
    summaryEl.textContent = `正在${actionLabel}作者抓取任务 #${crawlId}`;
    await api(`/api/author-crawls/${crawlId}/${action}`, { method: "POST" });
    await loadAuthorCrawls();
    renderAuthorCrawls();
    summaryEl.textContent = `作者抓取任务 #${crawlId} 已${actionLabel}`;
  } catch (error) {
    summaryEl.textContent = error.message || `${actionLabel}作者抓取任务失败`;
  } finally {
    button.disabled = false;
  }
});

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

librarySearchInput.addEventListener("input", () => {
  state.librarySearch = librarySearchInput.value.trim();
  if (state.libraryMode === "authors") state.libraryAuthorsPage = 1;
  else state.libraryMediaPage = 1;
  loadLibraryPage();
});

libraryTypeFilter.addEventListener("change", () => {
  state.libraryType = libraryTypeFilter.value;
  state.libraryMediaPage = 1;
  loadLibraryPage();
});

librarySort.addEventListener("change", () => {
  state.librarySort = librarySort.value || "newest";
  state.libraryMediaPage = 1;
  loadLibraryPage();
});

libraryClearButton.addEventListener("click", () => {
  state.libraryAuthor = "";
  state.libraryAuthorDetail = null;
  state.libraryMediaPage = 1;
  loadLibraryPage();
});

authorsEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-author]");
  if (!button) return;
  state.authorFilter = button.dataset.author || "";
  state.tasksPage = 1;
  refresh();
});

libraryAuthorsEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-library-author]");
  if (!button) return;
  state.libraryAuthor = button.dataset.libraryAuthor || "";
  setLibraryMode("media");
  state.libraryMediaPage = 1;
  loadLibraryPage();
});

libraryAuthorDetailEl.addEventListener("click", async (event) => {
  const authorCrawlButton = event.target.closest("[data-author-crawl-sec-uid]");
  if (authorCrawlButton) {
    const secUid = authorCrawlButton.dataset.authorCrawlSecUid || "";
    if (!secUid) return;
    try {
      authorCrawlButton.disabled = true;
      summaryEl.textContent = "正在创建作者更新任务";
      const result = await api("/api/author-crawls", {
        method: "POST",
        body: JSON.stringify({
          url: `https://www.douyin.com/user/${secUid}`,
          max_items: authorCrawlMaxItems(),
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
    state.tasksPage = 1;
    setView("tasks");
    refresh();
    return;
  }
  if (event.target.closest("[data-library-clear-author]")) {
    state.libraryAuthor = "";
    state.libraryAuthorDetail = null;
    state.libraryMediaPage = 1;
    loadLibraryPage();
  }
});

function handleLibraryPageClick(event) {
  const button = event.target.closest("[data-library-page]");
  if (!button || button.disabled) return;
  const delta = Number(button.dataset.pageDelta || 0);
  if (button.dataset.libraryPage === "authors") {
    state.libraryAuthorsPage += delta;
  } else {
    state.libraryMediaPage += delta;
  }
  loadLibraryPage();
}

libraryAuthorsPaginationEl.addEventListener("click", handleLibraryPageClick);
libraryMediaPaginationEl.addEventListener("click", handleLibraryPageClick);
tasksPaginationEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-library-page]");
  if (!button || button.disabled) return;
  state.tasksPage += Number(button.dataset.pageDelta || 0);
  refresh();
});

libraryMediaEl.addEventListener("click", (event) => {
  const card = event.target.closest("[data-media-job]");
  if (card) openMediaPreview(card.dataset.mediaJob);
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
      if (!confirm("删除这个任务和本地文件？")) return;
      await api(`/api/jobs/${deleteId}?delete_file=true`, { method: "DELETE" });
      summaryEl.textContent = "已删除";
    }
    refresh();
  } catch (error) {
    summaryEl.textContent = error.message || "操作失败";
  }
}

jobsEl.addEventListener("click", handleJobAction);
activeJobsEl.addEventListener("click", handleJobAction);

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
  if (!confirm("删除已选任务和本地文件？")) return;
  try {
    await runBulkAction("/api/jobs/bulk/delete", { delete_file: true }, "批量删除已完成");
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

mediaPreviewBodyEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-open-detail]");
  if (!button) return;
  closeMediaPreviewOnly();
  openJobDetail(button.dataset.openDetail);
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
