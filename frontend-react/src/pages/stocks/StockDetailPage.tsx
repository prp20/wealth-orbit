import React from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import AddInstrumentDialog from '../../components/AddInstrumentDialog';
import InfoTip from '../../components/InfoTip';
import MarketChart from '../../components/MarketChart';
import SyncJobButton from '../../components/SyncJobButton';
import ChartToolbar, { ChartRange } from '../../components/ChartToolbar';
import {
  formatCompactInr,
  formatDate,
  formatPct,
  formatPercentPoints,
  formatRatio,
} from '../../lib/format';
import StockHeader from './panels/StockHeader';
import StockDataFooter from './panels/StockDataFooter';
import FundamentalsPanel from './panels/FundamentalsPanel';
import PeersPanel from './panels/PeersPanel';
import ShareholdingPanel from './panels/ShareholdingPanel';
import TechnicalsPanel from './panels/TechnicalsPanel';
import { recordRecent } from '../../lib/recent';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'fundamentals', label: 'Fundamentals' },
  { id: 'technicals', label: 'Technicals' },
] as const;

type TabId = (typeof TABS)[number]['id'];

function isTabId(value: string | null): value is TabId {
  return TABS.some((tab) => tab.id === value);
}

type MetricCard = {
  key: string;
  label: string;
  value: unknown;
  format: (value: unknown) => string;
};

export default function StockDetailPage() {
  const { symbol = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const tab: TabId =
    tabParam === 'statements' || tabParam === 'valuation'
      ? tabParam === 'statements'
        ? 'fundamentals'
        : 'overview'
      : isTabId(tabParam)
        ? tabParam
        : 'overview';
  const [range, setRange] = React.useState<ChartRange>('1Y');
  const [mode, setMode] = React.useState('line');
  const [addOpen, setAddOpen] = React.useState(false);
  const stock = useQuery({ queryKey: ['stock', symbol], queryFn: () => api.stock(symbol) });
  const valuation = useQuery({
    queryKey: ['stock-valuation', symbol],
    queryFn: () => api.stockValuation(symbol),
    enabled: Boolean(symbol) && tab === 'overview',
  });
  const metrics = stock.data?.latest_daily_metrics || {};
  const valuationMetrics = valuation.data?.metrics || {};

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

  React.useEffect(() => {
    if (tabParam !== 'valuation') return;
    const params = new URLSearchParams(searchParams);
    params.delete('tab');
    setSearchParams(params, { replace: true });
  }, [tabParam, searchParams, setSearchParams]);

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
    const message = (stock.error as Error).message || 'Stock not found';
    const missing = /not found/i.test(message);
    return (
      <>
        <Link className="back" to="/stocks">
          ← Back to stocks
        </Link>
        <div className="empty empty-cta">
          <strong>{missing ? 'Not in catalog' : message}</strong>
          {missing && (
            <>
              <span>{symbol} is not tracked yet. Add it as an NSE symbol to sync history.</span>
              <button type="button" className="primary-button" onClick={() => setAddOpen(true)}>
                Add “{symbol}”
              </button>
            </>
          )}
          {!missing && <span>{message}</span>}
        </div>
        <AddInstrumentDialog
          open={addOpen}
          onClose={() => setAddOpen(false)}
          initialKind="stock"
          initialCode={symbol}
          allowedKinds={['stock']}
        />
      </>
    );
  }

  const detail = stock.data || {};
  const pick = (...values: unknown[]) => values.find((value) => value != null && value !== '');
  const ratioCards: MetricCard[] = [
    { key: 'market_cap', label: 'Market cap', value: pick(valuationMetrics.market_cap, metrics.market_cap), format: formatCompactInr },
    {
      key: 'enterprise_value',
      label: 'Enterprise value',
      value: valuationMetrics.enterprise_value,
      format: formatCompactInr,
    },
    { key: 'stock_pe', label: 'P/E (trailing)', value: pick(valuationMetrics.stock_pe, metrics.stock_pe), format: formatRatio },
    { key: 'price_to_book', label: 'P/B', value: pick(valuationMetrics.price_to_book, metrics.price_to_book), format: formatRatio },
    { key: 'ev_ebitda', label: 'EV / EBITDA', value: pick(valuationMetrics.ev_ebitda, metrics.ev_ebitda), format: formatRatio },
    { key: 'ev_sales', label: 'EV / Sales', value: valuationMetrics.ev_sales, format: formatRatio },
    { key: 'roe', label: 'Return on equity', value: metrics.roe, format: formatPct },
    { key: 'roce', label: 'Return on capital', value: metrics.roce, format: formatPct },
    {
      key: 'dividend_yield',
      label: 'Dividend yield',
      value: pick(valuationMetrics.dividend_yield, metrics.dividend_yield),
      format: formatPercentPoints,
    },
    { key: 'fcf_yield', label: 'FCF yield', value: valuationMetrics.fcf_yield, format: formatPercentPoints },
    { key: 'ebitda_ttm', label: 'EBITDA (TTM)', value: valuationMetrics.ebitda_ttm, format: formatCompactInr },
    { key: 'net_debt', label: 'Net debt', value: valuationMetrics.net_debt, format: formatCompactInr },
  ];
  const valuationNotes = [
    ...(valuation.data?.notes || []),
    'PEG is omitted until it is trailing earnings growth from stored results.',
  ];

  return (
    <div className="stock-detail">
      <div className="detail-topbar">
        <Link className="back" to="/stocks">
          ← Back to stocks
        </Link>
        <p className="eyebrow detail-eyebrow">Stock research</p>
      </div>

      <StockHeader stock={detail} />

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
              <div className="fundamentals-heading">
                <div className="fundamentals-title-row">
                  <h2>Key ratios</h2>
                  <InfoTip label="About key ratios">
                    <p>Latest daily snapshot of trailing valuation multiples and profitability ratios.</p>
                    {valuation.data && (
                      <p>
                        As of {formatDate(valuation.data.as_of) || '—'} · Source {valuation.data.source || '—'}
                        {valuation.data.forward_estimates_available ? '' : ' · Forward PE unavailable'}
                      </p>
                    )}
                    {valuationNotes.map((note) => (
                      <p key={note}>{note}</p>
                    ))}
                  </InfoTip>
                </div>
                <p className="panel-subtitle">Valuation and profitability</p>
              </div>
              <SyncJobButton
                symbol={symbol}
                kind="daily_metrics"
                thenKind="fundamentals"
                label="Update ratios"
                invalidateKeys={[
                  ['stock-daily-metrics', symbol],
                  ['stock', symbol],
                  ['stock-peers', symbol],
                  ['stock-valuation', symbol],
                  ['stock-fundamentals', symbol],
                  ['stock-fundamentals-summary', symbol],
                  ['stock-shareholding', symbol],
                ]}
              />
            </div>
            {(valuation.isLoading || stock.isLoading) && <div className="loading">Loading ratios…</div>}
            {valuation.error && <div className="empty">{(valuation.error as Error).message}</div>}
            {!valuation.isLoading && !valuation.error && (
              <section className="metrics compact-metrics snapshot-metrics">
                {ratioCards.map((card) => (
                  <div className="metric" key={card.key}>
                    <small>{card.label}</small>
                    <strong>{card.format(card.value)}</strong>
                  </div>
                ))}
              </section>
            )}
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
                  label="Update prices"
                  extendHistory
                  invalidateKeys={[['history', 'stock', symbol], ['stock', symbol], ['stock-valuation', symbol]]}
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

      {tab === 'fundamentals' && <FundamentalsPanel symbol={symbol} />}
      {tab === 'technicals' && <TechnicalsPanel symbol={symbol} />}

      <StockDataFooter stock={detail} />
    </div>
  );
}
