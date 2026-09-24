import React from 'react';
import { fileUrl, fmtBytes, isImage } from '../api';

export function basename(p) {
  const parts = p.split(/[\\/]/);
  return parts[parts.length - 1];
}

export const REASON_LABEL = {
  move: '将移动',
  moved: '已移动',
  dest_exist: '目标存在·跳过',
  skip: '跳过',
  src_missing: '源缺失',
  move_failed: '失败',
};
export const REASON_CLS = {
  move: 'move',
  moved: 'moved',
  dest_exist: 'dest_exist',
  skip: 'dest_exist',
  src_missing: 'move_failed',
  move_failed: 'move_failed',
};

function Thumb({ abs, kind }) {
  if (kind === 'vid') {
    return (
      <div className="thumb vid">
        <video src={fileUrl(abs)} preload="metadata" muted loop />
      </div>
    );
  }
  if (isImage(abs)) {
    return (
      <div className="thumb">
        <img src={fileUrl(abs)} alt="" loading="lazy" />
      </div>
    );
  }
  return <div className="thumb no-preview">无预览</div>;
}

export function GroupCard({ g, onKeep, onToggleSkip, onToggleExpand, keepMap, skipSet, movedSet, expanded }) {
  const isSkipped = skipSet.has(g.id);
  const open = expanded.has(g.id);
  return (
    <section className="group">
      <div className="ghead" onClick={() => onToggleExpand(g.id)}>
        <span className="gtoggle">{open ? '▼' : '▶'}</span>
        <span className="gid">组 #{g.id}</span>
        <span className="gmode">{g.mode}</span>
        <span className="gmeta">
          {g.items.length} 份 · {fmtBytes(g.total_size)}
          {isSkipped ? ' · 已跳过本组' : ''}
        </span>
        <label onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={isSkipped}
            onChange={() => onToggleSkip(g.id)}
          />
          本组跳过
        </label>
      </div>
      {open && (
        <div className="gbody">
          {g.items.map((it) => {
            const key = `${g.id}:${it.abs}`;
            const isKeep = keepMap[g.id] === it.abs;
            const moved = movedSet.has(it.abs);
            const b = moved
              ? { cls: 'badge moved', label: '已移动' }
              : isKeep
                ? { cls: 'badge keep', label: '保留' }
                : { cls: 'badge move', label: '待移动' };
            return (
              <div className={'row' + (moved ? ' moved' : '')} key={key}>
                <Thumb abs={it.abs} kind={it.kind} />
                <div className="info">
                  <div className="fname">{basename(it.abs)}</div>
                  <div className="fpath" title={it.abs}>{it.abs}</div>
                </div>
                <div className="meta">{fmtBytes(it.size)}</div>
                <div className="pick">
                  <label>
                    <input
                      type="radio"
                      name={`keep-${g.id}`}
                      checked={isKeep}
                      disabled={moved || isSkipped}
                      onChange={() => onKeep(g.id, it.abs)}
                    />
                    保留
                  </label>
                  <span className={b.cls}>{b.label}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}