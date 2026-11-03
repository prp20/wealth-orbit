import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';

function Page({ title, subtitle, children }: { title: string; subtitle: string; children?: React.ReactNode }) {
  return (
    <>
      <header>
        <p className="eyebrow">Wealth Orbit</p>
        <h1>{title}</h1>
        <p className="subtitle">{subtitle}</p>
      </header>
      {children}
    </>
  );
}

export default function StockListPage() {
  const [query, setQuery] = React.useState('');
  const [sector, setSector] = React.useState('All');
  const [industry, setIndustry] = React.useState('All');
  const sectors = useQuery({ queryKey: ['sectors'], queryFn: api.sectors });
  const industries = useQuery({ queryKey: ['filters', 'industry'], queryFn: () => api.filters('industry') });
  const stocks = useQuery({
    queryKey: ['stocks', query, sector, industry],
    queryFn: () =>
      api.stocks(
        new URLSearchParams({
          search: query,
          sector,
          industry,
        }).toString(),
      ),
  });
  const rows = stocks.data || [];

  return (
    <Page title="Stocks" subtitle="Browse, filter, and open a decision-ready stock view.">
      <div className="filters stock-list-filters">
        <input
          className="search"
          placeholder="Search stocks…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select value={sector} onChange={(event) => setSector(event.target.value)}>
          <option value="All">All sectors</option>
          {(sectors.data || []).map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
        <select value={industry} onChange={(event) => setIndustry(event.target.value)}>
          <option value="All">All industries</option>
          {(industries.data || []).map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </div>
      <section className="panel">
        {stocks.isLoading && <div className="loading">Loading stocks…</div>}
        {stocks.error && <div className="empty">{(stocks.error as Error).message}</div>}
        {!stocks.isLoading && !rows.length && <div className="empty">No stocks match these filters.</div>}
        {rows.length > 0 && (
          <>
            <p className="result-count">Showing {rows.length} stock{rows.length === 1 ? '' : 's'}</p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Company</th>
                    <th>Exchange</th>
                    <th>Sector</th>
                    <th>Industry</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row: any) => (
                    <tr key={row.trading_symbol}>
                      <td>
                        <Link to={`/stocks/${encodeURIComponent(row.trading_symbol)}`}>
                          {row.trading_symbol}
                        </Link>
                      </td>
                      <td>{row.company_name || '—'}</td>
                      <td>{row.exchange || '—'}</td>
                      <td>{row.sector_name || '—'}</td>
                      <td>{row.industry_name || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </Page>
  );
}
