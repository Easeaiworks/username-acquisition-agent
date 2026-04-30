import { useState, useEffect } from 'react';
import { Building2, Target, Mail, CheckSquare, TrendingUp, Clock } from 'lucide-react';
import StatCard from '../components/StatCard';
import DataTable from '../components/DataTable';
import { PriorityBadge, StatusBadge } from '../components/Badge';
import { getDashboardOverview, getTopOpportunities, getRecentActivity } from '../lib/api';

export default function OverviewPage() {
  const [overview, setOverview] = useState(null);
  const [topOpps, setTopOpps] = useState([]);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [ov, opps, act] = await Promise.allSettled([
          getDashboardOverview(),
          getTopOpportunities(5),
          getRecentActivity(10),
        ]);
        if (ov.status === 'fulfilled') setOverview(ov.value);
        if (opps.status === 'fulfilled') setTopOpps(opps.value);
        if (act.status === 'fulfilled') setActivity(act.value);
      } catch (e) {
        console.error('Overview load error:', e);
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

  const stats = overview || {};

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Dashboard Overview</h2>
        <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Daily pipeline status and key metrics</p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Companies"
          value={stats.total_companies ?? '—'}
          sub="In pipeline"
          icon={Building2}
          color="blue"
        />
        <StatCard
          label="Active Opportunities"
          value={stats.active_opportunities ?? '—'}
          sub="Score ≥ 0.5"
          icon={Target}
          color="green"
        />
        <StatCard
          label="Outreach Active"
          value={stats.outreach_active ?? '—'}
          sub="Sequences running"
          icon={Mail}
          color="amber"
        />
        <StatCard
          label="Meetings Booked"
          value={stats.meetings_booked ?? '—'}
          sub="All time"
          icon={CheckSquare}
          color="purple"
        />
      </div>

      {/* Secondary stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          label="Pending Approvals"
          value={stats.pending_approvals ?? '—'}
          icon={Clock}
          color="amber"
        />
        <StatCard
          label="Avg. Score"
          value={stats.avg_score != null ? stats.avg_score.toFixed(2) : '—'}
          icon={TrendingUp}
          color="blue"
        />
        <StatCard
          label="Response Rate"
          value={stats.response_rate != null ? `${(stats.response_rate * 100).toFixed(1)}%` : '—'}
          icon={Mail}
          color="green"
        />
      </div>

      {/* Two-column: Top Opportunities + Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm font-semibold mb-3" style={{ color: '#374a6d' }}>Top Opportunities</h3>
          <DataTable
            columns={[
              { key: 'brand_name', label: 'Company' },
              {
                key: 'composite_score',
                label: 'Score',
                render: (v) => (
                  <span className="font-mono font-medium" style={{ color: '#3a5289' }}>{v != null ? v.toFixed(2) : '—'}</span>
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
            ]}
            rows={topOpps}
            emptyMessage="No scored opportunities yet"
          />
        </div>

        <div>
          <h3 className="text-sm font-semibold mb-3" style={{ color: '#374a6d' }}>Recent Activity</h3>
          <div className="glass-table rounded-xl" style={{ overflow: 'hidden' }}>
            {activity.length === 0 ? (
              <p className="p-4 text-sm text-center" style={{ color: '#9aa5bd' }}>No recent activity</p>
            ) : (
              activity.map((item, i) => (
                <div
                  key={i}
                  className="px-4 py-3 flex items-start gap-3 transition-all duration-200"
                  style={{ borderBottom: '1px solid rgba(15, 26, 46, 0.04)' }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(91, 126, 194, 0.04)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <div className={`mt-1.5 w-2 h-2 rounded-full shrink-0 activity-dot`} style={{
                    backgroundColor:
                      item.type === 'meeting_booked' ? '#10b981' :
                      item.type === 'outreach_sent' ? '#3a5289' :
                      item.type === 'reply_received' ? '#d97706' :
                      '#9aa5bd',
                    color:
                      item.type === 'meeting_booked' ? '#10b981' :
                      item.type === 'outreach_sent' ? '#3a5289' :
                      item.type === 'reply_received' ? '#d97706' :
                      '#9aa5bd',
                  }} />
                  <div className="min-w-0">
                    <p className="text-sm truncate" style={{ color: '#374a6d' }}>{item.description}</p>
                    <p className="text-xs mt-0.5" style={{ color: '#9aa5bd' }}>{item.timestamp ? new Date(item.timestamp).toLocaleString() : ''}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
