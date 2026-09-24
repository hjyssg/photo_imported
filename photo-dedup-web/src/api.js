// src/api.js —— 所有后端接口封装（相对路径，dev 走 Vite 代理，prod 同源）

async function postJson(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  let data = {};
  try { data = await r.json(); } catch { /* 空响应 */ }
  if (!r.ok || data.error) {
    throw new Error(data.error || `请求失败（HTTP ${r.status}）`);
  }
  return data;
}

export async function ping() {
  try {
    const r = await fetch('/api/ping', { cache: 'no-store' });
    const j = await r.json();
    return r.ok && !!(j && j.ok);
  } catch {
    return false;
  }
}

export async function startScan(root) {
  return postJson('/api/scan/start', { root });
}

export async function getStatus(taskId) {
  const q = taskId ? `?task_id=${encodeURIComponent(taskId)}` : '';
  const r = await fetch(`/api/scan/status${q}`, { cache: 'no-store' });
  if (!r.ok) {
    let d = {};
    try { d = await r.json(); } catch {}
    throw new Error(d.error || `获取状态失败（HTTP ${r.status}）`);
  }
  return r.json();
}

export async function cancelScan() {
  return postJson('/api/scan/cancel', {});
}

export async function moveFiles(root, keepAbs, dry) {
  return postJson('/api/move', { root, keep_abs: keepAbs, dry });
}

export async function restartBackend() {
  return postJson('/api/backend/restart', {});
}

/** 缩略图/视频预览地址；p 为被扫目录内的绝对路径 */
export function fileUrl(p) {
  return `/api/file?p=${encodeURIComponent(p)}`;
}

export function isImage(p) {
  return /\.(jpg|jpeg|png|gif|bmp|webp)$/i.test(p);
}

export function fmtBytes(n) {
  n = Number(n) || 0;
  if (n < 1024) return `${n} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let u = -1;
  do { n /= 1024; u += 1; } while (n >= 1024 && u < units.length - 1);
  return `${n.toFixed(1)} ${units[u]}`;
}

export function fmtElapsed(sec) {
  sec = Math.max(0, Math.floor(Number(sec) || 0));
  const s = sec % 60;
  const m = Math.floor(sec / 60) % 60;
  const h = Math.floor(sec / 3600);
  if (h) return `${h}时${String(m).padStart(2, '0')}分${String(s).padStart(2, '0')}秒`;
  if (m) return `${m}分${String(s).padStart(2, '0')}秒`;
  return `${s}秒`;
}
