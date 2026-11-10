import { formatCount, formatDisplayDate, formatInr, firstSentence } from '../../../lib/format';
import { freshnessDateBits, freshnessFailureLine } from '../../../lib/syncFailures';

export default function StockHeader({ stock }: { stock: any }) {
  const price = stock?.latest_price;
  const freshness = stock?.freshness || {};
  const summary = firstSentence(stock?.business_summary);
  const syncFailureLine = freshnessFailureLine(freshness);
  const freshnessBits = freshnessDateBits(freshness);
  const identityBits = [
    stock?.exchange,
    stock?.sector_name,
    stock?.industry_name,
    stock?.isin ? `ISIN ${stock.isin}` : null,
    stock?.bse_code ? `BSE ${stock.bse_code}` : null,
    stock?.market_cap_class || null,
    stock?.listing_status || null,
  ].filter(Boolean);

  return (
    <section className="stock-header panel">
      <div className="stock-header-main">
        <div>
          <p className="eyebrow">{stock?.trading_symbol || '—'}</p>
          <h1 className="stock-title">{stock?.company_name || stock?.trading_symbol || 'Stock'}</h1>
          {summary ? <p className="panel-subtitle">{summary}</p> : null}
          <p className="subtitle">{identityBits.join(' · ') || '—'}</p>
          {!stock?.adjusted_history_available && (
            <p className="panel-subtitle">Prices are not adjusted for splits or bonuses. Source: yfinance.</p>
          )}
          {freshnessBits.length > 0 && <p className="panel-subtitle">{freshnessBits.join(' · ')}</p>}
          {syncFailureLine && <p className="panel-subtitle sync-failure-line">{syncFailureLine}</p>}
        </div>
        <div className="stock-price-block">
          <small>Last close</small>
          <strong>{formatInr(price?.close)}</strong>
          <small>{formatDisplayDate(price?.date)}</small>
          {price?.volume != null && price.volume !== '' && <small>Volume {formatCount(price.volume)}</small>}
          {price?.high_52w != null && price.high_52w !== '' && (
            <small>52-week high {formatInr(price.high_52w)}</small>
          )}
          {price?.low_52w != null && price.low_52w !== '' && <small>52-week low {formatInr(price.low_52w)}</small>}
        </div>
      </div>
    </section>
  );
}
