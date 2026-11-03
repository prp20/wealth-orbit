export type ChartRange = '1M' | '3M' | '6M' | '1Y' | '3Y' | 'MAX';

const RANGES: ChartRange[] = ['1M', '3M', '6M', '1Y', '3Y', 'MAX'];

export function rangeToFromDate(range: ChartRange, today = new Date()): string | undefined {
  if (range === 'MAX') return undefined;
  const date = new Date(today);
  const months = range === '1M' ? 1 : range === '3M' ? 3 : range === '6M' ? 6 : range === '1Y' ? 12 : 36;
  date.setMonth(date.getMonth() - months);
  return date.toISOString().slice(0, 10);
}

export default function ChartToolbar({
  range,
  onChange,
}: {
  range: ChartRange;
  onChange: (range: ChartRange) => void;
}) {
  return (
    <div className="chart-toolbar">
      {RANGES.map((item) => (
        <button
          key={item}
          type="button"
          className={item === range ? 'active' : ''}
          onClick={() => onChange(item)}
        >
          {item}
        </button>
      ))}
    </div>
  );
}
