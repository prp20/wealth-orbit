import React from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import MarketChart from '../../components/MarketChart';
import SyncJobButton from '../../components/SyncJobButton';
import ChartToolbar, { ChartRange } from '../../components/ChartToolbar';
import { formatCompactInr, formatPct, formatRatio } from '../../lib/format';
import StockHeader from './panels/StockHeader';
import InsightsPanel from './panels/InsightsPanel';
import FundamentalsPanel from './panels/FundamentalsPanel';
import StatementsPanel from './panels/StatementsPanel';
import ValuationPanel from './panels/ValuationPanel';
import PeersPanel from './panels/PeersPanel';
import ShareholdingPanel from './panels/ShareholdingPanel';
import TechnicalsPanel from './panels/TechnicalsPanel';
import { recordRecent } from '../../lib/recent';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'statements', label: 'Statements' },
  { id: 'fundamentals', label: 'Fundamentals' },
  { id: 'valuation', label: 'Valuation' },
  { id: 'technicals', label: 'Technicals' },
] as const;

type TabId = (typeof TABS)[number]['id'];

function isTabId(value: string | null): value is TabId {
  return TABS.some((tab) => tab.id === value);
}

export default function StockDetailPage() {
  const { symbol = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const tab: TabId = isTabId(tabParam) ? tabParam : 'overview';
  const [range, setRange] = React.useState<ChartRange>('1Y');
  const [mode, setMode] = React.useState('line');
  const stock = useQuery({ queryKey: ['stock', symbol], queryFn: () => api.stock(symbol) });
  const metrics = stock.data?.latest_daily_metrics;

  const setTab = (next: TabId) => {
    const params = new URLSearchParams(searchParams);
    if (next === 'overview') params.delete('tab');
    else params.set('tab', next);
    setSearchParams(params, { replace: true });
  };

  React.useEffect(() => {
    if (!stock.data) return;
    recordRecent({
      kind: 'stock',
      id: symbol,
      label: stock.data.company_name || symbol,
      path: `/stocks/${encodeURIComponent(symbol)}`,
    });
  }, [stock.data, symbol]);

  if (stock.isLoading) {
    return (
      <>
        <Link className="back" to="/stocks">
          ← Back to stocks
        </Link>
        <div className="loading">Loading stock…</div>
      </>
    );
  }

  if (stock.error) {
    return (
      <>
        <Link className="back" to="/stocks">
          ← Back to stocks
        </Link>
        <div className="empty">{(stock.error as Error).message}</div>
      </>
    );
  }

  const detail = stock.data || {};

  return (
    <div className="stock-detail">
      <Link className="back" to="/stocks">
        ← Back to stocks
      </Link>
      <p className="eyebrow detail-eyebrow">Stock research</p>

      <StockHeader stock={detail} />
      <InsightsPanel items={[]} />

      <nav className="fund-tabs" aria-label="Stock detail sections">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={tab === item.id ? 'active' : undefined}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {tab === 'overview' && (
        <>
          <section className="panel key-ratios-panel">
            <div className="panel-heading">
              <div>
                <h2>Key ratios</h2>
                <p className="panel-subtitle">Latest daily snapshot for quick comparison.</p>
              </div>
              <SyncJobButton
                symbol={symbol}
                kind="daily_metrics"
                invalidateKeys={[
                  ['stock-daily-metrics', symbol],
                  ['stock', symbol],
                  ['stock-peers', symbol],
                  ['stock-valuation', symbol],
                ]}
              />
            </div>
            <section className="metrics compact-metrics snapshot-metrics">
              <div className="metric">
                <small>PE</small>
                <strong>{formatRatio(metrics?.stock_pe)}</strong>
              </div>
              <div className="metric">
                <small>PB</small>
                <strong>{formatRatio(metrics?.price_to_book)}</strong>
              </div>
              <div className="metric">
                <small>EV/EBITDA</small>
                <strong>{formatRatio(metrics?.ev_ebitda)}</strong>
              </div>
              <div className="metric">
                <small>ROE</small>
                <strong>{formatPct(metrics?.roe)}</strong>
              </div>
              <div className="metric">
                <small>ROCE</small>
                <strong>{formatPct(metrics?.roce)}</strong>
              </div>
              <div className="metric">
                <small>Div yield</small>
                <strong>{formatPct(metrics?.dividend_yield)}</strong>
              </div>
              <div className="metric">
                <small>Market cap</small>
                <strong>{formatCompactInr(metrics?.market_cap)}</strong>
              </div>
            </section>
          </section>

          <section className="panel">
            <div className="panel-heading chart-panel-heading">
              <div>
                <h2>Price chart</h2>
                <p className="panel-subtitle">Recent price action with selectable ranges.</p>
              </div>
              <div className="chart-panel-controls">
                <ChartToolbar range={range} onChange={setRange} />
                <select value={mode} onChange={(event) => setMode(event.target.value)}>
                  <option value="line">Line + volume</option>
                  <option value="candles">Candlesticks + volume</option>
                </select>
                <SyncJobButton
                  symbol={symbol}
                  kind="prices"
                  invalidateKeys={[['history', 'stock', symbol], ['stock', symbol]]}
                />
              </div>
            </div>
            <MarketChart
              kind="stock"
              id={symbol}
              bare
              range={range}
              onRangeChange={setRange}
              mode={mode}
              onModeChange={setMode}
            />
          </section>

          <PeersPanel symbol={symbol} />
          <ShareholdingPanel symbol={symbol} />
        </>
      )}

      {tab === 'statements' && <StatementsPanel symbol={symbol} />}
      {tab === 'fundamentals' && <FundamentalsPanel symbol={symbol} />}
      {tab === 'valuation' && <ValuationPanel symbol={symbol} />}
      {tab === 'technicals' && (
        <>
          <section className="panel">
            <div className="panel-heading chart-panel-heading">
              <div>
                <h2>Price chart</h2>
                <p className="panel-subtitle">OHLCV with line or candlestick view.</p>
              </div>
              <div className="chart-panel-controls">
                <ChartToolbar range={range} onChange={setRange} />
                <select value={mode} onChange={(event) => setMode(event.target.value)}>
                  <option value="line">Line + volume</option>
                  <option value="candles">Candlesticks + volume</option>
                </select>
                <SyncJobButton
                  symbol={symbol}
                  kind="prices"
                  invalidateKeys={[['history', 'stock', symbol], ['stock', symbol]]}
                />
              </div>
            </div>
            <MarketChart
              kind="stock"
              id={symbol}
              bare
              range={range}
              onRangeChange={setRange}
              mode={mode}
              onModeChange={setMode}
            />
          </section>
          <TechnicalsPanel symbol={symbol} />
        </>
      )}
    </div>
  );
}
