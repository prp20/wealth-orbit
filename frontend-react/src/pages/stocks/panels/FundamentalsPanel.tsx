import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import SyncJobButton from '../../../components/SyncJobButton';
import { formatStatementValue } from '../../../lib/format';

const ANNUAL_SECTIONS = [
  { id: 'PL', title: 'Profit & loss' },
  { id: 'BS', title: 'Balance sheet' },
  { id: 'CF', title: 'Cash flow' },
] as const;

const RATIO_GROUPS = ['profitability', 'growth', 'leverage', 'liquidity', 'efficiency'] as const;

const GROUP_LABELS: Record<string, string> = {
  profitability: 'Profitability',
  growth: 'Growth (YoY / QoQ from statements)',
  leverage: 'Leverage',
  liquidity: 'Liquidity',
  efficiency: 'Efficiency',
};

const LINE_ORDER = [
  'REVENUE',
  'TOTAL_EXPENSES',
  'OPERATING_PROFIT',
  'OPERATING_MARGIN',
  'OTHER_INCOME',
  'DEPRECIATION',
  'INTEREST_EXPENSE',
  'PROFIT_BEFORE_TAX',
  'TAX_RATE',
  'NET_PROFIT',
  'EPS',
  'EQUITY_CAPITAL',
  'RESERVES',
  'BORROWINGS',
  'OTHER_LIABILITIES',
  'TOTAL_LIABILITIES',
  'FIXED_ASSETS',
  'CWIP',
  'INVESTMENTS',
  'OTHER_ASSETS',
  'TOTAL_ASSETS',
  'CASH_FROM_OPERATING_ACTIVITIES',
  'CASH_FROM_INVESTING_ACTIVITIES',
  'CASH_FROM_FINANCING_ACTIVITIES',
  'NET_CASH_FLOW',
];

const METRIC_LABELS: Record<string, string> = {
  REVENUE: 'Sales',
  TOTAL_EXPENSES: 'Expenses',
  OPERATING_PROFIT: 'Operating Profit',
  OPERATING_MARGIN: 'OPM %',
  OTHER_INCOME: 'Other Income',
  DEPRECIATION: 'Depreciation',
  INTEREST_EXPENSE: 'Interest',
  PROFIT_BEFORE_TAX: 'Profit before tax',
  TAX_RATE: 'Tax %',
  NET_PROFIT: 'Net Profit',
  EPS: 'EPS in Rs',
  EQUITY_CAPITAL: 'Equity Capital',
  RESERVES: 'Reserves',
  BORROWINGS: 'Borrowings',
  OTHER_LIABILITIES: 'Other Liabilities',
  TOTAL_LIABILITIES: 'Total Liabilities',
  FIXED_ASSETS: 'Fixed Assets',
  CWIP: 'CWIP',
  INVESTMENTS: 'Investments',
  OTHER_ASSETS: 'Other Assets',
  TOTAL_ASSETS: 'Total Assets',
  CASH_FROM_OPERATING_ACTIVITIES: 'Cash from Operating Activity',
  CASH_FROM_INVESTING_ACTIVITIES: 'Cash from Investing Activity',
  CASH_FROM_FINANCING_ACTIVITIES: 'Cash from Financing Activity',
  NET_CASH_FLOW: 'Net Cash Flow',
  ROE: 'Return on equity',
  ROCE: 'Return on capital',
  PAT_MARGIN: 'PAT margin',
  REVENUE_GROWTH: 'Revenue growth',
  EPS_GROWTH: 'EPS growth',
  DEBT_TO_EQUITY: 'Debt / equity',
  INTEREST_COVERAGE: 'Interest coverage',
  CURRENT_RATIO: 'Current ratio',
  QUICK_RATIO: 'Quick ratio',
  ASSET_TURNOVER: 'Asset turnover',
  ROA: 'Return on assets',
};

function orderedCodes(codes: string[]) {
  const rank = new Map(LINE_ORDER.map((code, index) => [code, index]));
  return [...codes].sort((a, b) => (rank.get(a) ?? 1000) - (rank.get(b) ?? 1000) || a.localeCompare(b));
}

function StatementTable({ title, rows }: { title: string; rows: any[] }) {
  const periods = Array.from(new Set(rows.map((row) => String(row.period_end_date).slice(0, 10)))).slice(0, 6);
  const codes = orderedCodes(Array.from(new Set(rows.map((row) => String(row.metric_code)))));
  const values = new Map(
    rows.map((row) => [`${row.metric_code}|${String(row.period_end_date).slice(0, 10)}`, row.metric_value]),
  );

  return (
    <div className="fundamentals-group">
      <h3>{title}</h3>
      {!periods.length && <div className="empty">No rows for this statement.</div>}
      {periods.length > 0 && (
        <div className="table-wrap statement-table-wrap">
          <table className="stock-table statement-table">
            <thead>
              <tr>
                <th>Line</th>
                {periods.map((period) => (
                  <th key={period} className="num">
                    {period}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {codes.map((code) => (
                <tr key={code}>
                  <th scope="row">{METRIC_LABELS[code] || code}</th>
                  {periods.map((period) => (
                    <td key={period} className="num">
                      {formatStatementValue(code, values.get(`${code}|${period}`))}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function LatestRatiosStrip({
  ratios,
  snapshot,
  definitions,
}: {
  ratios: Record<string, unknown>;
  snapshot: Record<string, unknown> | undefined;
  definitions: Record<string, string>;
}) {
  const entries = Object.entries(ratios || {}).filter(([, value]) => value != null && value !== '');
  if (!entries.length) return null;
  const asOf = snapshot?.as_of ? String(snapshot.as_of).slice(0, 10) : null;
  const basis = snapshot?.reporting_basis ? String(snapshot.reporting_basis) : null;
  const method = snapshot?.calculation_method ? String(snapshot.calculation_method) : 'calc_v1';
  return (
    <div className="fundamentals-group">
      <h3>Latest ratios</h3>
      <p className="panel-subtitle">
        {basis ? `${basis === 'STANDALONE' ? 'Standalone' : 'Consolidated'}` : 'Basis'}
        {asOf ? ` · as of ${asOf}` : ''}
        {` · ${method}`}
        {snapshot?.computed_on_read ? ' · computed on read' : ' · stored snapshot'}
        . Standalone and consolidated are never mixed.
      </p>
      <div className="table-wrap statement-table-wrap">
        <table className="stock-table statement-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th className="num">Value</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([code, value]) => (
              <tr key={code}>
                <th scope="row" title={definitions[code] || ''}>
                  {METRIC_LABELS[code] || code}
                </th>
                <td className="num">{formatStatementValue(code, value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function FundamentalsPanel({ symbol }: { symbol: string }) {
  const [period, setPeriod] = React.useState('ANNUAL');
  const [basis, setBasis] = React.useState('CONSOLIDATED');
  const lines = useQuery({
    queryKey: ['stock-fundamentals', symbol, period, basis],
    queryFn: () =>
      api.stockFundamentals(
        symbol,
        new URLSearchParams({ reporting_period: period, reporting_basis: basis }).toString(),
      ),
  });
  const summary = useQuery({
    queryKey: ['stock-fundamentals-summary', symbol, period, basis],
    queryFn: () => api.stockFundamentalsSummary(symbol, period, basis),
  });

  const rows = lines.data || [];
  const periods = (summary.data?.periods || []).slice(0, 6);
  const groups = summary.data?.groups || {};
  const definitions = summary.data?.definitions || {};
  const latestRatios = summary.data?.latest_ratios || {};
  const ratioSnapshot = summary.data?.ratio_snapshot;
  const isQuarterly = period === 'QUARTERLY';

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Fundamentals</h2>
          <p className="panel-subtitle">
            Annual and quarterly statements are stored separately (up to 6 columns each). Quarterly matches
            Screener Quarterly Results; annual matches yearly Profit &amp; loss, Balance sheet, and Cash
            flow. Consolidated includes subsidiaries; standalone is the parent only — they are never mixed.
          </p>
        </div>
        <SyncJobButton
          symbol={symbol}
          kind="fundamentals"
          label="Update statements"
          invalidateKeys={[
            ['stock-fundamentals-summary', symbol],
            ['stock-fundamentals', symbol],
            ['stock-statements', symbol],
            ['stock-shareholding', symbol],
            ['stock-detail', symbol],
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
      </div>
      {lines.isLoading && <div className="loading">Loading fundamentals…</div>}
      {lines.error && <div className="empty">{(lines.error as Error).message}</div>}
      {!lines.isLoading && isQuarterly && (
        <StatementTable title="Quarterly Results" rows={rows.filter((row: any) => row.statement_type === 'PL')} />
      )}
      {!lines.isLoading &&
        !isQuarterly &&
        ANNUAL_SECTIONS.map((section) => (
          <StatementTable
            key={section.id}
            title={section.title}
            rows={rows.filter((row: any) => row.statement_type === section.id)}
          />
        ))}
      <LatestRatiosStrip ratios={latestRatios} snapshot={ratioSnapshot} definitions={definitions} />
      {periods.length > 0 &&
        RATIO_GROUPS.map((group) => {
          const metrics = groups[group] as Record<string, Record<string, unknown>> | undefined;
          if (!metrics) return null;
          const hasAny = Object.values(metrics).some((values) =>
            Object.values(values || {}).some((value) => value != null && value !== ''),
          );
          if (!hasAny) return null;
          const columnPeriods =
            group === 'growth'
              ? periods
              : Array.from(
                  new Set(
                    Object.values(metrics).flatMap((values) => Object.keys(values || {})),
                  ),
                ).sort((a, b) => b.localeCompare(a));
          return (
            <div key={group} className="fundamentals-group">
              <h3>{GROUP_LABELS[group]}</h3>
              <div className="table-wrap statement-table-wrap">
                <table className="stock-table statement-table">
                  <thead>
                    <tr>
                      <th>Line</th>
                      {columnPeriods.map((item: string) => (
                        <th key={item} className="num">
                          {String(item).slice(0, 10)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(metrics).map(([code, values]) => (
                      <tr key={code}>
                        <th scope="row" title={definitions[code] || ''}>
                          {METRIC_LABELS[code] || code}
                        </th>
                        {columnPeriods.map((item: string) => (
                          <td key={item} className="num">
                            {formatStatementValue(code, values[item])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
    </section>
  );
}
