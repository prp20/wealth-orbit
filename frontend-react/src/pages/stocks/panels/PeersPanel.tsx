import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import { formatCompactInr, formatInr, formatPct, formatRatio } from '../../../lib/format';

export default function PeersPanel({ symbol }: { symbol: string }) {
  const [by, setBy] = React.useState('sector');
  const peers = useQuery({
    queryKey: ['stock-peers', symbol, by],
    queryFn: () => api.stockPeers(symbol, by, 8),
  });
  const current = useQuery({ queryKey: ['stock', symbol], queryFn: () => api.stock(symbol) });
  const currentMetrics = current.data?.latest_daily_metrics;

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Peers</h2>
          <p className="panel-subtitle">
            Side-by-side latest metrics vs {peers.data?.group || by} peers.
          </p>
        </div>
        <label className="stock-field inline-field">
          <span>Compare by</span>
          <select value={by} onChange={(event) => setBy(event.target.value)}>
            <option value="sector">Sector</option>
            <option value="industry">Industry</option>
          </select>
        </label>
      </div>
      {peers.isLoading && <div className="loading">Loading peers…</div>}
      {peers.error && <div className="empty">{(peers.error as Error).message}</div>}
      {!peers.isLoading && !(peers.data?.peers || []).length && (
        <div className="empty">No peers found for this {by}.</div>
      )}
      {(peers.data?.peers || []).length > 0 && (
        <div className="table-wrap">
          <table className="stock-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Name</th>
                <th>Close</th>
                <th>PE</th>
                <th>PB</th>
                <th>ROE</th>
                <th>ROCE</th>
                <th>MCap</th>
              </tr>
            </thead>
            <tbody>
              <tr className="peer-current">
                <td className="symbol-cell">{symbol}</td>
                <td className="company-cell">{current.data?.company_name || '—'}</td>
                <td>{formatInr(current.data?.latest_price?.close)}</td>
                <td>{formatRatio(currentMetrics?.stock_pe)}</td>
                <td>{formatRatio(currentMetrics?.price_to_book)}</td>
                <td>{formatPct(currentMetrics?.roe)}</td>
                <td>{formatPct(currentMetrics?.roce)}</td>
                <td>{formatCompactInr(currentMetrics?.market_cap)}</td>
              </tr>
              {(peers.data?.peers || []).map((peer: any) => (
                <tr key={peer.trading_symbol}>
                  <td className="symbol-cell">
                    <Link to={`/stocks/${encodeURIComponent(peer.trading_symbol)}`}>
                      {peer.trading_symbol}
                    </Link>
                  </td>
                  <td className="company-cell">{peer.company_name || '—'}</td>
                  <td>{formatInr(peer.latest_close)}</td>
                  <td>{formatRatio(peer.latest_metrics?.stock_pe)}</td>
                  <td>{formatRatio(peer.latest_metrics?.price_to_book)}</td>
                  <td>{formatPct(peer.latest_metrics?.roe)}</td>
                  <td>{formatPct(peer.latest_metrics?.roce)}</td>
                  <td>{formatCompactInr(peer.latest_metrics?.market_cap)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
