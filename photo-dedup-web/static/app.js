"use strict";

// ---------- 全局状态 ----------
const S = {
  root: "",
  taskId: null,
  timer: null,
  busy: false,
  groups: [],        // 本次扫描结果的全部重复组
  stats: null,
  keepMap: {},       // group.id -> 保留的 abs（默认不覆盖用户选择）
  skipSet: new Set(),// 跳过的 group.id
  movedSet: new Set(),// 已移动到 temp 的 abs
  lastKeep: [],      // 最近一次移动用的 keep 清单
  page: 0,
  pageSize: 60,
  filter: "",
};

const IMG_EXTS = ["jpg", "jpeg", "png", "gif", "bmp", "webp"];
const VID_EXTS = ["mov", "mp4", "avi", "mkv", "m4v"];

// ---------- 工具 ----------
const $ = (id) => document.getElementById(id);

function fmtBytes(n) {
  n = Number(n) || 0;
  if (n < 1024) return n + " B";
  const units = ["KB", "MB", "GB", "TB"];
  let u = -1;
  do { n /= 1024; u++; } while (n >= 1024 && u < units.length - 1);
  return n.toFixed(1) + " " + units[u];
}

function extOf(p) {
  const m = /\.([^.]+)$/.exec(p);
  return m ? m[1].toLowerCase() : "";
}

function basename(p) {
  const parts = p.split(/[\\/]/);
  return parts[parts.length - 1];
}

let toastTimer = null;
function toast(msg) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 3200);
}

async function postJson(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return r.json();
}

function setBusy(b) {
  S.busy = b;
  $("btnScan").disabled = b;
  $("btnCancel").style.display = b && S.taskId ? "inline-block" : "none";
}

// ---------- 可见反馈 / 健康检查 ----------
function showErr(msg) {
  const el = $("errBanner");
  el.style.display = msg ? "" : "none";
  el.textContent = msg || "";
}
function setReqStatus(msg) {
  $("reqStatus").textContent = msg || "";
}
function setSrvStatus(ok, text) {
  const el = $("srvStatus");
  el.textContent = text;
  el.className = "srv-status" + (ok ? " ok" : " err");
}

async function pingBackend() {
  try {
    const r = await fetch("/api/ping", { cache: "no-store" });
    const j = await r.json();
    if (j && j.ok) {
      setSrvStatus(true, "后端在线");
      return true;
    }
    setSrvStatus(false, "后端异常");
    return false;
  } catch (e) {
    setSrvStatus(false, "后端离线");
    return false;
  }
}

async function restartBackend() {
  if (S.busy) { toast("请先等待当前任务结束"); return; }
  setReqStatus("正在重启后端…");
  showErr("");
  try { await postJson("/api/backend/restart", {}); } catch (e) { /* 重启瞬间连接中断属正常 */ }
  let ok = false;
  for (let i = 0; i < 40; i++) {
    await new Promise((r) => setTimeout(r, 600));
    ok = await pingBackend();
    if (ok) break;
  }
  $("btnRestart").style.display = "none";
  setBusy(false);
  if (ok) {
    setReqStatus("后端已重启，请重新点击「开始检查」。");
    toast("后端已重启");
  } else {
    setReqStatus("重启后端失败，请手动运行 python run.py");
    toast("重启后端失败");
  }
}

// 页面加载即探测后端，给即时可见反馈
window.addEventListener("load", () => { pingBackend(); });

// ---------- 开始扫描 ----------
async function startScan() {
  showErr("");                       // 清掉上一次的错误
  if (S.busy) { toast("扫描正在进行中…"); return; }
  let root;
  try { root = $("rootInput").value.trim(); }
  catch (e) { showErr("页面初始化失败：" + e.message); return; }
  if (!root) { toast("请输入文件夹路径"); return; }

  const ok = await pingBackend();
  if (!ok) {
    showErr("无法连接后端（未启动或已崩溃）。若已启动 python run.py，请点击右上角「重启后端」，或重启服务后刷新页面。");
    $("btnRestart").style.display = "";
    setBusy(false);
    return;
  }

  setBusy(true);
  setReqStatus("正在提交扫描任务…");
  // 清理上轮 UI（对可能缺失的元素做保护，避免 DOM 异常阻断请求）
  ["resultList", "statsBar", "toolbar", "emptyHint", "previewWrap"].forEach((id) => {
    const el = $(id); if (el) el.style.display = "none";
  });

  let res;
  try {
    res = await postJson("/api/scan/start", { root });
  } catch (e) {
    setBusy(false); setReqStatus("");
    showErr("请求发送失败：" + e.message);
    return;
  }
  if (res.error) {
    setBusy(false); setReqStatus("");
    showErr(res.error);
    return;
  }

  // 新扫描：重置上一次的勾选 / 跳过 / 已移动状态
  S.keepMap = {};
  S.skipSet = new Set();
  S.movedSet = new Set();
  S.lastKeep = [];
  S.page = 0;
  S.filter = "";
  const fi = $("filterInput"); if (fi) fi.value = "";
  S.taskId = res.task_id;
  S.root = res.root || root;
  setReqStatus("请求已发送，任务 " + S.taskId + "，等待扫描…");
  const pw = $("progressWrap"); if (pw) pw.style.display = "";
  const pp = $("progPhase"); if (pp) pp.textContent = "准备中…";
  const pc = $("progCount"); if (pc) pc.textContent = "0";
  startPoll();
}

function startPoll() {
  stopPoll();
  S.timer = setInterval(poll, 800);
  poll();
}
function stopPoll() {
  if (S.timer) { clearInterval(S.timer); S.timer = null; }
}

async function poll() {
  let res;
  try {
    res = await fetch("/api/scan/status?task_id=" + S.taskId).then((r) => r.json());
  } catch (e) {
    return; // 下次轮询再试
  }
  if (res.state === "done") {
    stopPoll();
    S.groups = res.groups || [];
    S.stats = res.stats || {};
    S.root = res.root || S.root;
    initKeep();
    setBusy(false);
    setReqStatus("");
    $("progressWrap").style.display = "none";
    renderResults();
    toast("扫描完成，共 " + S.groups.length + " 组重复");
    return;
  }
  if (res.state === "error") {
    stopPoll();
    setBusy(false);
    $("progressWrap").style.display = "none";
    toast("扫描出错：" + (res.error || "未知错误"));
    return;
  }
  if (res.state === "cancelled") {
    stopPoll();
    setBusy(false);
    $("progressWrap").style.display = "none";
    toast("已取消扫描");
    return;
  }
  // running / cancelling：刷新进度
  updateProgress(res.phase, res.scanned, res.total);
}

function updateProgress(phase, scanned, total) {
  $("progPhase").textContent = phase || "扫描中…";
  $("progCount").textContent = String(scanned || 0) + (total ? " / " + total : "");
  const pct = total ? Math.min(100, Math.round((scanned / total) * 100)) : 0;
  $("progFill").style.width = pct + "%";
}

async function cancelScan() {
  if (!S.taskId) return;
  await postJson("/api/scan/cancel", {});
  toast("正在取消…");
}

// ---------- 保留默认值 ----------
function initKeep() {
  for (const g of S.groups) {
    if (!(g.id in S.keepMap)) S.keepMap[g.id] = g.keep_abs;
  }
// ---------- 渲染结果 ----------
function visibleGroups() {
  const f = S.filter.toLowerCase();
  if (!f) return S.groups;
  return S.groups.filter((g) =>
    g.items.some((it) => basename(it.abs).toLowerCase().includes(f))
  );
}

function renderResults() {
  $("resultList").innerHTML = "";
  $("resultList").style.display = "";
  $("toolbar").style.display = "";
  $("emptyHint").style.display = "none";

  if (!S.groups.length) {
    $("resultList").style.display = "none";
    $("emptyHint").style.display = "";
    $("emptyHint").textContent = "没有发现重复的文件。";
    return;
  }
  renderStats();

  const groups = visibleGroups();
  const totalPages = Math.max(1, Math.ceil(groups.length / S.pageSize));
  if (S.page >= totalPages) S.page = totalPages - 1;
  const start = S.page * S.pageSize;
  const slice = groups.slice(start, start + S.pageSize);

  const frag = document.createDocumentFragment();
  slice.forEach((g) => frag.appendChild(buildGroup(g)));
  $("resultList").appendChild(frag);
  renderPager(totalPages);
}

function renderStats() {
  const st = S.stats || {};
  $("stGroups").textContent = st.groups || 0;
  $("stFiles").textContent = st.files || 0;
  $("stToMove").textContent = st.to_move || 0;
  $("stFreed").textContent = fmtBytes(st.freed_bytes || 0);
  $("statsBar").style.display = "";
}

function renderPager(totalPages) {
  const p = $("pager");
  p.innerHTML = "";
  const label = document.createElement("span");
  label.textContent = (S.page + 1) + " / " + totalPages + " 页";
  p.appendChild(label);
  const mk = (txt, fn, dis) => {
    const b = document.createElement("button");
    b.textContent = txt;
    b.disabled = !!dis;
    b.onclick = fn;
    p.appendChild(b);
  };
  mk("‹", () => { S.page--; renderResults(); }, S.page <= 0);
  mk("›", () => { S.page++; renderResults(); }, S.page >= totalPages - 1);
}

function applyFilter() {
  S.filter = $("filterInput").value.trim().toLowerCase();
  S.page = 0;
  renderResults();
}

// ---------- 构建一个分组 ----------
function buildGroup(g) {
  const sec = document.createElement("section");
  sec.className = "group";
  sec.dataset.id = g.id;

  const isSkipped = S.skipSet.has(g.id);
  const head = document.createElement("div");
  head.className = "ghead";

  const toggle = document.createElement("span");
  toggle.className = "gtoggle";
  toggle.textContent = "▶";
  const gid = document.createElement("span");
  gid.className = "gid";
  gid.textContent = "组 #" + g.id;
  const mode = document.createElement("span");
  mode.className = "gmode";
  mode.textContent = g.mode;
  const meta = document.createElement("span");
  meta.className = "gmeta";
  meta.textContent = "· " + g.items.length + " 份 · " + fmtBytes(g.total_size);

  const skipLbl = document.createElement("label");
  const skipBox = document.createElement("input");
  skipBox.type = "checkbox";
  skipBox.checked = isSkipped;
  skipBox.addEventListener("change", () => {
    if (skipBox.checked) S.skipSet.add(g.id); else S.skipSet.delete(g.id);
    sec.classList.toggle("skipped", skipBox.checked);
  });
  skipLbl.appendChild(skipBox);
  skipLbl.appendChild(document.createTextNode("本组跳过"));

  head.append(toggle, gid, mode, meta, skipLbl);

  const body = document.createElement("div");
  body.className = "gbody";
  toggle.addEventListener("click", () => {
    const open = body.classList.toggle("open");
    toggle.textContent = open ? "▼" : "▶";
  });

  g.items.forEach((it) => {
    if (S.movedSet.has(it.abs)) return; // 已移动的不再显示
    body.appendChild(buildRow(g, it));
  });

  sec.append(head, body);
  if (isSkipped) sec.classList.add("skipped");
  return sec;
}
function buildRow(g, it) {
  const row = document.createElement("div");
  row.className = "row";

  const thumb = document.createElement("div");
  thumb.className = "thumb";
  const ext = extOf(it.abs);
  if (VID_EXTS.includes(ext)) {
    const v = document.createElement("video");
    v.preload = "metadata";
    v.src = "/api/file?p=" + encodeURIComponent(it.abs);
    v.muted = true;
    v.onerror = () => { thumb.innerHTML = '<span class="video-ico">▶</span>'; };
    thumb.appendChild(v);
  } else if (IMG_EXTS.includes(ext)) {
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = "/api/file?p=" + encodeURIComponent(it.abs);
    img.onerror = () => { thumb.innerHTML = '<span class="no-preview">无法预览</span>'; };
    thumb.appendChild(img);
  } else {
    thumb.innerHTML = '<span class="no-preview">无法预览</span>';
  }

  const info = document.createElement("div");
  info.className = "info";
  const fn = document.createElement("div");
  fn.className = "fname";
  fn.textContent = basename(it.abs);
  fn.title = it.abs;
  const fp = document.createElement("div");
  fp.className = "fpath";
  fp.textContent = it.abs;
  fp.title = it.abs;
  info.append(fn, fp);

  const meta = document.createElement("div");
  meta.className = "meta";
  const kindTxt = it.kind === "vid" ? "视频" : "图片";
  meta.textContent = fmtBytes(it.size) + " · " + kindTxt;

  const pick = document.createElement("div");
  pick.className = "pick";
  const radio = document.createElement("input");
  radio.type = "radio";
  radio.name = "keep_" + g.id;
  radio.value = it.abs;
  radio.checked = S.keepMap[g.id] === it.abs;
  radio.addEventListener("change", () => {
    if (radio.checked) S.keepMap[g.id] = it.abs;
    refreshGroupBadges(g.id);
  });
  const badge = document.createElement("span");
  badge.className = "badge";
  pick.append(radio, badge);

  row.append(thumb, info, meta, pick);
  refreshGroupBadges(g.id);
  return row;
}

function refreshGroupBadges(gid) {
  const radios = document.querySelectorAll('input[name="keep_' + gid + '"]');
  radios.forEach((radio) => {
    const row = radio.closest(".row");
    if (!row) return;
    const badge = row.querySelector(".badge");
    if (radio.checked) {
      badge.textContent = "保留";
      badge.className = "badge keep";
    } else {
      badge.textContent = "待移动";
      badge.className = "badge move";
    }
  });
}

// ---------- 移动（两阶段） ----------
function collectKeeps() {
  const list = [];
  for (const g of S.groups) {
    if (S.skipSet.has(g.id)) continue;
    const k = S.keepMap[g.id];
    if (k) list.push(k);
  }
  return list;
}

async function startMove() {
  const keeps = collectKeeps();
  if (!keeps.length) { toast("没有待移动的文件（请至少为每组保留 1 份）"); return; }
  S.lastKeep = keeps;
  const res = await postJson("/api/move", {
    root: S.root,
    keep_abs: keeps,
    dry: true,
  });
  if (res.error) { toast(res.error); return; }
  renderPreview(res, true);
}

async function confirmMove() {
  const res = await postJson("/api/move", {
    root: S.root,
    keep_abs: S.lastKeep,
    dry: false,
  });
  if (res.error) { toast(res.error); return; }
  const moved = (res.preview || []).filter((p) => p.reason === "moved");
  moved.forEach((p) => S.movedSet.add(p.from));
  renderPreview(res, false);

  const skip = res.skip || 0;
  const failed = res.failed || 0;
  let msg = "已移动 " + moved.length + " 份文件到 temp";
  if (skip) msg += "，跳过 " + skip + "（目标已存在）";
  if (failed) msg += "，失败 " + failed;
  toast(msg);
  renderResults(); // 刷新：隐藏已移动的行
}

function renderPreview(res, dry) {
  const wrap = $("previewWrap");
  wrap.style.display = "";
  $("previewMode").textContent = dry ? "（预览，未执行）" : "（已执行）";
  $("previewDest").textContent = "→ " + (res.dest || "");
  const list = $("previewList");
  list.innerHTML = "";

  const items = res.preview || [];
  if (!items.length) {
    const d = document.createElement("div");
    d.className = "pv-row";
    d.textContent = "没有需要移动的文件。";
    list.appendChild(d);
  }
  items.forEach((p) => {
    const row = document.createElement("div");
    row.className = "pv-row" + (p.reason === "dest_exist" ? " dest_exist" : "") + (dry ? "" : " read-only");
    const from = document.createElement("span");
    from.className = "pv-from";
    from.textContent = basename(p.from);
    from.title = p.from;
    const arrow = document.createElement("span");
    arrow.className = "pv-arrow";
    arrow.textContent = "→";
    const to = document.createElement("span");
    to.className = "pv-to";
    to.textContent = p.to;
    to.title = p.to;
    const tag = document.createElement("span");
    tag.className = "pv-tag " + p.reason;
    const labelMap = {
      move: "将移动",
      moved: "已移动",
      dest_exist: "目标存在·跳过",
      src_missing: "源缺失",
      move_failed: "失败",
    };
    tag.textContent = labelMap[p.reason] || p.reason;
    row.append(from, arrow, to, tag);
    list.appendChild(row);
  });

  $("btnConfirm").style.display = dry ? "" : "none";
}

function closePreview() {
  $("previewWrap").style.display = "none";
}

// 回车触发扫描
document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && document.activeElement === $("rootInput")) {
    startScan();
  }
});

// 显式挂到 window，保证内联 onclick 一定能解析到（兼容任何加载时序）
window.startScan = startScan;
window.cancelScan = cancelScan;
window.startMove = startMove;
window.confirmMove = confirmMove;
window.applyFilter = applyFilter;
window.closePreview = closePreview;
window.restartBackend = restartBackend;
}