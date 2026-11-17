import React from 'react';
import { formatDisplayDate, formatRatio } from '../lib/format';
import { indexLabel } from '../lib/homeIndexes';

export function formatChange(value: unknown) {
  if (value == null || value === '') return '—';
  const amount = Number(value);
  if (Number.isNaN(amount)) return '—';
  const text = formatRatio(Math.abs(amount));
  if (amount > 0) return `+${text}%`;
  if (amount < 0) return `-${text}%`;
  return `${text}%`;
}

export function changeClass(value: unknown): string | undefined {
  if (value == null || value === '') return undefined;
  const amount = Number(value);
  if (Number.isNaN(amount) || amount === 0) return undefined;
  return amount < 0 ? 'change-down' : 'change-up';
}

function newestDate(rows: any[]) {
  const dates = rows.map((row) => String(row.as_of || '')).filter(Boolean).sort();
  return dates[dates.length - 1];
}

export default function IndexStrip({
  rows,
  lead,
}: {
  rows: any[];
  lead?: React.ReactNode;
}) {
  const newest = formatDisplayDate(newestDate(rows));
  return (
    <div className="index-strip">
      {lead}
      {rows.map((row) => {
        const asOf = formatDisplayDate(row.as_of);
        return (
          <article className="index-tile" key={row.index_code}>
            <small>{indexLabel(row)}</small>
            <strong>{formatRatio(row.close)}</strong>
            <span className={changeClass(row.change_pct)}>{formatChange(row.change_pct)}</span>
            {asOf !== newest && <em>As of {asOf}</em>}
          </article>
        );
      })}
    </div>
  );
}

export { newestDate };
