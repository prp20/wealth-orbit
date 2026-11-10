import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api';
import AddInstrumentDialog from '../components/AddInstrumentDialog';
import PageHeader from '../components/PageHeader';
import RecentSyncJobs from '../components/RecentSyncJobs';
import SyncJobButton from '../components/SyncJobButton';
import { formatDisplayDate, formatInr, formatRatio } from '../lib/format';
import { formatRecentWhen, readRecent } from '../lib/recent';

const HOME_INDEXES = ['NIFTY50', 'SENSEX', 'NIFTYBANK', 'NIFTYIT'];
const SECTOR_INDEXES = ['NIFTYPHARMA', 'NIFTYAUTO', 'NIFTYFMCG', 'NIFTYMETAL'];
const EXTRA_INDEXES_KEY = 'wealth-orbit:extra-home-indexes';

function readExtraIndexes(): string[] {
  try {
    const raw = window.localStorage.getItem(EXTRA_INDEXES_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed.map((item) => String(item || '').toUpperCase()).filter(Boolean)
      : [];
  } catch {
    return [];
  }
}

function rememberExtraIndex(code: string) {
  const next = Array.from(new Set([...readExtraIndexes(), code.toUpperCase()]));
  window.localStorage.setItem(EXTRA_INDEXES_KEY, JSON.stringify(next));
  return next;
}

const INDEX_LABELS: Record<string, string> = {
  NIFTY50: 'Nifty 50',
  SENSEX: 'Sensex',
  NIFTYBANK: 'Nifty Bank',
  NIFTYIT: 'Nifty IT',
  NIFTYPHARMA: 'Nifty Pharma',
  NIFTYAUTO: 'Nifty Auto',
  NIFTYFMCG: 'Nifty FMCG',
  NIFTYMETAL: 'Nifty Metal',
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

function newestDate(rows: any[]) {
  const dates = rows.map((row) => String(row.as_of || '')).filter(Boolean).sort();
  return dates[dates.length - 1];
}

function IndexStrip({ rows }: { rows: any[] }) {
  const newest = formatDisplayDate(newestDate(rows));
  return (
    <div className="index-strip">
      {rows.map((row) => {
        const asOf = formatDisplayDate(row.as_of);
        const change = Number(row.change_pct);
        const down = row.change_pct != null && !Number.isNaN(change) && change < 0;
        return (
          <article className="index-tile" key={row.index_code}>
            <small>{indexLabel(row)}</small>
            <strong>{formatRatio(row.close)}</strong>
            <span className={down ? 'change-down' : undefined}>
              {formatChange(row.change_pct)} vs previous close
            </span>
            {asOf !== newest && <em>As of {asOf}</em>}
          </article>
        );
      })}
    </div>
  );
}

export default function DashboardPage() {
  const [recent, setRecent] = React.useState(() => readRecent());
  const [extraIndexes, setExtraIndexes] = React.useState(() => readExtraIndexes());
  const [addIndexOpen, setAddIndexOpen] = React.useState(false);
  const homeCodes = React.useMemo(
    () => Array.from(new Set([...HOME_INDEXES, ...extraIndexes])),
    [extraIndexes],
  );
  const syncCodes = React.useMemo(
    () => Array.from(new Set([...homeCodes, ...SECTOR_INDEXES])),
    [homeCodes],
  );
  const account = useQuery({ queryKey: ['auth-me'], queryFn: api.authMe, retry: false });
  const signedIn = account.data?.signed_in === true;
  const market = useQuery({
    queryKey: ['benchmark-summary', homeCodes.join(',')],
    queryFn: () => api.benchmarkSummary(homeCodes),
  });
  const sectors = useQuery({
    queryKey: ['benchmark-summary', SECTOR_INDEXES.join(',')],
    queryFn: () => api.benchmarkSummary(SECTOR_INDEXES),
  });
  const portfolios = useQuery({ queryKey: ['portfolios'], queryFn: api.portfolios, enabled: signedIn });
  const portfolioRows = portfolios.data || [];
  const portfolioId = portfolioRows[0]?.portfolio_id;
  const holdings = useQuery({
    queryKey: ['holdings', portfolioId],
    queryFn: () => api.holdings(portfolioId),
    enabled: Boolean(portfolioId),
  });

  React.useEffect(() => {
    const refresh = () => {
      if (document.visibilityState === 'visible') setRecent(readRecent());
    };
    const onFocus = () => setRecent(readRecent());
    document.addEventListener('visibilitychange', refresh);
    window.addEventListener('focus', onFocus);
    return () => {
      document.removeEventListener('visibilitychange', refresh);
      window.removeEventListener('focus', onFocus);
    };
  }, []);

  const rows = market.data || [];
  const sectorRows = sectors.data || [];
  const newest = newestDate(rows);
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
              {rows.length ? `Delayed · as of ${formatDisplayDate(newest)} · index history` : 'Delayed · index history'}
            </p>
          </div>
          <div className="panel-sync">
            <button type="button" className="secondary" onClick={() => setAddIndexOpen(true)}>
              Add index
            </button>
            <SyncJobButton
              kind="PRICES"
              label="Update indexes"
              hideSucceeded
              extendHistory
              startJob={() => api.syncBenchmarks(syncCodes)}
              startExtendJob={(period) => api.syncBenchmarks(syncCodes, period)}
              loadStatus={() => api.syncBenchmarkStatus()}
              invalidateKeys={[['benchmark-summary']]}
            />
          </div>
        </div>
        <AddInstrumentDialog
          open={addIndexOpen}
          onClose={() => setAddIndexOpen(false)}
          initialKind="index"
          allowedKinds={['index']}
          onTracked={(result) => {
            const code = String(result.master.index_code || '').toUpperCase();
            if (code) setExtraIndexes(rememberExtraIndex(code));
          }}
        />
        {market.isLoading && <div className="home-note">Loading market…</div>}
        {market.error && <div className="home-note">Market data could not be loaded.</div>}
        {!market.isLoading && !market.error && !rows.length && <div className="home-note">No index history yet.</div>}
        {rows.length > 0 && <IndexStrip rows={rows} />}
      </section>

      {sectorRows.length > 0 && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Sectors</h2>
              <p className="panel-subtitle">
                Delayed · as of {formatDisplayDate(newestDate(sectorRows))} · index history
              </p>
            </div>
          </div>
          <IndexStrip rows={sectorRows} />
        </section>
      )}

      <div className="home-split">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Portfolio</h2>
              {portfolioRows.length > 1 && portfolioRows[0]?.user_name && (
                <p className="panel-subtitle">{portfolioRows[0].user_name}</p>
              )}
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
              </div>
              <p className="panel-subtitle home-cost-note">Invested is cost. Positions are not marked to market.</p>
              {sleeveRows.length > 0 && (
                <>
                  <p className="panel-subtitle sleeve-caption">By invested cost</p>
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
                </>
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
                    <em>{formatRecentWhen(item.viewedAt)}</em>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <RecentSyncJobs />
    </div>
  );
}
