import { freshnessDateBits } from '../../../lib/syncFailures';

export default function StockDataFooter({ stock }: { stock: any }) {
  const freshnessBits = freshnessDateBits(stock?.freshness || {});
  const metaBits = [
    stock?.isin ? `ISIN ${stock.isin}` : null,
    stock?.bse_code ? `BSE ${stock.bse_code}` : null,
    stock?.market_cap_class || null,
    stock?.listing_status || null,
  ].filter(Boolean);
  const notes = [
    ...metaBits,
    ...freshnessBits,
    !stock?.adjusted_history_available ? 'Unadjusted prices' : null,
    !stock?.adjusted_history_available ? 'Source: yfinance' : null,
  ].filter(Boolean);

  if (!notes.length) return null;

  return (
    <footer className="stock-data-footer">
      <p>{notes.join(' · ')}</p>
    </footer>
  );
}
