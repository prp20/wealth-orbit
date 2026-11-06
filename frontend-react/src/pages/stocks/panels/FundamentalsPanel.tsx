import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../../api';
import SyncJobButton from '../../../components/SyncJobButton';
import { formatStatementValue } from '../../../lib/format';

const STATEMENT_SECTIONS = [
  { id: 'PL', title: 'Profit & loss' },
  { id: 'BS', title: 'Balance sheet' },
  { id: 'CF', title: 'Cash flow' },
] as const;

const RATIO_GROUPS = ['profitability', 'growth', 'leverage'] as const;

const GROUP_LABELS: Record<string, string> = {
  profitability: 'Profitability',
  growth: 'Growth',
  leverage: 'Leverage',
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
  REVENUE: 'Revenue',
  TOTAL_EXPENSES: 'Total expenses',
  OPERATING_PROFIT: 'Operating profit',
  OPERATING_MARGIN: 'Operating margin',
  OTHER_INCOME: 'Other income',
  DEPRECIATION: 'Depreciation',
  INTEREST_EXPENSE: 'Interest',
  PROFIT_BEFORE_TAX: 'Profit before tax',
  TAX_RATE: 'Tax',
  NET_PROFIT: 'Net profit',
  EPS: 'EPS',
  EQUITY_CAPITAL: 'Equity capital',
  RESERVES: 'Reserves',
  BORROWINGS: 'Borrowings',
  OTHER_LIABILITIES: 'Other liabilities',
  TOTAL_LIABILITIES: 'Total liabilities',
  FIXED_ASSETS: 'Fixed assets',
  CWIP: 'CWIP',
  INVESTMENTS: 'Investments',
  OTHER_ASSETS: 'Other assets',
  TOTAL_ASSETS: 'Total assets',
  CASH_FROM_OPERATING_ACTIVITIES: 'Cash from operations',
  CASH_FROM_INVESTING_ACTIVITIES: 'Cash from investing',
  CASH_FROM_FINANCING_ACTIVITIES: 'Cash from financing',
  NET_CASH_FLOW: 'Net cash flow',
  ROE: 'Return on equity',
  ROCE: 'Return on capital',
  PAT_MARGIN: 'PAT margin',
  REVENUE_GROWTH: 'Revenue growth',
  EPS_GROWTH: 'EPS growth',
  DEBT_TO_EQUITY: 'Debt / equity',
  INTEREST_COVERAGE: 'Interest coverage',
};

function orderedCodes(codes: string[]) {
  const rank = new Map(LINE_ORDER.map((code, index) => [code, index]));
  return [...codes].sort((a, b) => (rank.get(a) ?? 1000) - (rank.get(b) ?? 1000) || a.localeCompare(b));
}

function StatementTable({ title, rows }: { title: string; rows: any[] }) {
  const periods = Array.from(new Set(rows.map((row) => String(row.period_end_date)))).slice(0, 6);
  const codes = orderedCodes(Array.from(new Set(rows.map((row) => String(row.metric_code)))));
  const values = new Map(rows.map((row) => [`${row.metric_code}|${row.period_end_date}`, row.metric_value]));

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
                    {period.slice(0, 10)}
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
  const periods = (summary.data?.periods || []).slice(0, 5);
  const groups = summary.data?.groups || {};
  const definitions = summary.data?.definitions || {};

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Fundamentals</h2>
          <p className="panel-subtitle">
            Profit and loss, balance sheet, and cash flow stay in separate tables. Consolidated includes the
            subsidiaries. Standalone is the parent company only.
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
      {!lines.isLoading &&
        STATEMENT_SECTIONS.map((section) => (
          <StatementTable
            key={section.id}
            title={section.title}
            rows={rows.filter((row: any) => row.statement_type === section.id)}
          />
        ))}
      {periods.length > 0 &&
        RATIO_GROUPS.map((group) => {
          const metrics = groups[group] as Record<string, Record<string, unknown>> | undefined;
          if (!metrics) return null;
          const hasAny = Object.values(metrics).some((values) => Object.keys(values || {}).length > 0);
          if (!hasAny) return null;
          return (
            <div key={group} className="fundamentals-group">
              <h3>{GROUP_LABELS[group]}</h3>
              <div className="table-wrap statement-table-wrap">
                <table className="stock-table statement-table">
                  <thead>
                    <tr>
                      <th>Line</th>
                      {periods.map((item: string) => (
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
                        {periods.map((item: string) => (
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
