import React from 'react';
import InfoTip from '../../../components/InfoTip';
import { formatCount, formatDisplayDate, formatInr, firstSentence } from '../../../lib/format';
import { freshnessFailureLine } from '../../../lib/syncFailures';

export default function StockHeader({ stock }: { stock: any }) {
  const price = stock?.latest_price;
  const summary = firstSentence(stock?.business_summary);
  const syncFailureLine = freshnessFailureLine(stock?.freshness || {});
  const identityBits = [stock?.exchange, stock?.sector_name, stock?.industry_name].filter(Boolean);

  const hasPriceFacts =
    price?.date ||
    (price?.volume != null && price.volume !== '') ||
    (price?.high_52w != null && price.high_52w !== '') ||
    (price?.low_52w != null && price.low_52w !== '');

  return (
    <section className="stock-header panel">
      <div className="stock-header-main">
        <div className="stock-header-copy">
          <p className="eyebrow">{stock?.trading_symbol || '—'}</p>
          <h1 className="stock-title">{stock?.company_name || stock?.trading_symbol || 'Stock'}</h1>
          <p className="subtitle">{identityBits.join(' · ') || '—'}</p>
          {summary ? <p className="stock-summary">{summary}</p> : null}
          {syncFailureLine && <p className="panel-subtitle sync-failure-line">{syncFailureLine}</p>}
        </div>
        <div className="stock-price-block">
          <div className="stock-price-label-row">
            <small>Last close</small>
            {hasPriceFacts && (
              <InfoTip label="Price details" align="right">
                {price?.date && (
                  <div>
                    <em>As of</em>
                    <span>{formatDisplayDate(price.date)}</span>
                  </div>
                )}
                {price?.volume != null && price.volume !== '' && (
                  <div>
                    <em>Volume</em>
                    <span>{formatCount(price.volume)}</span>
                  </div>
                )}
                {price?.high_52w != null && price.high_52w !== '' && (
                  <div>
                    <em>52W high</em>
                    <span>{formatInr(price.high_52w)}</span>
                  </div>
                )}
                {price?.low_52w != null && price.low_52w !== '' && (
                  <div>
                    <em>52W low</em>
                    <span>{formatInr(price.low_52w)}</span>
                  </div>
                )}
              </InfoTip>
            )}
          </div>
          <strong>{formatInr(price?.close)}</strong>
        </div>
      </div>
    </section>
  );
}
