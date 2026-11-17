import React from 'react';
import { formatDisplayDate, formatRatio } from '../lib/format';
import { indexLabel } from '../lib/homeIndexes';
import { changeClass, formatChange } from './IndexStrip';

export default function IndexTable({
  rows,
  onEdit,
}: {
  rows: any[];
  onEdit?: (row: any) => void;
}) {
  return (
    <div className="table-wrap stock-table-wrap index-table-wrap">
      <table className="stock-table index-table">
        <thead>
          <tr>
            <th>Index</th>
            <th>Code</th>
            <th>Yahoo</th>
            <th className="num">Close</th>
            <th className="num">Change</th>
            <th className="num">As of</th>
            {onEdit ? <th /> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.index_code}>
              <td className="company-cell">{indexLabel(row)}</td>
              <td className="symbol-cell">{String(row.index_code || '').toUpperCase()}</td>
              <td className="symbol-cell">{row.yf_symbol || '—'}</td>
              <td className="num">{formatRatio(row.close)}</td>
              <td className={`num ${changeClass(row.change_pct) || ''}`.trim()}>
                {formatChange(row.change_pct)}
              </td>
              <td className="num">{formatDisplayDate(row.as_of)}</td>
              {onEdit ? (
                <td className="num">
                  <button type="button" className="text-link index-edit-btn" onClick={() => onEdit(row)}>
                    Edit
                  </button>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
