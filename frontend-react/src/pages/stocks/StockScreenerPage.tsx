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
  const [resultRows, setResultRows] = React.useState<any[]>([]);
  const [resultMeta, setResultMeta] = React.useState<{ name?: string; total?: number } | null>(null);

  const screensQuery = useQuery({
    queryKey: ['stock-screens'],
    queryFn: () => api.stockScreens(false),
  });

  const screens: ScreenEntry[] = screensQuery.data?.screens || [];
  const runnable = screens.filter((item) => item.enabled && item.status === 'ok');
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
      setResultRows(data.rows || []);
      setResultMeta({ name: data.name, total: data.total });
      setRunError(null);
    },
    onError: (err) => {
      setResultRows([]);
      setResultMeta(null);
      setRunError((err as Error).message);
    },
  });

  return (
    <>
      <PageHeader
        title="Stock screener"
        subtitle="Run validated Python screens on stored metrics — no live scrape, no SQL."
        actions={
          <div className="page-header-actions-row">
            <Link className="text-link" to="/stocks">
              Browse list
            </Link>
            <button
              type="button"
              className="primary-button secondary"
              disabled={refresh.isPending}
              onClick={() => refresh.mutate()}
            >
              {refresh.isPending ? 'Refreshing…' : 'Refresh screens'}
            </button>
          </div>
        }
      />

      <section className="panel stock-list-panel">
        {screensQuery.isLoading && <div className="loading">Loading screens…</div>}
        {screensQuery.error && <div className="empty">{(screensQuery.error as Error).message}</div>}

        {!screensQuery.isLoading && !screens.length && (
          <div className="empty">
            No screen plugins found. Add a `.py` file under `screens/stock/user/` (see `screens/README.md`) and refresh.
          </div>
        )}

        {!!screens.length && (
          <div className="fund-toolbar fund-screener-toolbar">
            <label className="stock-field">
              <span>Screen</span>
              <select
                value={selected?.screen_id || ''}
                onChange={(event) => {
                  setSelectedId(event.target.value);
                  setResultRows([]);
                  setResultMeta(null);
                }}
              >
                {runnable.map((item) => (
                  <option key={item.screen_id} value={item.screen_id}>
                    {(item.meta?.name || item.screen_id) + ` (v${item.meta?.version || '?'})`}
                  </option>
                ))}
                {!runnable.length && <option value="">No runnable screens</option>}
              </select>
            </label>

            {(selected?.meta?.parameters || []).map((param) => (
              <label key={param.name} className="stock-field">
                <span>{param.name}</span>
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

            <div className="toolbar-actions">
              <button
                type="button"
                className="primary-button"
                disabled={!selected || run.isPending || !runnable.length}
                onClick={() => run.mutate()}
              >
                {run.isPending ? 'Running…' : 'Run'}
              </button>
            </div>
          </div>
        )}

        {selected?.meta?.description && <p className="subtitle">{selected.meta.description}</p>}
        {runError && <div className="empty">{runError}</div>}

        {!!screens.length && (
          <div className="table-wrap" style={{ marginTop: '1rem' }}>
            <table>
              <thead>
                <tr>
                  <th>Id</th>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Path</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {screens.map((item) => (
                  <tr key={`${item.screen_id}-${item.path}`}>
                    <td>{item.screen_id}</td>
                    <td>{item.meta?.name || '—'}</td>
                    <td>{item.status}</td>
                    <td>{item.path}</td>
                    <td>{(item.errors || []).join('; ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="panel stock-list-panel">
        <h2 style={{ marginTop: 0 }}>Results</h2>
        {!resultMeta && !run.isPending && (
          <div className="empty">Pick a screen and run it against the stored metrics snapshot.</div>
        )}
        {resultMeta && (
          <p className="subtitle">
            {resultMeta.name || selected?.meta?.name}: {resultMeta.total ?? resultRows.length} match
            {(resultMeta.total ?? resultRows.length) === 1 ? '' : 'es'}
          </p>
        )}
        {!!resultRows.length && (
          <div className="table-wrap">
            <table>
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
                      <td>
                        <Link to={`/stocks/${encodeURIComponent(symbol)}`}>{symbol}</Link>
                      </td>
                      <td>
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
        )}
        {resultMeta && !resultRows.length && !runError && (
          <div className="empty">No rows matched these parameters on the stored snapshot.</div>
        )}
      </section>
    </>
  );
}
