import React from 'react';
import { fmtBytes } from '../api';
import { GroupCard, REASON_CLS, REASON_LABEL, basename } from './GroupCard';

const PAGE_SIZE = 60;

export default function Results({
  groups, stats, keepMap, onKeep, skipSet, onToggleSkip,
  movedSet, expandedMap, onToggleExpand,
  filter, onFilter, page, onPage,
  onMove, movedDisabled, canMove,
  preview, onClosePreview, onConfirmPreview, confirmDisabled,
}) {
  const visible = groups.filter((g) => {
    if (!filter) return true;
    return g.items.some((it) => basename(it.abs).toLowerCase().includes(filter));
  });
  const totalPages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const start = page * PAGE_SIZE;
  const slice = visible.slice(start, start + PAGE_SIZE);

  return (
    <>
      <div className="stats">
        <div className="st"><span className="st-k">重复组</span><b>{stats.groups ?? 0}</b></div>
        <div className="st"><span className="st-k">文件</span><b>{stats.files ?? 0}</b></div>
        <div className="st"><span className="st-k">待移动</span><b>{stats.to_move ?? 0}</b></div>
        <div className="st"><span className="st-k">可释放</span><b>{fmtBytes(stats.freed_bytes ?? 0)}</b></div>
        {canMove && (
          <button className="warn" onClick={onMove} disabled={movedDisabled}>
            移动到 temp（释出清单）
          </button>
        )}
      </div>

      {visible.length > 0 && (
        <div className="toolbar">
          <input
            type="text"
            placeholder="按文件名过滤分组…"
            value={filter}
            onChange={(e) => onFilter(e.target.value)}
            autoComplete="off"
          />
          <span className="pager">
            <span className="pager-txt">{page + 1} / {totalPages} 页</span>
            <button onClick={() => onPage(page - 1)} disabled={page <= 0}>‹</button>
            <button onClick={() => onPage(page + 1)} disabled={page + 1 >= totalPages}>›</button>
          </span>
        </div>
      )}

      {visible.length === 0 ? (
        <div className="empty-hint">没有发现重复的文件。</div>
      ) : (
        <div className="results">
          {slice.map((g) => (
            <GroupCard
              key={g.id}
              g={g}
              keepMap={keepMap}
              onKeep={onKeep}
              skipSet={skipSet}
              onToggleSkip={onToggleSkip}
              movedSet={movedSet}
              expanded={expandedMap}
              onToggleExpand={onToggleExpand}
            />
          ))}
        </div>
      )}

      {preview && (
        <div className="preview">
          <h3>
            移动预览{' '}
            <span className="pv-mode">{preview.dry ? '（预览，未执行）' : '（已执行）'}</span>
            <span className="pv-dest">→ {preview.dest}</span>
          </h3>
          <div className="preview-list">
            {preview.items.length === 0 && <div className="pv-row">没有需要移动的文件。</div>}
            {preview.items.map((p, i) => (
              <div className={'pv-row ' + (REASON_CLS[p.reason] || '')} key={i}>
                <span className="pv-from" title={p.from}>{basename(p.from)}</span>
                <span className="pv-arrow">→</span>
                <span className="pv-to" title={p.to}>{p.to}</span>
                <span className={'pv-tag ' + (REASON_CLS[p.reason] || '')}>
                  {REASON_LABEL[p.reason] || p.reason}
                </span>
              </div>
            ))}
          </div>
          <p className="preview-note">黄色 = 目标已存在，将跳过（不覆盖）。确认前不会改动任何文件。</p>
          {preview.dry && (
            <button className="danger" onClick={onConfirmPreview} disabled={confirmDisabled}>
              确认移动
            </button>
          )}
          <button className="ghost" onClick={onClosePreview}>关闭预览</button>
        </div>
      )}
    </>
  );
}