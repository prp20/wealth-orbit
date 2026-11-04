import React from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import SyncJobButton from '../../components/SyncJobButton';
import ChartToolbar, { ChartRange } from '../../components/ChartToolbar';
import FundNavChart from '../../components/FundNavChart';
import FundHeader from './panels/FundHeader';
import KeyMetricsPanel from './panels/KeyMetricsPanel';
import PerformancePanel from './panels/PerformancePanel';
import FundFactsPanel from './panels/FundFactsPanel';
import SimilarFundsPanel from './panels/SimilarFundsPanel';
import BenchmarkPanel from './panels/BenchmarkPanel';
import RiskPanel from './panels/RiskPanel';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'performance', label: 'Performance' },
  { id: 'risk', label: 'Risk' },
  { id: 'benchmark', label: 'Benchmark' },
] as const;

type TabId = (typeof TABS)[number]['id'];

function isTabId(value: string | null): value is TabId {
  return TABS.some((tab) => tab.id === value);
}

export default function FundDetailPage() {
  const { schemeId = '' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const tab: TabId = isTabId(tabParam) ? tabParam : 'overview';
  const [range, setRange] = React.useState<ChartRange>('1Y');
  const [overlay, setOverlay] = React.useState(false);
  const fund = useQuery({ queryKey: ['fund', schemeId], queryFn: () => api.fund(schemeId) });

  const setTab = (next: TabId) => {
    const params = new URLSearchParams(searchParams);
    if (next === 'overview') params.delete('tab');
    else params.set('tab', next);
    setSearchParams(params, { replace: true });
  };

  if (fund.isLoading) {
    return (
      <>
        <Link className="back" to="/mutualfunds">
          ← Back to mutual funds
        </Link>
        <div className="loading">Loading fund…</div>
      </>
    );
  }

  if (fund.error) {
    return (
      <>
        <Link className="back" to="/mutualfunds">
          ← Back to mutual funds
        </Link>
        <div className="empty">{(fund.error as Error).message}</div>
      </>
    );
  }

  const detail = fund.data || {};
  const benchmarkAvailable = Boolean(detail.benchmark?.available && detail.benchmark?.index_code);
  const compareHref = `/mutualfunds/compare?scheme_codes=${encodeURIComponent(schemeId)}&metric_period=1Y`;

  return (
    <div className="fund-detail stock-detail">
      <div className="page-header-actions-row" style={{ marginBottom: 12 }}>
        <Link className="back" to="/mutualfunds">
          ← Back to mutual funds
        </Link>
        <Link className="text-link" to="/mutualfunds/screen">
          Screener
        </Link>
        <Link className="text-link" to={compareHref}>
          Compare
        </Link>
      </div>
      <p className="eyebrow detail-eyebrow">Fund research</p>

      <FundHeader fund={detail} />

      <nav className="fund-tabs" aria-label="Fund detail sections">
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
          <KeyMetricsPanel schemeId={schemeId} fund={detail} />
          <FundFactsPanel schemeId={schemeId} fund={detail} />
        </>
      )}

      {tab === 'performance' && (
        <>
          <section className="panel">
            <div className="panel-heading chart-panel-heading">
              <div>
                <h2>NAV chart</h2>
                <p className="panel-subtitle">Scheme NAV with selectable ranges.</p>
              </div>
              <div className="chart-panel-controls">
                <ChartToolbar range={range} onChange={setRange} />
                <SyncJobButton
                  entity="fund"
                  id={schemeId}
                  kind="nav"
                  invalidateKeys={[['history', 'fund', schemeId], ['fund', schemeId]]}
                />
              </div>
            </div>
            <FundNavChart
              schemeId={schemeId}
              range={range}
              overlay={false}
              benchmarkAvailable={benchmarkAvailable}
            />
          </section>
          <PerformancePanel schemeId={schemeId} />
        </>
      )}

      {tab === 'risk' && <RiskPanel schemeId={schemeId} fund={detail} />}

      {tab === 'benchmark' && (
        <>
          <section className="panel">
            <div className="panel-heading chart-panel-heading">
              <div>
                <h2>NAV vs benchmark</h2>
                <p className="panel-subtitle">
                  Optional overlay normalizes fund and benchmark to 100 for relative comparison.
                </p>
              </div>
              <div className="chart-panel-controls">
                <ChartToolbar range={range} onChange={setRange} />
                <label className="overlay-toggle">
                  <input
                    type="checkbox"
                    checked={overlay && benchmarkAvailable}
                    disabled={!benchmarkAvailable}
                    onChange={(event) => setOverlay(event.target.checked)}
                  />
                  vs benchmark
                </label>
                <SyncJobButton
                  entity="fund"
                  id={schemeId}
                  kind="nav"
                  invalidateKeys={[['history', 'fund', schemeId], ['fund', schemeId]]}
                />
              </div>
            </div>
            <FundNavChart
              schemeId={schemeId}
              range={range}
              overlay={overlay}
              benchmarkAvailable={benchmarkAvailable}
            />
          </section>
          <BenchmarkPanel schemeId={schemeId} fund={detail} />
          <SimilarFundsPanel schemeId={schemeId} />
        </>
      )}
    </div>
  );
}
