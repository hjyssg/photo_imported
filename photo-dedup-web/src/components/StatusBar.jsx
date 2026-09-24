import React from 'react';

export default function StatusBar({ online, onRestart, restarting }) {
  return (
    <span className="srv-status-wrap">
      <span className={`srv-status ${online ? 'ok' : 'err'}`}>
        {online ? '后端在线' : '后端离线'}
      </span>
      {!online && (
        <button className="ghost small" onClick={onRestart} disabled={restarting}>
          {restarting ? '重启中…' : '重启后端'}
        </button>
      )}
    </span>
  );
}