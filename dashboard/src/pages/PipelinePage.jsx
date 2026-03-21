import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import StatCard from '../components/StatCard';
import { Layers, TrendingUp, Clock, Zap } from 'lucide-react';
import { getPipelineSummary, getScoringDistribution } from '../lib/api';

const STAGE_COLORS = {
  new: '#9aa5bd',
  scanned: '#5b7ec2',
  scored: '#818cf8',
  enriched: '#34d399',
  qualified: '#22c55e',
  approval_queue: '#fbbf24',
  outreach_active: '#f97316',
  meeting_booked: '#a855f7',
  rejected: '#ef4444',
  parked: '#9ca3af',
};

const PIE_COLORS = ['#ef4444', '#f59e0b', '#3a5289', '#8b5cf6', '#9aa5bd'];

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
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  const stageData = pipeline?.stages
    ? Object.entries(pipeline.stages).map(([stage, count]) => ({
        name: stage.replace(/_/g, ' '),
        count,
        fill: STAGE_COLORS[stage] || '#9aa5bd',
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
        <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Pipeline</h2>
        <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Company progression through the acquisition funnel</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total in Pipeline" value={pipeline?.total ?? '—'} icon={Layers} color="blue" />
        <StatCard label="Scanned Today" value={pipeline?.scanned_today ?? '—'} icon={Zap} color="green" />
        <StatCard label="Scored Today" value={pipeline?.scored_today ?? '—'} icon={TrendingUp} color="purple" />
        <StatCard label="Avg. Processing Time" value={pipeline?.avg_processing_hours ? `${pipeline.avg_processing_hours}h` : '—'} icon={Clock} color="amber" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stage funnel */}
        <div className="lg:col-span-2 glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-4" style={{ color: '#374a6d' }}>Pipeline Stages</h3>
          {stageData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={stageData} layout="vertical" margin={{ left: 100 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(15,26,46,0.06)" />
                <XAxis type="number" tick={{ fill: '#6b7a99', fontSize: 12 }} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#374a6d', fontSize: 12 }} />
                <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(91,126,194,0.2)', borderRadius: '8px', boxShadow: '0 4px 12px rgba(15,26,46,0.1)' }} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {stageData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-center py-12" style={{ color: '#9aa5bd' }}>No pipeline data yet</p>
          )}
        </div>

        {/* Priority distribution */}
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-4" style={{ color: '#374a6d' }}>Priority Distribution</h3>
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
                  <Tooltip contentStyle={{ background: 'rgba(255,255,255,0.95)', border: '1px solid rgba(91,126,194,0.2)', borderRadius: '8px', boxShadow: '0 4px 12px rgba(15,26,46,0.1)' }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2 mt-2">
                {priorityData.map((item, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.fill }} />
                      <span className="capitalize" style={{ color: '#6b7a99' }}>{item.name}</span>
                    </div>
                    <span className="font-medium" style={{ color: '#1b2a4a' }}>{item.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-center py-12" style={{ color: '#9aa5bd' }}>No scoring data yet</p>
          )}
        </div>
      </div>
    </div>
  );
}
