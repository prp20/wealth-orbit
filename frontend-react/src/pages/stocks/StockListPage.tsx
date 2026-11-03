import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import PageHeader from '../../components/PageHeader';

const PAGE_SIZE = 25;

export default function StockListPage() {
  const [query, setQuery] = React.useState('');
  const [debouncedQuery, setDebouncedQuery] = React.useState('');
  const [sector, setSector] = React.useState('All');
  const [industry, setIndustry] = React.useState('All');
  const [page, setPage] = React.useState(1);

  React.useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  React.useEffect(() => {
    setPage(1);
  }, [debouncedQuery, sector, industry]);

  const sectors = useQuery({ queryKey: ['sectors'], queryFn: api.sectors });
  const industries = useQuery({ queryKey: ['filters', 'industry'], queryFn: () => api.filters('industry') });
  const stocks = useQuery({
    queryKey: ['stocks', debouncedQuery, sector, industry],
    queryFn: () =>
      api.stocks(
        new URLSearchParams({
          search: debouncedQuery,
          sector,
          industry,
        }).toString(),
      ),
  });

  const rows = stocks.data || [];
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * PAGE_SIZE;
  const pageRows = rows.slice(start, start + PAGE_SIZE);
  const showingFrom = rows.length ? start + 1 : 0;
  const showingTo = Math.min(start + PAGE_SIZE, rows.length);

  return (
    <>
      <PageHeader title="Stocks" subtitle="Browse, filter, and open a decision-ready stock view." />
      <section className="panel stock-list-panel">
        <div className="stock-toolbar">
          <label className="stock-field">
            <span>Search</span>
            <input
              className="search"
              placeholder="Symbol or company…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label className="stock-field">
            <span>Sector</span>
            <select value={sector} onChange={(event) => setSector(event.target.value)}>
              <option value="All">All sectors</option>
              {(sectors.data || []).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="stock-field">
            <span>Industry</span>
            <select value={industry} onChange={(event) => setIndustry(event.target.value)}>
              <option value="All">All industries</option>
              {(industries.data || []).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>

        {stocks.isLoading && <div className="loading">Loading stocks…</div>}
        {stocks.error && <div className="empty">{(stocks.error as Error).message}</div>}
        {!stocks.isLoading && !rows.length && <div className="empty">No stocks match these filters.</div>}

        {rows.length > 0 && (
          <>
            <p className="result-count">
              Showing {showingFrom}–{showingTo} of {rows.length}
            </p>
            <div className="table-wrap stock-table-wrap">
              <table className="stock-table">
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
                  {pageRows.map((row: any) => (
                    <tr key={row.trading_symbol}>
                      <td className="symbol-cell">
                        <Link to={`/stocks/${encodeURIComponent(row.trading_symbol)}`}>
                          {row.trading_symbol}
                        </Link>
                      </td>
                      <td className="company-cell">{row.company_name || '—'}</td>
                      <td>{row.exchange || '—'}</td>
                      <td>{row.sector_name || '—'}</td>
                      <td>{row.industry_name || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pager">
              <button type="button" disabled={safePage <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                Previous
              </button>
              <span>
                Page {safePage} of {totalPages}
              </span>
              <button
                type="button"
                disabled={safePage >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
              </button>
            </div>
          </>
        )}
      </section>
    </>
  );
}
