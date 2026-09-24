import React from 'react';

export default function ScanBar({ root, onRoot, onStart, onCancel, busy, canCancel }) {
  return (
    <div className="input-bar">
      <input
        type="text"
        value={root}
        onChange={(e) => onRoot(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && busy && onStart()}
        placeholder="输入要检查的文件夹绝对路径，如 D:/photos/2017"
        spellCheck={false}
        autoComplete="off"
        disabled={busy}
      />
      <button className="primary" onClick={onStart} disabled={busy || !root.trim()}>
        {busy ? '扫描中…' : '开始检查'}
      </button>
      {busy && (
        <button className="ghost" onClick={onCancel} disabled={!canCancel}>
          取消
        </button>
      )}
    </div>
  );
}