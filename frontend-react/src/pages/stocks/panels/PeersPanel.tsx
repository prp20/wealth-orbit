import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';

const fmt = (value: unknown) => (value == null || value === '' ? '—' : String(value));

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
        <div className="filters">
          <select value={by} onChange={(event) => setBy(event.target.value)}>
            <option value="sector">Sector</option>
            <option value="industry">Industry</option>
          </select>
        </div>
      </div>
      {peers.isLoading && <div className="loading">Loading peers…</div>}
      {peers.error && <div className="empty">{(peers.error as Error).message}</div>}
      {!peers.isLoading && !(peers.data?.peers || []).length && (
        <div className="empty">No peers found for this {by}.</div>
      )}
      {(peers.data?.peers || []).length > 0 && (
        <div className="table-wrap">
          <table>
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
                <td>{symbol}</td>
                <td>{current.data?.company_name || '—'}</td>
                <td>{fmt(current.data?.latest_price?.close)}</td>
                <td>{fmt(currentMetrics?.stock_pe)}</td>
                <td>{fmt(currentMetrics?.price_to_book)}</td>
                <td>{fmt(currentMetrics?.roe)}</td>
                <td>{fmt(currentMetrics?.roce)}</td>
                <td>{fmt(currentMetrics?.market_cap)}</td>
              </tr>
              {(peers.data?.peers || []).map((peer: any) => (
                <tr key={peer.trading_symbol}>
                  <td>
                    <Link to={`/stocks/${encodeURIComponent(peer.trading_symbol)}`}>
                      {peer.trading_symbol}
                    </Link>
                  </td>
                  <td>{peer.company_name || '—'}</td>
                  <td>{fmt(peer.latest_close)}</td>
                  <td>{fmt(peer.latest_metrics?.stock_pe)}</td>
                  <td>{fmt(peer.latest_metrics?.price_to_book)}</td>
                  <td>{fmt(peer.latest_metrics?.roe)}</td>
                  <td>{fmt(peer.latest_metrics?.roce)}</td>
                  <td>{fmt(peer.latest_metrics?.market_cap)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
