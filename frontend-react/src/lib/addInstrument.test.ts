import { describe, expect, it } from 'vitest';
import {
  addInstrumentCodeLabel,
  fundDetailPath,
  stockDetailPath,
  validateAddInstrumentCode,
} from './addInstrument';

describe('addInstrument helpers', () => {
  it('validates empty codes for preview and add', () => {
    expect(validateAddInstrumentCode('', 'preview')).toBe('Enter a code to preview.');
    expect(validateAddInstrumentCode('  ', 'add')).toBe('Enter a code to add.');
    expect(validateAddInstrumentCode('RELIANCE', 'preview')).toBeNull();
  });

  it('labels India-first identifier fields', () => {
    expect(addInstrumentCodeLabel('stock')).toBe('NSE trading symbol');
    expect(addInstrumentCodeLabel('fund')).toBe('AMFI scheme code');
    expect(addInstrumentCodeLabel('index')).toBe('Index code');
  });

  it('builds detail navigation paths', () => {
    expect(stockDetailPath('RELIANCE')).toBe('/stocks/RELIANCE');
    expect(fundDetailPath('120503')).toBe('/mutualfunds/120503');
  });
});
