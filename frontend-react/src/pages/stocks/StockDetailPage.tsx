import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import MarketChart from '../../components/MarketChart';
import SyncJobButton from '../../components/SyncJobButton';
import StockHeader from './panels/StockHeader';
import InsightsPanel from './panels/InsightsPanel';
import FundamentalsPanel from './panels/FundamentalsPanel';
import PeersPanel from './panels/PeersPanel';
import ShareholdingPanel from './panels/ShareholdingPanel';
import TechnicalsPanel from './panels/TechnicalsPanel';

const money = (value: unknown) =>
  value == null || value === ''
    ? '—'
    : new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(Number(value));

function Page({ title, subtitle, children }: { title: string; subtitle: string; children?: React.ReactNode }) {
  return (
    <>
      <header>
        <p className="eyebrow">Wealth Orbit</p>
        <h1>{title}</h1>
        <p className="subtitle">{subtitle}</p>
      </header>
      {children}
    </>
  );
}

export default function StockDetailPage() {
  const { symbol = '' } = useParams();
  const stock = useQuery({ queryKey: ['stock', symbol], queryFn: () => api.stock(symbol) });
  const metrics = stock.data?.latest_daily_metrics;

  if (stock.isLoading) {
    return (
      <Page title={symbol} subtitle="Loading stock decision surface…">
        <div className="loading">Loading stock…</div>
      </Page>
    );
  }

  if (stock.error) {
    return (
      <Page title={symbol} subtitle="Stock detail">
        <Link className="back" to="/stocks">
          ← Back to stocks
        </Link>
        <div className="empty">{(stock.error as Error).message}</div>
      </Page>
    );
  }

  const detail = stock.data || {};

  return (
    <Page title={detail.company_name || symbol} subtitle="Scannable market context for decision-making.">
      <Link className="back" to="/stocks">
        ← Back to stocks
      </Link>
      <StockHeader stock={detail} />
      <InsightsPanel items={[]} />
      <section className="metrics compact-metrics snapshot-metrics">
        <div className="metric">
          <small>PE</small>
          <strong>{money(metrics?.stock_pe)}</strong>
        </div>
        <div className="metric">
          <small>PB</small>
          <strong>{money(metrics?.price_to_book)}</strong>
        </div>
        <div className="metric">
          <small>ROE</small>
          <strong>{money(metrics?.roe)}</strong>
        </div>
        <div className="metric">
          <small>ROCE</small>
          <strong>{money(metrics?.roce)}</strong>
        </div>
        <div className="metric">
          <small>Div yield</small>
          <strong>{money(metrics?.dividend_yield)}</strong>
        </div>
        <div className="metric">
          <small>Market cap</small>
          <strong>{money(metrics?.market_cap)}</strong>
        </div>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Price chart</h2>
            <p className="panel-subtitle">Choose a range to inspect recent price action.</p>
          </div>
          <SyncJobButton
            symbol={symbol}
            kind="prices"
            invalidateKeys={[['history', 'stock', symbol], ['stock', symbol]]}
          />
        </div>
        <MarketChart kind="stock" id={symbol} />
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Daily metrics sync</h2>
            <p className="panel-subtitle">Refresh PE/PB/ROE snapshot used in the header cards.</p>
          </div>
          <SyncJobButton
            symbol={symbol}
            kind="daily_metrics"
            invalidateKeys={[['stock-daily-metrics', symbol], ['stock', symbol], ['stock-peers', symbol]]}
          />
        </div>
      </section>
      <FundamentalsPanel symbol={symbol} />
      <PeersPanel symbol={symbol} />
      <ShareholdingPanel symbol={symbol} />
      <TechnicalsPanel symbol={symbol} />
    </Page>
  );
}
