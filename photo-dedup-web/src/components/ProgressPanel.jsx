import React from 'react';
import { fmtElapsed } from '../api';

export default function ProgressPanel({ phaseText, percent, scanned, total, elapsed, canceling }) {
  return (
    <div className="progress">
      <div className="prog-line">
        <span className="prog-label">阶段</span>
        <span className="prog-phase">{phaseText}{canceling ? ' · 正在取消…' : ''}</span>
        <span className="prog-elapsed">已用时 {fmtElapsed(elapsed)}</span>
      </div>
      <div className="prog-bar">
        <div className="prog-fill" style={{ width: `${percent}%` }} />
      </div>
      <div className="prog-num">
        <span>{scanned || 0}{total ? ` / ${total}` : ''}</span> 项 · {percent}%
      </div>
    </div>
  );
}