import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import ChartToolbar, { ChartRange, rangeToFromDate } from './ChartToolbar';

export default function MarketChart({ kind, id }: { kind: 'stock' | 'fund'; id: string }) {
  const [mode, setMode] = useState('line');
  const [range, setRange] = useState<ChartRange>('1Y');
  const fromDate = rangeToFromDate(range);
  const query = useQuery({
    queryKey: ['history', kind, id, range],
    queryFn: () =>
      kind === 'stock' ? api.stockHistory(id, fromDate || '', '') : api.fundHistory(id, fromDate || '', ''),
  });

  if (query.isLoading) return <div className="empty">Loading chart…</div>;
  const rows = query.data || [];
  if (!rows.length) return <div className="empty">No historical data available.</div>;

  const visible = range === 'MAX' && rows.length > 500 ? rows.slice(-500) : rows;
  const vals = visible.map((row) => Number(kind === 'stock' ? row.close : row.nav));
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const points = vals
    .map((value, index) => `${(index / (vals.length - 1 || 1)) * 100},${100 - ((value - min) / span) * 100}`)
    .join(' ');
  const volumes = kind === 'stock' ? visible.map((row) => Number(row.volume) || 0) : [];
  const maxVolume = Math.max(...volumes, 1);
  const label = (value: any) => {
    const date = new Date(`${value}T00:00:00`);
    return `${value} (${date.toLocaleDateString('en-IN', { weekday: 'short' })})`;
  };

  return (
    <section className="chart-card">
      <div className="chart-head">
        <h2>Price history</h2>
        <div className="chart-controls">
          <ChartToolbar range={range} onChange={setRange} />
          {kind === 'stock' && (
            <select value={mode} onChange={(event) => setMode(event.target.value)}>
              <option value="line">Line + volume</option>
              <option value="candles">Candlesticks + volume</option>
            </select>
          )}
        </div>
      </div>
      {mode === 'line' ? (
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="line-chart">
          <polyline
            points={points}
            fill="none"
            stroke="#42a87c"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      ) : (
        <div className="candle-chart">
          {visible.map((row, index) => {
            const open = +row.open;
            const close = +row.close;
            const high = +row.high;
            const low = +row.low;
            const wickTop = 100 - ((high - min) / span) * 100;
            const wickHeight = ((high - low) / span) * 100;
            const bodyTop = 100 - ((Math.max(open, close) - min) / span) * 100;
            const bodyHeight = Math.max(1, (Math.abs(close - open) / span) * 100);
            return (
              <i
                className="candle"
                key={index}
                style={{
                  left: `${(index / (visible.length - 1 || 1)) * 100}%`,
                  top: `${wickTop}%`,
                  height: `${Math.max(1, wickHeight)}%`,
                  background: close >= open ? '#42a87c' : '#d16d67',
                }}
              >
                <b
                  style={{
                    top: `${(Math.max(0, bodyTop - wickTop) / Math.max(0.01, wickHeight)) * 100}%`,
                    height: `${(bodyHeight / Math.max(0.01, wickHeight)) * 100}%`,
                  }}
                />
              </i>
            );
          })}
        </div>
      )}
      {kind === 'stock' && (
        <div className="volume-chart">
          {volumes.map((volume, index) => (
            <span key={index} style={{ height: `${(volume / maxVolume) * 100}%` }} />
          ))}
        </div>
      )}
      <small>
        {label(visible[0].date)} to {label(visible[visible.length - 1].date)} · {visible.length} points
      </small>
    </section>
  );
}
