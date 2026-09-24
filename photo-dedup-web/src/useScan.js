// src/useScan.js —— 扫描任务的轮询 Hook（状态机驱动进度/完成/错误/取消/空闲）

import { useEffect, useRef, useState } from 'react';
import { getStatus } from './api';

const POLL_MS = 800;
const PHASE_LABEL = {
  counting: '扫描文件…',
  图片指纹: '计算图片指纹…',
  MD5: '比对数校验…',
};

function pct(phase, scanned, total) {
  if (!phase || !total) return 0;
  return Math.min(100, Math.round((scanned / total) * 100));
}

export function useScan({ taskId, onDone, onError }) {
  const [state, setState] = useState('idle'); // idle|running|done|error|cancelled|offline
  const [phase, setPhase] = useState('');
  const [scanned, setScanned] = useState(0);
  const [total, setTotal] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);

  const onDoneRef = useRef(onDone);
  const onErrorRef = useRef(onError);
  onDoneRef.current = onDone;
  onErrorRef.current = onError;

  useEffect(() => {
    if (!taskId) return;
    setState('running');
    setScanned(0); setTotal(0); setElapsed(0); setError(null);

    let dead = false;
    let timer = null;

    const tick = async () => {
      let res;
      try {
        res = await getStatus(taskId);
      } catch (e) {
        if (dead) return;
        setState((prev) => (prev === 'running' ? 'offline' : prev));
        return;
      }
      if (dead) return;

      if (res.state === 'done') {
        dead = true;
        setState('done');
        setPhase(res.phase || '完成');
        setScanned(res.scanned ?? 0);
        setTotal(res.total ?? 0);
        if (onDoneRef.current) onDoneRef.current(res);
        return;
      }
      if (res.state === 'error') {
        dead = true;
        setState('error');
        setError(res.error || '未知错误');
        if (onErrorRef.current) onErrorRef.current(res.error || '未知错误');
        return;
      }
      if (res.state === 'cancelled') {
        dead = true;
        setState('cancelled');
        return;
      }
      if (res.state === 'idle') {
        // 无匹配任务（后端可能已重启）→ 视为异常
        dead = true;
        setState('error');
        setError('任务不存在或后端已重启，请重新扫描。');
        if (onErrorRef.current) onErrorRef.current('任务不存在或后端已重启，请重新扫描。');
        return;
      }
      // running / cancelling：刷新进度
      setState('running');
      setPhase(res.phase || '');
      setScanned(res.scanned ?? 0);
      setTotal(res.total ?? 0);
      setElapsed(res.elapsed ?? 0);
    };

    timer = setInterval(tick, POLL_MS);
    tick();

    return () => {
      dead = true;
      if (timer) clearInterval(timer);
    };
  }, [taskId]);

  const percent = pct(phase, scanned, total);
  const phaseText = PHASE_LABEL[phase] || phase || '扫描中…';

  return { state, phase, phaseText, scanned, total, percent, elapsed, error };
}