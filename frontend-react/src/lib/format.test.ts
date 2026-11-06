import { describe, expect, it } from 'vitest';
import { firstSentence, formatPct, formatPercentPoints, formatStatementValue } from './format';

describe('formatPercentPoints', () => {
  it('prints stored percent points without rescaling', () => {
    expect(formatPercentPoints(1.2)).toBe('1.20%');
    expect(formatPercentPoints(0.4)).toBe('0.40%');
    expect(formatPercentPoints(null)).toBe('—');
    expect(formatPct(0.4)).toBe('40.00%');
  });
});

describe('formatStatementValue', () => {
  it('keeps EPS in rupees, margins in percent points, and other lines in crore', () => {
    expect(formatStatementValue('EPS', 42.5)).toBe('₹42.50');
    expect(formatStatementValue('OPERATING_MARGIN', 18.2)).toBe('18.20%');
    expect(formatStatementValue('REVENUE', 125000)).toBe('1,25,000 Cr');
    expect(formatStatementValue('DEBT_TO_EQUITY', 0.42)).toBe('0.42');
  });
});

describe('firstSentence', () => {
  it('keeps the first sentence and caps a long one', () => {
    expect(firstSentence('')).toBe('');
    expect(firstSentence('ABB India Limited develops products. It also sells them.')).toBe(
      'ABB India Limited develops products.',
    );
    const long = `${'word '.repeat(80)}end.`;
    const sentence = firstSentence(long);
    expect(sentence.endsWith('…')).toBe(true);
    expect(sentence.length).toBeLessThanOrEqual(281);
  });
});
