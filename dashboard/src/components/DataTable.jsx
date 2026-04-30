export default function DataTable({ columns, rows, onRowClick, emptyMessage = 'No data available' }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="glass-table rounded-xl p-8 text-center text-sm" style={{ color: '#9aa5bd' }}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="glass-table rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(15, 26, 46, 0.06)', background: 'rgba(238, 241, 248, 0.5)' }}>
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider"
                  style={{ color: '#6b7a99', ...(col.width ? { width: col.width } : {}) }}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={row.id || i}
                onClick={() => onRowClick?.(row)}
                className={`transition-all duration-200 ${onRowClick ? 'cursor-pointer' : ''}`}
                style={{ borderBottom: '1px solid rgba(15, 26, 46, 0.04)' }}
                onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(91, 126, 194, 0.04)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
              >
                {columns.map((col) => (
                  <td key={col.key} className="px-4 py-3 whitespace-nowrap" style={{ color: '#374a6d' }}>
                    {col.render ? col.render(row[col.key], row) : row[col.key] ?? '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
