import React from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api';
import PageHeader from '../../components/PageHeader';
import { formatCompactInr, formatPct, formatRatio } from '../../lib/format';

type ScreenParam = {
  name: string;
  type: string;
  default?: unknown;
  description?: string | null;
};

type ScreenMeta = {
  name: string;
  version: string;
  description: string;
  asset_class: string;
  parameters: ScreenParam[];
};

type ScreenEntry = {
  screen_id: string;
  path: string;
  enabled: boolean;
  status: string;
  meta: ScreenMeta | null;
  errors: string[];
  warnings?: string[];
};

const PARAM_LABELS: Record<string, string> = {
  max_pe: 'Max PE',
  min_roe: 'Min ROE',
  min_roa: 'Min ROA',
  min_roce: 'Min ROCE',
  min_dividend_yield: 'Min dividend yield',
  max_dividend_payout: 'Max dividend payout',
  min_profit_growth_3y: 'Min profit growth (3y)',
  min_sales_growth_3y: 'Min sales growth (3y)',
  max_debt_to_equity: 'Max debt / equity',
  min_market_cap_cr: 'Min market cap (Cr)',
  max_market_cap_cr: 'Max market cap (Cr)',
  min_promoter_holding: 'Min promoter holding',
  max_pledged_pct: 'Max pledged %',
  min_operating_margin: 'Min operating margin',
  min_interest_coverage: 'Min interest coverage',
  min_earnings_yield: 'Min earnings yield',
  min_asset_turnover: 'Min asset turnover',
  min_current_ratio: 'Min current ratio',
  min_cfo_to_profit: 'Min CFO / profit',
  exclude_bfsi: 'Exclude BFSI',
};

function paramLabel(name: string): string {
  if (PARAM_LABELS[name]) return PARAM_LABELS[name];
  return name
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function paramDefaults(meta: ScreenMeta | null | undefined): Record<string, string> {
  const values: Record<string, string> = {};
  for (const param of meta?.parameters || []) {
    values[param.name] = param.default == null ? '' : String(param.default);
  }
  return values;
}

function coerceParams(meta: ScreenMeta | null | undefined, raw: Record<string, string>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const param of meta?.parameters || []) {
    const text = (raw[param.name] ?? '').trim();
    if (!text) {
      out[param.name] = param.default;
      continue;
    }
    if (param.type === 'float') out[param.name] = Number(text);
    else if (param.type === 'int') out[param.name] = Number.parseInt(text, 10);
    else if (param.type === 'bool') out[param.name] = text === 'true' || text === '1';
    else out[param.name] = text;
  }
  return out;
}

export default function StockScreenerPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = React.useState<string>('');
  const [paramValues, setParamValues] = React.useState<Record<string, string>>({});
  const [runError, setRunError] = React.useState<string | null>(null);
  const [hasRun, setHasRun] = React.useState(false);
  const [resultRows, setResultRows] = React.useState<any[]>([]);
  const [resultMeta, setResultMeta] = React.useState<{ name?: string; total?: number } | null>(null);

  const screensQuery = useQuery({
    queryKey: ['stock-screens'],
    queryFn: () => api.stockScreens(false),
  });

  const screens: ScreenEntry[] = screensQuery.data?.screens || [];
  const runnable = screens.filter((item) => item.enabled && item.status === 'ok');
  const failed = screens.filter((item) => item.status !== 'ok');
  const selected = screens.find((item) => item.screen_id === selectedId) || runnable[0] || null;

  React.useEffect(() => {
    if (!selected) return;
    if (selectedId !== selected.screen_id) setSelectedId(selected.screen_id);
    setParamValues(paramDefaults(selected.meta));
    setRunError(null);
  }, [selected?.screen_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = useMutation({
    mutationFn: () => api.refreshStockScreens(),
    onSuccess: (data) => {
      queryClient.setQueryData(['stock-screens'], data);
      setRunError(null);
    },
    onError: (err) => setRunError((err as Error).message),
  });

  const run = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error('Select a screen first');
      const params = coerceParams(selected.meta, paramValues);
      return api.runStockScreen(selected.screen_id, params);
    },
    onSuccess: (data) => {
      setHasRun(true);
      setResultRows(data.rows || []);
      setResultMeta({ name: data.name, total: data.total });
      setRunError(null);
    },
    onError: (err) => {
      setHasRun(true);
      setResultRows([]);
      setResultMeta(null);
      setRunError((err as Error).message);
    },
  });

  const total = resultMeta?.total ?? resultRows.length;
  const showingFrom = resultRows.length ? 1 : 0;
  const showingTo = resultRows.length;

  return (
    <>
      <PageHeader
        title="Stock screener"
        subtitle="Filter stocks with validated screens on stored metrics."
        actions={
          <div className="page-header-actions-row">
            <Link className="text-link" to="/stocks">
              Browse list
            </Link>
            <button
              type="button"
              className="text-link"
              disabled={refresh.isPending}
              onClick={() => refresh.mutate()}
            >
              {refresh.isPending ? 'Refreshing…' : 'Refresh screens'}
            </button>
            <button
              type="button"
              className="primary-btn"
              disabled={!selected || run.isPending || !runnable.length}
              onClick={() => run.mutate()}
            >
              {run.isPending ? 'Running…' : 'Run screen'}
            </button>
          </div>
        }
      />

      <section className="panel fund-list-panel">
        {screensQuery.isLoading && <div className="loading">Loading screens…</div>}
        {screensQuery.error && <div className="empty">{(screensQuery.error as Error).message}</div>}

        {!screensQuery.isLoading && !runnable.length && (
          <div className="empty">
            {failed.length
              ? 'No runnable screens yet. Fix validation errors below, then refresh.'
              : 'No screen plugins found. Add a file under screens/stock/user/ and refresh.'}
          </div>
        )}

        {!!runnable.length && (
          <div className="fund-toolbar fund-screener-toolbar">
            <label className="stock-field">
              <span>Screen</span>
              <select
                value={selected?.screen_id || ''}
                onChange={(event) => {
                  setSelectedId(event.target.value);
                  setHasRun(false);
                  setResultRows([]);
                  setResultMeta(null);
                  setRunError(null);
                }}
              >
                {runnable.map((item) => (
                  <option key={item.screen_id} value={item.screen_id}>
                    {item.meta?.name || item.screen_id}
                  </option>
                ))}
              </select>
            </label>

            {(selected?.meta?.parameters || []).map((param) => (
              <label key={param.name} className="stock-field">
                <span>{paramLabel(param.name)}</span>
                <input
                  type={param.type === 'str' ? 'text' : 'number'}
                  step={param.type === 'int' ? '1' : 'any'}
                  value={paramValues[param.name] ?? ''}
                  onChange={(event) =>
                    setParamValues((prev) => ({ ...prev, [param.name]: event.target.value }))
                  }
                />
              </label>
            ))}
          </div>
        )}

        {selected?.meta?.description && <p className="panel-subtitle">{selected.meta.description}</p>}
        {runError && <div className="empty">{runError}</div>}

        {run.isPending && <div className="loading">Screening stocks…</div>}

        {hasRun && !run.isPending && !runError && !resultRows.length && (
          <div className="empty">No stocks match these filters.</div>
        )}

        {!hasRun && !run.isPending && !!runnable.length && !runError && (
          <div className="empty">Choose a screen and run it against the stored metrics snapshot.</div>
        )}

        {resultRows.length > 0 && (
          <>
            <p className="result-count">
              Showing {showingFrom}–{showingTo} of {total}
              {resultMeta?.name ? ` · ${resultMeta.name}` : ''}
            </p>
            <div className="table-wrap stock-table-wrap">
              <table className="stock-table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Company</th>
                    <th>Sector</th>
                    <th>PE</th>
                    <th>ROE</th>
                    <th>Div yield</th>
                    <th>Market cap</th>
                  </tr>
                </thead>
                <tbody>
                  {resultRows.map((row) => {
                    const symbol = String(row.trading_symbol || '');
                    return (
                      <tr key={symbol}>
                        <td className="symbol-cell">
                          <Link to={`/stocks/${encodeURIComponent(symbol)}`}>{symbol}</Link>
                        </td>
                        <td className="company-cell">
                          <Link to={`/stocks/${encodeURIComponent(symbol)}`}>
                            {row.company_name || '—'}
                          </Link>
                        </td>
                        <td>{row.sector_name || '—'}</td>
                        <td>{row.stock_pe == null ? '—' : formatRatio(row.stock_pe)}</td>
                        <td>{row.roe == null ? '—' : formatPct(row.roe)}</td>
                        <td>{row.dividend_yield == null ? '—' : formatRatio(row.dividend_yield)}</td>
                        <td>{row.market_cap == null ? '—' : formatCompactInr(row.market_cap)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}

        {!!failed.length && (
          <p className="panel-subtitle">
            {failed.length} screen{failed.length === 1 ? '' : 's'} failed validation
            {failed
              .slice(0, 3)
              .map((item) => ` · ${item.meta?.name || item.screen_id}: ${(item.errors || [])[0] || item.status}`)
              .join('')}
            {failed.length > 3 ? ' · …' : ''}
          </p>
        )}
      </section>
    </>
  );
}
