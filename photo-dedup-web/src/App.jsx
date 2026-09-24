import React, { useEffect, useRef, useState } from 'react';
import ScanBar from './components/ScanBar';
import StatusBar from './components/StatusBar';
import ProgressPanel from './components/ProgressPanel';
import Results from './components/Results';
import Toast from './components/Toast';
import { useScan } from './useScan';
import { ping, startScan, cancelScan, moveFiles, restartBackend } from './api';

export default function App() {
  const [root, setRoot] = useState('');
  const [online, setOnline] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [taskId, setTaskId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [canceling, setCanceling] = useState(false);

  // 扫描结果
  const [groups, setGroups] = useState([]);
  const [stats, setStats] = useState({});
  const [keepMap, setKeepMap] = useState({});
  const [skipSet, setSkipSet] = useState(() => new Set());
  const [movedSet, setMovedSet] = useState(() => new Set());
  const [expandedMap, setExpandedMap] = useState(() => new Set());
  const [filter, setFilter] = useState('');
  const [page, setPage] = useState(0);
  const [preview, setPreview] = useState(null);
  const [toast, setToast] = useState(null);
  const lastKeepsRef = useRef([]);

  const scan = useScan({
    taskId,
    onDone: (res) => {
      setGroups(res.groups || []);
      setStats(res.stats || {});
      setKeepMap((prev) => {
        const next = { ...prev };
        (res.groups || []).forEach((g) => { if (!(g.id in next)) next[g.id] = g.keep_abs; });
        return next;
      });
      setExpandedMap(new Set((res.groups || []).map((g) => g.id)));
      setPreview(null);
      setToast(`扫描完成，共 ${(res.groups || []).length} 组重复`);
      setSubmitting(false);
      setCanceling(false);
    },
    onError: (err) => {
      setToast('扫描出错：' + (err || '未知错误'));
      setSubmitting(false);
      setCanceling(false);
    },
  });
  const busy = submitting || ['connecting', 'running', 'offline'].includes(scan.state);
  const canCancel = submitting || ['connecting', 'running', 'offline'].includes(scan.state);

  // 初始探测后端
  useEffect(() => {
    let alive = true;
    ping().then((ok) => { if (alive) setOnline(ok); });
    return () => { alive = false; };
  }, []);

  // Toast 自动隐藏
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3200);
    return () => clearTimeout(t);
  }, [toast]);

  async function handleStart() {
    if (busy) { setToast('扫描正在进行中…'); return; }
    const r = root.trim();
    if (!r) { setToast('请输入文件夹路径'); return; }
    const ok = await ping();
    setOnline(ok);
    if (!ok) { setToast('无法连接后端（未启动或已崩溃）。请重启后端或刷新页面。'); return; }

    setSubmitting(true);
    setCanceling(false);
    setTaskId(null);
    setGroups([]); setStats({}); setKeepMap({});
    setSkipSet(new Set()); setMovedSet(new Set()); setExpandedMap(new Set());
    setFilter(''); setPage(0); setPreview(null);
    try {
      const res = await startScan(r);
      setTaskId(res.task_id);
    } catch (e) {
      setToast(e.message || '提交任务失败');
      setSubmitting(false);
    }
  }

  async function handleCancel() {
    setCanceling(true);
    cancelScan().then(() => setToast('正在取消…')).catch((e) => setToast(e.message));
  }

  async function handleMove() {
    if (!groups.length) { setToast('暂无可移动的结果'); return; }
    const keeps = [];
    for (const g of groups) {
      if (skipSet.has(g.id)) continue;
      const k = keepMap[g.id];
      if (k) keeps.push(k);
    }
    if (!keeps.length) { setToast('没有待移动的文件（请至少为每组保留 1 份）'); return; }
    lastKeepsRef.current = keeps;
    try {
      const res = await moveFiles(root, keeps, true);
      setPreview({ dry: true, dest: res.dest, items: res.preview || [] });
    } catch (e) {
      setToast(e.message);
    }
  }

async function handleConfirmMove() {
    try {
      const res = await moveFiles(root, lastKeepsRef.current, false);
      setPreview({ dry: false, dest: res.dest, items: res.preview || [] });
      setMovedSet((prev) => {
        const next = new Set(prev);
        (res.preview || []).forEach((p) => { if (p.reason === 'moved') next.add(p.from); });
        return next;
      });
      const moved = (res.preview || []).filter((p) => p.reason === 'moved').length;
      let msg = `已移动 ${moved} 份文件到 temp`;
      if (res.skip) msg += `，跳过 ${res.skip}`;
      if (res.failed) msg += `，失败 ${res.failed}`;
      setToast(msg);
    } catch (e) {
      setToast(e.message);
    }
  }

  async function handleRestart() {
    setRestarting(true);
    try { await restartBackend(); } catch { /* 重启瞬间断连属正常 */ }
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 600));
      const ok = await ping();
      if (ok) { setOnline(true); break; }
    }
    setRestarting(false);
  }

  const statsBar = stats.groups !== undefined;

  return (
    <div id="app">
      <header>
        <h1>
          照片去重工具
          <StatusBar online={online} onRestart={handleRestart} restarting={restarting} />
        </h1>
        <ScanBar
          root={root}
          onRoot={setRoot}
          onStart={handleStart}
          onCancel={handleCancel}
          busy={busy}
          canCancel={canCancel}
        />
        {busy && (
          <p className="req-status">
            {taskId ? `任务 ${taskId} · 正在扫描，请稍候` : '正在提交扫描任务…'}
          </p>
        )}
        {scan.state === 'cancelled' && <div className="err-banner">已取消扫描。</div>}
        {scan.state === 'error' && <div className="err-banner">{scan.error || '扫描出错'}</div>}
        {scan.state === 'offline' && (
          <div className="err-banner">暂时无法获取扫描进度（后端可能已重启）。请稍候或「重启后端」。</div>
        )}
      </header>

      {(scan.state === 'running' || submitting) && (
        <ProgressPanel
          phaseText={scan.phaseText}
          percent={scan.percent}
          scanned={scan.scanned}
          total={scan.total}
          elapsed={scan.elapsed}
          canceling={canceling}
        />
      )}

      {statsBar && !busy && scan.state === 'done' && (
        <Results
          groups={groups}
          stats={stats}
          keepMap={keepMap}
          onKeep={(gid, abs) => setKeepMap((p) => ({ ...p, [gid]: abs }))}
          skipSet={skipSet}
          onToggleSkip={(gid) => setSkipSet((prev) => {
            const next = new Set(prev);
            next.has(gid) ? next.delete(gid) : next.add(gid);
            return next;
          })}
          movedSet={movedSet}
          expandedMap={expandedMap}
          onToggleExpand={(gid) => setExpandedMap((prev) => {
            const next = new Set(prev);
            next.has(gid) ? next.delete(gid) : next.add(gid);
            return next;
          })}
          filter={filter}
          onFilter={(v) => { setFilter(v.toLowerCase()); setPage(0); }}
          page={page}
          onPage={(p) => setPage(Math.max(0, p))}
          onMove={handleMove}
          movedDisabled={!groups.length}
          canMove={true}
          preview={preview}
          onClosePreview={() => setPreview(null)}
          onConfirmPreview={handleConfirmMove}
          confirmDisabled={false}
        />
      )}

      <Toast msg={toast} />
    </div>
  );
}