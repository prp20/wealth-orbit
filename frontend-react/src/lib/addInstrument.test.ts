import { describe, expect, it } from 'vitest';
import {
  addInstrumentButtonLabel,
  addInstrumentCodeLabel,
  addInstrumentDialogTitle,
  fundDetailPath,
  normalizeHistoryPeriod,
  stockDetailPath,
  validateAddInstrumentCode,
} from './addInstrument';

describe('addInstrument helpers', () => {
  it('validates empty codes for preview and add', () => {
    expect(validateAddInstrumentCode('', 'preview')).toBe('Enter a code to preview.');
    expect(validateAddInstrumentCode('  ', 'add')).toBe('Enter a code to add.');
    expect(validateAddInstrumentCode('RELIANCE', 'preview')).toBeNull();
  });

  it('labels India-first identifier fields and buttons', () => {
    expect(addInstrumentCodeLabel('stock')).toBe('NSE trading symbol');
    expect(addInstrumentCodeLabel('fund')).toBe('AMFI scheme code');
    expect(addInstrumentCodeLabel('index')).toBe('Index code');
    expect(addInstrumentButtonLabel('stock')).toBe('Add stock');
    expect(addInstrumentButtonLabel('fund')).toBe('Add fund');
    expect(addInstrumentDialogTitle('index')).toBe('Add index');
  });

  it('builds detail navigation paths', () => {
    expect(stockDetailPath('RELIANCE')).toBe('/stocks/RELIANCE');
    expect(fundDetailPath('120503')).toBe('/mutualfunds/120503');
  });

  it('normalizes history depth presets', () => {
    expect(normalizeHistoryPeriod('10y')).toBe('10y');
    expect(normalizeHistoryPeriod('max')).toBe('max');
    expect(normalizeHistoryPeriod('nope')).toBe('5y');
  });
});
