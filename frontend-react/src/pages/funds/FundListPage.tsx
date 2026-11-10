import React from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import AddInstrumentDialog from '../../components/AddInstrumentDialog';
import PageHeader from '../../components/PageHeader';

const PAGE_SIZE = 25;

export default function FundListPage() {
  const [params] = useSearchParams();
  const [query, setQuery] = React.useState(params.get('search') || '');
  const [debouncedQuery, setDebouncedQuery] = React.useState('');
  const [amc, setAmc] = React.useState('All');
  const [category, setCategory] = React.useState('All');
  const [subcategory, setSubcategory] = React.useState('All');
  const [page, setPage] = React.useState(1);
  const [addOpen, setAddOpen] = React.useState(false);
  const [addCode, setAddCode] = React.useState('');

  React.useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  React.useEffect(() => {
    setPage(1);
  }, [debouncedQuery, amc, category, subcategory]);

  const amcs = useQuery({ queryKey: ['filters', 'amc'], queryFn: () => api.filters('amc') });
  const categories = useQuery({ queryKey: ['filters', 'category'], queryFn: () => api.filters('category') });
  const subcategories = useQuery({
    queryKey: ['filters', 'subcategory'],
    queryFn: () => api.filters('subcategory'),
  });
  const funds = useQuery({
    queryKey: ['funds', debouncedQuery, amc, category, subcategory],
    queryFn: () =>
      api.funds(
        new URLSearchParams({
          search: debouncedQuery,
          amc,
          category,
          subcategory,
        }).toString(),
      ),
  });

  const rows = funds.data || [];
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * PAGE_SIZE;
  const pageRows = rows.slice(start, start + PAGE_SIZE);
  const showingFrom = rows.length ? start + 1 : 0;
  const showingTo = Math.min(start + PAGE_SIZE, rows.length);

  return (
    <>
      <PageHeader
        title="Mutual funds"
        subtitle="Browse, filter, and open a decision-ready fund view."
        actions={
          <div className="page-header-actions-row">
            <Link className="text-link" to="/mutualfunds/screen">
              Screener
            </Link>
            <Link className="text-link" to="/mutualfunds/compare">
              Compare
            </Link>
          </div>
        }
      />
      <section className="panel fund-list-panel">
        <div className="fund-toolbar">
          <label className="stock-field">
            <span>Search</span>
            <input
              className="search"
              placeholder="Scheme name or code…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label className="stock-field">
            <span>AMC</span>
            <select value={amc} onChange={(event) => setAmc(event.target.value)}>
              <option value="All">All AMCs</option>
              {(amcs.data || []).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="stock-field">
            <span>Category</span>
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="All">All categories</option>
              {(categories.data || []).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="stock-field">
            <span>Subcategory</span>
            <select value={subcategory} onChange={(event) => setSubcategory(event.target.value)}>
              <option value="All">All subcategories</option>
              {(subcategories.data || []).map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <div className="toolbar-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => {
                setAddCode(debouncedQuery);
                setAddOpen(true);
              }}
            >
              Add
            </button>
          </div>
        </div>

        {funds.isLoading && <div className="loading">Loading mutual funds…</div>}
        {funds.error && <div className="empty">{(funds.error as Error).message}</div>}
        {!funds.isLoading && !rows.length && (
          <div className="empty empty-cta">
            <span>No funds match these filters.</span>
            {debouncedQuery && (
              <button
                type="button"
                className="primary-button"
                onClick={() => {
                  setAddCode(debouncedQuery);
                  setAddOpen(true);
                }}
              >
                Add “{debouncedQuery}” as scheme code?
              </button>
            )}
          </div>
        )}
        <AddInstrumentDialog
          open={addOpen}
          onClose={() => setAddOpen(false)}
          initialKind="fund"
          initialCode={addCode}
          allowedKinds={['fund']}
        />

        {rows.length > 0 && (
          <>
            <p className="result-count">
              Showing {showingFrom}–{showingTo} of {rows.length}
            </p>
            <div className="table-wrap stock-table-wrap">
              <table className="stock-table">
                <thead>
                  <tr>
                    <th>Scheme name</th>
                    <th>Scheme code</th>
                    <th>AMC</th>
                    <th>Category</th>
                    <th>Subcategory</th>
                    <th>Plan</th>
                    <th>Option</th>
                  </tr>
                </thead>
                <tbody>
                  {pageRows.map((row: any) => (
                    <tr key={row.scheme_code}>
                      <td className="company-cell">
                        <Link to={`/mutualfunds/${encodeURIComponent(row.scheme_code)}`}>
                          {row.scheme_name || row.scheme_code}
                        </Link>
                      </td>
                      <td className="scheme-code">{row.scheme_code}</td>
                      <td>{row.amc_name || '—'}</td>
                      <td>{row.category_name || '—'}</td>
                      <td>{row.subcategory_name || '—'}</td>
                      <td>{row.plan_type || '—'}</td>
                      <td>{row.option_type || '—'}</td>
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
