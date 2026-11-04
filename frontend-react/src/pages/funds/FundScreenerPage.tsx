import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import PageHeader from '../../components/PageHeader';
import { formatCompactInr, formatPct, formatRatio } from '../../lib/format';
import { METRIC_PERIODS, SCREEN_SORT_OPTIONS } from '../../lib/fundMetrics';

const PAGE_SIZE = 50;
const MAX_COMPARE = 10;

function toFraction(percentInput: string): string | undefined {
  const trimmed = percentInput.trim();
  if (!trimmed) return undefined;
  const n = Number(trimmed);
  if (Number.isNaN(n)) return undefined;
  return String(n / 100);
}

export default function FundScreenerPage() {
  const navigate = useNavigate();
  const [query, setQuery] = React.useState('');
  const [debouncedQuery, setDebouncedQuery] = React.useState('');
  const [amc, setAmc] = React.useState('All');
  const [category, setCategory] = React.useState('All');
  const [subcategory, setSubcategory] = React.useState('All');
  const [planType, setPlanType] = React.useState('All');
  const [optionType, setOptionType] = React.useState('All');
  const [metricPeriod, setMetricPeriod] = React.useState('1Y');
  const [minTrailingPct, setMinTrailingPct] = React.useState('');
  const [minSharpe, setMinSharpe] = React.useState('');
  const [maxDdPct, setMaxDdPct] = React.useState('');
  const [maxExpensePct, setMaxExpensePct] = React.useState('');
  const [minAumCr, setMinAumCr] = React.useState('');
  const [sortBy, setSortBy] = React.useState('trailing_return');
  const [sortDir, setSortDir] = React.useState('desc');
  const [offset, setOffset] = React.useState(0);
  const [selected, setSelected] = React.useState<string[]>([]);

  React.useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  React.useEffect(() => {
    setOffset(0);
  }, [
    debouncedQuery,
    amc,
    category,
    subcategory,
    planType,
    optionType,
    metricPeriod,
    minTrailingPct,
    minSharpe,
    maxDdPct,
    maxExpensePct,
    minAumCr,
    sortBy,
    sortDir,
  ]);

  const amcs = useQuery({ queryKey: ['filters', 'amc'], queryFn: () => api.filters('amc') });
  const categories = useQuery({ queryKey: ['filters', 'category'], queryFn: () => api.filters('category') });
  const subcategories = useQuery({
    queryKey: ['filters', 'subcategory'],
    queryFn: () => api.filters('subcategory'),
  });

  const params = React.useMemo(() => {
    const p = new URLSearchParams({
      search: debouncedQuery,
      amc,
      category,
      subcategory,
      plan_type: planType,
      option_type: optionType,
      metric_period: metricPeriod,
      sort_by: sortBy,
      sort_dir: sortDir,
      limit: String(PAGE_SIZE),
      offset: String(offset),
    });
    const minTrailing = toFraction(minTrailingPct);
    if (minTrailing != null) p.set('min_trailing', minTrailing);
    if (minSharpe.trim()) p.set('min_sharpe', minSharpe.trim());
    const maxDd = toFraction(maxDdPct);
    if (maxDd != null) p.set('max_drawdown', String(-Math.abs(Number(maxDd))));
    const maxExpense = toFraction(maxExpensePct);
    if (maxExpense != null) p.set('max_expense_ratio', maxExpense);
    if (minAumCr.trim()) {
      const cr = Number(minAumCr.trim());
      if (!Number.isNaN(cr)) p.set('min_aum', String(cr * 1e7));
    }
    return p.toString();
  }, [
    debouncedQuery,
    amc,
    category,
    subcategory,
    planType,
    optionType,
    metricPeriod,
    minTrailingPct,
    minSharpe,
    maxDdPct,
    maxExpensePct,
    minAumCr,
    sortBy,
    sortDir,
    offset,
  ]);

  const screen = useQuery({
    queryKey: ['fund-screen', params],
    queryFn: () => api.fundScreen(params),
  });

  const rows = screen.data?.rows || [];
  const total = screen.data?.total || 0;
  const showingFrom = rows.length ? offset + 1 : 0;
  const showingTo = offset + rows.length;
  const canPrev = offset > 0;
  const canNext = offset + PAGE_SIZE < total;

  const toggleCode = (code: string) => {
    setSelected((prev) => {
      if (prev.includes(code)) return prev.filter((c) => c !== code);
      if (prev.length >= MAX_COMPARE) return prev;
      return [...prev, code];
    });
  };

  const goCompare = () => {
    if (!selected.length) return;
    const q = new URLSearchParams({
      scheme_codes: selected.join(','),
      metric_period: metricPeriod,
    });
    navigate(`/mutualfunds/compare?${q}`);
  };

  return (
    <>
      <PageHeader
        title="Fund screener"
        subtitle="Filter by returns, risk, AUM, and expense using latest metric snapshots."
        actions={
          <div className="page-header-actions-row">
            <Link className="text-link" to="/mutualfunds">
              Browse list
            </Link>
            <button type="button" className="primary-btn" disabled={!selected.length} onClick={goCompare}>
              Compare selected ({selected.length}/{MAX_COMPARE})
            </button>
          </div>
        }
      />
      <section className="panel fund-list-panel">
        <div className="fund-toolbar fund-screener-toolbar">
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
          <label className="stock-field">
            <span>Plan</span>
            <select value={planType} onChange={(event) => setPlanType(event.target.value)}>
              <option value="All">All</option>
              <option value="DIRECT">Direct</option>
              <option value="REGULAR">Regular</option>
            </select>
          </label>
          <label className="stock-field">
            <span>Option</span>
            <select value={optionType} onChange={(event) => setOptionType(event.target.value)}>
              <option value="All">All</option>
              <option value="GROWTH">Growth</option>
              <option value="IDCW">IDCW</option>
            </select>
          </label>
          <label className="stock-field">
            <span>Metric period</span>
            <select value={metricPeriod} onChange={(event) => setMetricPeriod(event.target.value)}>
              {METRIC_PERIODS.map((period) => (
                <option key={period} value={period}>
                  {period}
                </option>
              ))}
            </select>
          </label>
          <label className="stock-field">
            <span>Min trailing %</span>
            <input
              type="number"
              step="0.1"
              placeholder="e.g. 12"
              value={minTrailingPct}
              onChange={(event) => setMinTrailingPct(event.target.value)}
            />
          </label>
          <label className="stock-field">
            <span>Min Sharpe</span>
            <input
              type="number"
              step="0.1"
              placeholder="e.g. 0.8"
              value={minSharpe}
              onChange={(event) => setMinSharpe(event.target.value)}
            />
          </label>
          <label className="stock-field">
            <span>Max loss % (DD)</span>
            <input
              type="number"
              step="0.1"
              placeholder="e.g. 20"
              value={maxDdPct}
              onChange={(event) => setMaxDdPct(event.target.value)}
            />
          </label>
          <label className="stock-field">
            <span>Max expense %</span>
            <input
              type="number"
              step="0.01"
              placeholder="e.g. 1.0"
              value={maxExpensePct}
              onChange={(event) => setMaxExpensePct(event.target.value)}
            />
          </label>
          <label className="stock-field">
            <span>Min AUM (Cr)</span>
            <input
              type="number"
              step="1"
              placeholder="e.g. 500"
              value={minAumCr}
              onChange={(event) => setMinAumCr(event.target.value)}
            />
          </label>
          <label className="stock-field">
            <span>Sort by</span>
            <select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
              {SCREEN_SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="stock-field">
            <span>Sort dir</span>
            <select value={sortDir} onChange={(event) => setSortDir(event.target.value)}>
              <option value="desc">Desc</option>
              <option value="asc">Asc</option>
            </select>
          </label>
        </div>

        {screen.isLoading && <div className="loading">Screening mutual funds…</div>}
        {screen.error && <div className="empty">{(screen.error as Error).message}</div>}
        {!screen.isLoading && !rows.length && <div className="empty">No funds match these filters.</div>}

        {rows.length > 0 && (
          <>
            <p className="result-count">
              Showing {showingFrom}–{showingTo} of {total} · period {screen.data?.metric_period || metricPeriod}
            </p>
            <div className="table-wrap stock-table-wrap">
              <table className="stock-table">
                <thead>
                  <tr>
                    <th aria-label="Select" />
                    <th>Scheme code</th>
                    <th>Scheme name</th>
                    <th>AMC</th>
                    <th>Category</th>
                    <th>Trailing</th>
                    <th>CAGR</th>
                    <th>Sharpe</th>
                    <th>Max DD</th>
                    <th>AUM</th>
                    <th>Expense</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row: any) => {
                    const checked = selected.includes(row.scheme_code);
                    const disabled = !checked && selected.length >= MAX_COMPARE;
                    return (
                      <tr key={row.scheme_code}>
                        <td>
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={disabled}
                            onChange={() => toggleCode(row.scheme_code)}
                            aria-label={`Select ${row.scheme_code}`}
                          />
                        </td>
                        <td className="symbol-cell">
                          <Link to={`/mutualfunds/${encodeURIComponent(row.scheme_code)}`}>
                            {row.scheme_code}
                          </Link>
                        </td>
                        <td className="company-cell">{row.scheme_name || '—'}</td>
                        <td>{row.amc_name || '—'}</td>
                        <td>{row.category_name || '—'}</td>
                        <td>{formatPct(row.trailing_return)}</td>
                        <td>{formatPct(row.cagr)}</td>
                        <td>{formatRatio(row.sharpe)}</td>
                        <td>{formatPct(row.maximum_drawdown)}</td>
                        <td>{formatCompactInr(row.aum)}</td>
                        <td>{formatPct(row.expense_ratio)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="pager">
              <button type="button" disabled={!canPrev} onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}>
                Previous
              </button>
              <span>
                Offset {offset} · page size {PAGE_SIZE}
              </span>
              <button type="button" disabled={!canNext} onClick={() => setOffset((o) => o + PAGE_SIZE)}>
                Next
              </button>
            </div>
          </>
        )}
      </section>
    </>
  );
}
