import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, SyncJob, syncJobFailureMessage } from '../api';
import PageHeader from '../components/PageHeader';
import { formatDate, formatInr, formatRatio } from '../lib/format';
import { readRecent } from '../lib/recent';

const HOME_INDEXES = ['NIFTY50', 'SENSEX', 'NIFTYBANK', 'NIFTYIT'];

const INDEX_LABELS: Record<string, string> = {
  NIFTY50: 'Nifty 50',
  SENSEX: 'Sensex',
  NIFTYBANK: 'Nifty Bank',
  NIFTYIT: 'Nifty IT',
};

const SLEEVE_LABELS: Record<string, string> = {
  MUTUAL_FUND: 'Mutual funds',
  STOCK: 'Stocks',
};

function formatChange(value: unknown) {
  if (value == null || value === '') return '—';
  const amount = Number(value);
  if (Number.isNaN(amount)) return '—';
  const text = formatRatio(Math.abs(amount));
  if (amount > 0) return `+${text}%`;
  if (amount < 0) return `-${text}%`;
  return `${text}%`;
}

function sleeveLabel(assetType: string) {
  return SLEEVE_LABELS[assetType] || assetType.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase());
}

function indexLabel(row: { index_code?: string; index_name?: string }) {
  const code = String(row.index_code || '').toUpperCase();
  return INDEX_LABELS[code] || row.index_name || row.index_code || 'Index';
}

function MarketSyncButton() {
  const queryClient = useQueryClient();
  const [busy, setBusy] = React.useState(false);
  const [status, setStatus] = React.useState('idle');
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    let cancelled = false;
    api.syncBenchmarkStatus()
      .then((payload) => {
        if (cancelled) return;
        const failure = syncJobFailureMessage(payload.job);
        setStatus(failure ? 'failed' : payload.status || 'idle');
        setError(failure || '');
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const run = async () => {
    setBusy(true);
    setError('');
    setStatus('queued');
    try {
      const job = await api.syncBenchmarks(HOME_INDEXES);
      const terminal = await pollJob(job.job_id, (current) => {
        const failure = syncJobFailureMessage(current);
        setStatus(failure ? 'failed' : String(current.status || '').toLowerCase());
        if (failure) setError(failure);
      });
      const failure = syncJobFailureMessage(terminal);
      if (failure) {
        setStatus('failed');
        setError(failure);
      } else {
        setStatus('succeeded');
        setError('');
        await queryClient.invalidateQueries({ queryKey: ['benchmark-summary'] });
      }
    } catch (err: any) {
      setStatus('failed');
      setError(err.message || 'Sync failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel-sync">
      <button type="button" disabled={busy} onClick={run}>
        {busy ? 'Syncing…' : 'Sync today'}
      </button>
      {status !== 'idle' && <span className={`sync-chip status-${status}`}>{status}</span>}
      {error && <small className="sync-error">{error}</small>}
    </div>
  );
}

async function pollJob(jobId: string, onUpdate: (job: SyncJob) => void): Promise<SyncJob> {
  for (let attempt = 0; attempt < 90; attempt += 1) {
    const job = await api.syncJob(jobId);
    onUpdate(job);
    if (['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(String(job.status || '').toUpperCase())) return job;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error('Sync is still running. Refresh in a moment.');
}

export default function DashboardPage() {
  const recent = React.useMemo(() => readRecent(), []);
  const account = useQuery({ queryKey: ['auth-me'], queryFn: api.authMe, retry: false });
  const signedIn = account.data?.signed_in === true;
  const market = useQuery({
    queryKey: ['benchmark-summary', HOME_INDEXES.join(',')],
    queryFn: () => api.benchmarkSummary(HOME_INDEXES),
  });
  const portfolios = useQuery({ queryKey: ['portfolios'], queryFn: api.portfolios, enabled: signedIn });
  const portfolioId = portfolios.data?.[0]?.portfolio_id;
  const holdings = useQuery({
    queryKey: ['holdings', portfolioId],
    queryFn: () => api.holdings(portfolioId),
    enabled: Boolean(portfolioId),
  });

  const rows = market.data || [];
  const dates = rows.map((row: any) => String(row.as_of || '')).filter(Boolean).sort();
  const newest = dates[dates.length - 1];
  const holdingRows = holdings.data || [];
  const invested = holdingRows.reduce((sum: number, row: any) => sum + Number(row.invested_amount || 0), 0);
  const sleeves = new Map<string, number>();
  for (const row of holdingRows) {
    const key = String(row.asset_type || 'OTHER');
    sleeves.set(key, (sleeves.get(key) || 0) + Number(row.invested_amount || 0));
  }
  const sleeveRows = Array.from(sleeves.entries()).filter(([, amount]) => amount !== 0);

  return (
    <div className="home">
      <PageHeader title="Home" subtitle="Market context, invested capital, and recent research." />

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Market</h2>
            <p className="panel-subtitle">
              {rows.length ? `Delayed · as of ${formatDate(newest)} · index history` : 'Delayed · index history'}
            </p>
          </div>
          <MarketSyncButton />
        </div>
        {market.isLoading && <div className="home-note">Loading market…</div>}
        {market.error && <div className="home-note">Market data could not be loaded.</div>}
        {!market.isLoading && !market.error && !rows.length && <div className="home-note">No index history yet.</div>}
        {rows.length > 0 && (
          <div className="index-strip">
            {rows.map((row: any) => {
              const asOf = formatDate(row.as_of);
              return (
                <article className="index-tile" key={row.index_code}>
                  <small>{indexLabel(row)}</small>
                  <strong>{formatRatio(row.close)}</strong>
                  <span>{formatChange(row.change_pct)}</span>
                  {asOf !== formatDate(newest) && <em>As of {asOf}</em>}
                </article>
              );
            })}
          </div>
        )}
      </section>

      <div className="home-split">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Portfolio</h2>
            </div>
            {signedIn && (
              <Link className="text-link" to="/portfolio">
                {holdingRows.length ? 'View holdings' : 'Open portfolio'}
              </Link>
            )}
          </div>
          {!account.isLoading && !signedIn && (
            <div className="home-note">
              <p>Sign in to see invested capital.</p>
              <div className="home-note-links">
                <Link className="text-link" to="/login">Sign in</Link>
              </div>
            </div>
          )}
          {signedIn && (portfolios.isLoading || (portfolioId && holdings.isLoading)) && <div className="home-note">Loading portfolio…</div>}
          {signedIn && (portfolios.error || holdings.error) && <div className="home-note">Portfolio could not be loaded.</div>}
          {signedIn && !portfolios.isLoading && !portfolios.error && !holdings.error && !holdingRows.length && !holdings.isLoading && (
            <div className="home-note">No holdings yet. Research can continue without a portfolio.</div>
          )}
          {holdingRows.length > 0 && (
            <>
              <div className="home-stats">
                <div>
                  <small>Invested</small>
                  <strong>{formatInr(invested)}</strong>
                </div>
                <div>
                  <small>Holdings</small>
                  <strong>{holdingRows.length}</strong>
                </div>
                <div className="home-stat-quiet">
                  <small>Market gains</small>
                  <strong>Not available</strong>
                </div>
              </div>
              <p className="panel-subtitle home-cost-note">Invested is cost. Positions are not marked to market.</p>
              {sleeveRows.length > 0 && (
                <ul className="sleeve-list">
                  {sleeveRows.map(([type, amount]) => {
                    const share = invested ? (amount / invested) * 100 : null;
                    return (
                      <li key={type}>
                        <div className="sleeve-row">
                          <span>{sleeveLabel(type)}</span>
                          <span className="sleeve-amount">
                            {formatInr(amount)}
                            <em>{share == null ? '—' : `${formatRatio(share, 1)}%`}</em>
                          </span>
                        </div>
                        <div className="sleeve-track" aria-hidden="true">
                          <i className={type === 'STOCK' ? 'sleeve-stock' : 'sleeve-fund'} style={{ width: `${share ?? 0}%` }} />
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </>
          )}
        </section>

        <section className="panel">
          <h2>Continue research</h2>
          {!recent.length && (
            <div className="home-note">
              <p>Open a fund or stock and it will show up here.</p>
              <div className="home-note-links">
                <Link className="text-link" to="/mutualfunds">Mutual funds</Link>
                <Link className="text-link" to="/stocks">Stocks</Link>
              </div>
            </div>
          )}
          {recent.length > 0 && (
            <ul className="recent-list">
              {recent.map((item) => (
                <li key={`${item.kind}-${item.id}`}>
                  <Link to={item.path}>
                    <small>{item.kind === 'fund' ? 'Fund' : 'Stock'}</small>
                    <span>{item.label || item.id}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="home-later">
        <h2>Watchlists and alerts</h2>
        <p>Watchlists and alerts are not available yet. They will show changes and notices here when those features exist.</p>
      </section>
    </div>
  );
}
