import { useState, useEffect } from 'react';
import DataTable from '../components/DataTable';
import { PriorityBadge, StatusBadge } from '../components/Badge';
import { getTopOpportunities } from '../lib/api';

export default function OpportunitiesPage() {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState(50);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const data = await getTopOpportunities(limit);
        setOpportunities(data);
      } catch (e) {
        console.error('Opportunities load error:', e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [limit]);

  const columns = [
    { key: 'brand_name', label: 'Company' },
    {
      key: 'industry',
      label: 'Industry',
      render: (v) => <span className="capitalize">{v || '—'}</span>,
    },
    {
      key: 'composite_score',
      label: 'Score',
      render: (v) => (
        <div className="flex items-center gap-2">
          <div className="w-16 bg-gray-200 rounded-full h-1.5">
            <div
              className="bg-blue-600 h-1.5 rounded-full"
              style={{ width: `${(v || 0) * 100}%` }}
            />
          </div>
          <span className="font-mono text-xs">{v != null ? v.toFixed(2) : '—'}</span>
        </div>
      ),
    },
    {
      key: 'priority_bucket',
      label: 'Priority',
      render: (v) => <PriorityBadge priority={v} />,
    },
    {
      key: 'pipeline_stage',
      label: 'Stage',
      render: (v) => <StatusBadge status={v} />,
    },
    {
      key: 'employee_range',
      label: 'Size',
      render: (v) => v || '—',
    },
    {
      key: 'created_at',
      label: 'Added',
      render: (v) => v ? new Date(v).toLocaleDateString() : '—',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Opportunities</h2>
          <p className="text-sm text-gray-500 mt-1">Scored companies ranked by acquisition potential</p>
        </div>
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-white text-gray-700"
        >
          <option value={25}>Top 25</option>
          <option value={50}>Top 50</option>
          <option value={100}>Top 100</option>
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : (
        <DataTable
          columns={columns}
          rows={opportunities}
          emptyMessage="No scored opportunities yet. Run the scoring pipeline to populate this view."
        />
      )}
    </div>
  );
}
