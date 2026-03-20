import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import StatCard from '../components/StatCard';
import { Layers, TrendingUp, Clock, Zap } from 'lucide-react';
import { getPipelineSummary, getScoringDistribution } from '../lib/api';

const STAGE_COLORS = {
  new: '#94a3b8',
  scanned: '#60a5fa',
  scored: '#818cf8',
  enriched: '#34d399',
  qualified: '#22c55e',
  approval_queue: '#fbbf24',
  outreach_active: '#f97316',
  meeting_booked: '#a855f7',
  rejected: '#ef4444',
  parked: '#9ca3af',
};

const PIE_COLORS = ['#ef4444', '#f59e0b', '#3b82f6', '#8b5cf6', '#9ca3af'];

export default function PipelinePage() {
  const [pipeline, setPipeline] = useState(null);
  const [distribution, setDistribution] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [p, d] = await Promise.allSettled([
          getPipelineSummary(),
          getScoringDistribution(),
        ]);
        if (p.status === 'fulfilled') setPipeline(p.value);
        if (d.status === 'fulfilled') setDistribution(d.value);
      } catch (e) {
        console.error('Pipeline load error:', e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  const stageData = pipeline?.stages
    ? Object.entries(pipeline.stages).map(([stage, count]) => ({
        name: stage.replace(/_/g, ' '),
        count,
        fill: STAGE_COLORS[stage] || '#94a3b8',
      }))
    : [];

  const priorityData = distribution?.buckets
    ? Object.entries(distribution.buckets).map(([bucket, count], i) => ({
        name: bucket.replace(/_/g, ' '),
        value: count,
        fill: PIE_COLORS[i % PIE_COLORS.length],
      }))
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-gray-900">Pipeline</h2>
        <p className="text-sm text-gray-500 mt-1">Company progression through the acquisition funnel</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total in Pipeline" value={pipeline?.total ?? '—'} icon={Layers} color="blue" />
        <StatCard label="Scanned Today" value={pipeline?.scanned_today ?? '—'} icon={Zap} color="green" />
        <StatCard label="Scored Today" value={pipeline?.scored_today ?? '—'} icon={TrendingUp} color="purple" />
        <StatCard label="Avg. Processing Time" value={pipeline?.avg_processing_hours ? `${pipeline.avg_processing_hours}h` : '—'} icon={Clock} color="amber" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stage funnel */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Pipeline Stages</h3>
          {stageData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={stageData} layout="vertical" margin={{ left: 100 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {stageData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-400 text-center py-12">No pipeline data yet</p>
          )}
        </div>

        {/* Priority distribution */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Priority Distribution</h3>
          {priorityData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={priorityData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {priorityData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2 mt-2">
                {priorityData.map((item, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.fill }} />
                      <span className="text-gray-600 capitalize">{item.name}</span>
                    </div>
                    <span className="font-medium text-gray-900">{item.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-gray-400 text-center py-12">No scoring data yet</p>
          )}
        </div>
      </div>
    </div>
  );
}
