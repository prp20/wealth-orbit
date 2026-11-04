import React from 'react';
import { Link, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api';
import SyncJobButton from '../../components/SyncJobButton';
import ChartToolbar, { ChartRange } from '../../components/ChartToolbar';
import FundNavChart from '../../components/FundNavChart';
import InsightsPanel from '../stocks/panels/InsightsPanel';
import FundHeader from './panels/FundHeader';
import KeyMetricsPanel from './panels/KeyMetricsPanel';
import PerformancePanel from './panels/PerformancePanel';
import FundFactsPanel from './panels/FundFactsPanel';
import SimilarFundsPanel from './panels/SimilarFundsPanel';
import BenchmarkPanel from './panels/BenchmarkPanel';

export default function FundDetailPage() {
  const { schemeId = '' } = useParams();
  const [range, setRange] = React.useState<ChartRange>('1Y');
  const [overlay, setOverlay] = React.useState(false);
  const fund = useQuery({ queryKey: ['fund', schemeId], queryFn: () => api.fund(schemeId) });

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

  return (
    <div className="fund-detail stock-detail">
      <Link className="back" to="/mutualfunds">
        ← Back to mutual funds
      </Link>
      <p className="eyebrow detail-eyebrow">Fund research</p>

      <FundHeader fund={detail} />
      <InsightsPanel items={[]} />
      <KeyMetricsPanel schemeId={schemeId} fund={detail} />

      <section className="panel">
        <div className="panel-heading chart-panel-heading">
          <div>
            <h2>NAV chart</h2>
            <p className="panel-subtitle">
              Scheme NAV with selectable ranges. Optional overlay normalizes fund and benchmark to 100.
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

      <PerformancePanel schemeId={schemeId} />
      <FundFactsPanel schemeId={schemeId} fund={detail} />
      <SimilarFundsPanel schemeId={schemeId} />
      <BenchmarkPanel schemeId={schemeId} fund={detail} />
    </div>
  );
}
