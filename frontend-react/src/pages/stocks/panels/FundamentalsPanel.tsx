import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import SyncJobButton from '../../../components/SyncJobButton';

const GROUP_LABELS: Record<string, string> = {
  profit_and_loss: 'Profit & loss',
  balance_sheet: 'Balance sheet',
  cash_flow: 'Cash flow',
  profitability: 'Profitability',
  growth: 'Growth',
  leverage: 'Leverage',
};

const METRIC_LABELS: Record<string, string> = {
  REVENUE: 'Revenue',
  SALES: 'Sales',
  OPERATING_PROFIT: 'Operating profit',
  OPERATING_MARGIN: 'Operating margin',
  EBITDA: 'EBITDA',
  NET_PROFIT: 'Net profit',
  EPS: 'EPS',
  EQUITY_CAPITAL: 'Equity capital',
  RESERVES: 'Reserves',
  BORROWINGS: 'Borrowings',
  TOTAL_DEBT: 'Total debt',
  NET_DEBT: 'Net debt',
  TOTAL_ASSETS: 'Total assets',
  CASH_FROM_OPERATING_ACTIVITIES: 'Cash from operations',
  OPERATING_CASH_FLOW: 'Operating cash flow',
  FREE_CASH_FLOW: 'Free cash flow',
  NET_CASH_FLOW: 'Net cash flow',
  ROE: 'ROE',
  ROCE: 'ROCE',
  PAT_MARGIN: 'PAT margin',
  REVENUE_GROWTH: 'Revenue growth',
  EPS_GROWTH: 'EPS growth',
  DEBT_TO_EQUITY: 'Debt / equity',
  INTEREST_COVERAGE: 'Interest coverage',
};

const CORE_GROUPS = ['profitability', 'growth', 'leverage', 'cash_flow'] as const;

export default function FundamentalsPanel({ symbol }: { symbol: string }) {
  const [period, setPeriod] = React.useState('ANNUAL');
  const [basis, setBasis] = React.useState('CONSOLIDATED');
  const [showRaw, setShowRaw] = React.useState(false);
  const summary = useQuery({
    queryKey: ['stock-fundamentals-summary', symbol, period, basis],
    queryFn: () => api.stockFundamentalsSummary(symbol, period, basis),
  });
  const raw = useQuery({
    queryKey: ['stock-fundamentals', symbol, period, basis],
    queryFn: () =>
      api.stockFundamentals(
        symbol,
        new URLSearchParams({ reporting_period: period, reporting_basis: basis }).toString(),
      ),
    enabled: showRaw,
  });

  const periods = (summary.data?.periods || []).slice(0, 5);
  const groups = summary.data?.groups || {};
  const definitions = summary.data?.definitions || {};

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Fundamentals</h2>
          <p className="panel-subtitle">
            Core profitability, growth, leverage and cash-flow ratios. {summary.data?.note || ''}
            {summary.data?.source ? ` Source: ${summary.data.source}.` : ''}
          </p>
        </div>
        <SyncJobButton
          symbol={symbol}
          kind="fundamentals"
          invalidateKeys={[
            ['stock-fundamentals-summary', symbol],
            ['stock-fundamentals', symbol],
            ['stock-statements', symbol],
            ['stock-shareholding', symbol],
          ]}
        />
      </div>
      <div className="filters">
        <select value={period} onChange={(event) => setPeriod(event.target.value)}>
          <option value="ANNUAL">Annual</option>
          <option value="QUARTERLY">Quarterly</option>
        </select>
        <select value={basis} onChange={(event) => setBasis(event.target.value)}>
          <option value="CONSOLIDATED">Consolidated</option>
          <option value="STANDALONE">Standalone</option>
        </select>
        <button type="button" className="text-button" onClick={() => setShowRaw((value) => !value)}>
          {showRaw ? 'Hide raw table' : 'Show raw table'}
        </button>
      </div>
      {summary.isLoading && <div className="loading">Loading fundamentals…</div>}
      {summary.error && <div className="empty">{(summary.error as Error).message}</div>}
      {!summary.isLoading && !periods.length && (
        <div className="empty">No fundamentals yet. Sync to pull Screener data.</div>
      )}
      {periods.length > 0 &&
        CORE_GROUPS.map((group) => {
          const metrics = groups[group] as Record<string, Record<string, unknown>> | undefined;
          if (!metrics) return null;
          const hasAny = Object.values(metrics).some((values) => Object.keys(values || {}).length > 0);
          if (!hasAny) return null;
          return (
            <div key={group} className="fundamentals-group">
              <h3>{GROUP_LABELS[group] || group}</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Metric</th>
                      {periods.map((item: string) => (
                        <th key={item}>{String(item).slice(0, 10)}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(metrics).map(([code, values]) => (
                      <tr key={code}>
                        <td title={definitions[code] || ''}>
                          {METRIC_LABELS[code] || code}
                          {definitions[code] ? <small className="metric-def"> — {definitions[code]}</small> : null}
                        </td>
                        {periods.map((item: string) => (
                          <td key={item}>{values[item] == null ? '—' : String(values[item])}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      {showRaw && (
        <div className="raw-block">
          {raw.isLoading && <div className="loading">Loading raw fundamentals…</div>}
          {raw.data && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {Object.keys(raw.data[0] || { metric_code: '', metric_value: '' }).map((key) => (
                      <th key={key}>{key.replaceAll('_', ' ')}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(raw.data || []).map((row: any, index: number) => (
                    <tr key={index}>
                      {Object.keys(row).map((key) => (
                        <td key={key}>{String(row[key] ?? '—')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
