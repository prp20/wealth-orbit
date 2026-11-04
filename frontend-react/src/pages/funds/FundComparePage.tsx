import React from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import PageHeader from '../../components/PageHeader';
import { formatCompactInr, formatDate, formatInr, formatPct, formatRatio } from '../../lib/format';
import { METRIC_PERIODS } from '../../lib/fundMetrics';

type MetricRow = {
  label: string;
  value: (fund: any) => React.ReactNode;
};

export default function FundComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const codesParam = searchParams.get('scheme_codes') || '';
  const metricPeriod = searchParams.get('metric_period') || '1Y';
  const codes = React.useMemo(
    () =>
      codesParam
        .split(',')
        .map((c) => c.trim())
        .filter(Boolean)
        .slice(0, 10),
    [codesParam],
  );

  const compare = useQuery({
    queryKey: ['fund-compare', codes.join(','), metricPeriod],
    queryFn: () => api.fundCompare(codes, metricPeriod),
    enabled: codes.length > 0,
  });

  const funds = compare.data || [];
  const planTypes = new Set(funds.map((f: any) => f.plan_type).filter(Boolean));
  const asOfDates = new Set(
    funds.map((f: any) => f.metrics?.as_of_date).filter(Boolean).map((d: unknown) => String(d).slice(0, 10)),
  );
  const mixedPlans = planTypes.size > 1;
  const mixedAsOf = asOfDates.size > 1;

  const setPeriod = (period: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('metric_period', period);
    if (codes.length) next.set('scheme_codes', codes.join(','));
    setSearchParams(next);
  };

  const rows: MetricRow[] = [
    {
      label: 'Latest NAV',
      value: (f) =>
        f.latest_nav?.nav != null
          ? `${formatInr(f.latest_nav.nav)} (${formatDate(f.latest_nav.date)})`
          : '—',
    },
    { label: 'Metrics as of', value: (f) => formatDate(f.metrics?.as_of_date) },
    { label: 'Trailing return', value: (f) => formatPct(f.metrics?.trailing_return) },
    { label: 'CAGR', value: (f) => formatPct(f.metrics?.cagr) },
    { label: 'Std deviation', value: (f) => formatPct(f.metrics?.standard_deviation) },
    { label: 'Sharpe', value: (f) => formatRatio(f.metrics?.sharpe) },
    { label: 'Sortino', value: (f) => formatRatio(f.metrics?.sortino) },
    { label: 'Max drawdown', value: (f) => formatPct(f.metrics?.maximum_drawdown) },
    { label: 'Alpha', value: (f) => formatRatio(f.metrics?.alpha) },
    { label: 'Beta', value: (f) => formatRatio(f.metrics?.beta) },
    { label: 'AUM', value: (f) => formatCompactInr(f.enrichment?.aum) },
    { label: 'Expense ratio', value: (f) => formatPct(f.enrichment?.expense_ratio) },
    { label: 'Exit load', value: (f) => f.enrichment?.exit_load || '—' },
    {
      label: 'Benchmark',
      value: (f) =>
        f.benchmark?.available
          ? f.benchmark.index_name || f.benchmark.index_code || '—'
          : '—',
    },
    { label: 'Fund manager', value: (f) => f.enrichment?.fund_manager || '—' },
    { label: 'AMC', value: (f) => f.amc_name || '—' },
    { label: 'Category', value: (f) => f.category_name || '—' },
    { label: 'Plan / option', value: (f) => `${f.plan_type || '—'} / ${f.option_type || '—'}` },
  ];

  return (
    <>
      <PageHeader
        title="Compare funds"
        subtitle="Side-by-side metrics for up to 10 schemes."
        actions={
          <div className="page-header-actions-row">
            <Link className="text-link" to="/mutualfunds/screen">
              Back to screener
            </Link>
            <Link className="text-link" to="/mutualfunds">
              Browse list
            </Link>
          </div>
        }
      />
      <section className="panel fund-list-panel">
        <div className="fund-toolbar fund-compare-toolbar">
          <label className="stock-field">
            <span>Metric period</span>
            <select value={metricPeriod} onChange={(event) => setPeriod(event.target.value)}>
              {METRIC_PERIODS.map((period) => (
                <option key={period} value={period}>
                  {period}
                </option>
              ))}
            </select>
          </label>
          <p className="result-count fund-compare-codes">
            {codes.length
              ? `${codes.length} scheme${codes.length === 1 ? '' : 's'} selected`
              : 'No schemes selected'}
          </p>
        </div>

        {!codes.length && (
          <div className="empty">
            Choose funds from the{' '}
            <Link to="/mutualfunds/screen">screener</Link> to compare.
          </div>
        )}
        {codes.length > 0 && compare.isLoading && <div className="loading">Loading comparison…</div>}
        {codes.length > 0 && compare.error && (
          <div className="empty">{(compare.error as Error).message}</div>
        )}
        {codes.length > 0 && !compare.isLoading && !funds.length && (
          <div className="empty">No matching schemes found for the selected codes.</div>
        )}

        {funds.length > 0 && (mixedPlans || mixedAsOf) && (
          <div className="empty" style={{ marginBottom: 12 }}>
            {mixedPlans ? 'Selected schemes mix plan types (e.g. Direct vs Regular) — compare carefully. ' : ''}
            {mixedAsOf ? 'Metric as-of dates differ across columns — observation windows are not fully aligned.' : ''}
          </div>
        )}

        {funds.length > 0 && (
          <div className="table-wrap stock-table-wrap fund-compare-table-wrap">
            <table className="stock-table fund-compare-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  {funds.map((fund: any) => (
                    <th key={fund.scheme_code}>
                      <Link to={`/mutualfunds/${encodeURIComponent(fund.scheme_code)}`}>
                        {fund.scheme_code}
                      </Link>
                      <div className="fund-compare-name">{fund.scheme_name || '—'}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.label}>
                    <td className="fund-compare-label">{row.label}</td>
                    {funds.map((fund: any) => (
                      <td key={`${fund.scheme_code}-${row.label}`}>{row.value(fund)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
