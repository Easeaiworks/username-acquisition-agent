import { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';
import StatCard from '../components/StatCard';
import DataTable from '../components/DataTable';
import Badge from '../components/Badge';
import { Mail, Send, MessageSquare, Calendar, Zap } from 'lucide-react';
import { getOutreachStats, getPendingOutreach, triggerAutoOutreach, triggerFollowups } from '../lib/api';

const STATUS_COLORS = {
  draft: 'gray',
  sent: 'blue',
  replied: 'green',
  bounced: 'red',
  meeting_booked: 'purple',
};

export default function OutreachPage() {
  const [stats, setStats] = useState(null);
  const [pending, setPending] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const [s, p] = await Promise.allSettled([
          getOutreachStats(30),
          getPendingOutreach(),
        ]);
        if (s.status === 'fulfilled') setStats(s.value);
        if (p.status === 'fulfilled') setPending(Array.isArray(p.value) ? p.value : p.value.items || []);
      } catch (e) {
        console.error('Outreach load error:', e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleAction = async (action, label) => {
    setActionLoading(label);
    try {
      await action();
      // Reload stats
      const s = await getOutreachStats(30);
      setStats(s);
    } catch (e) {
      console.error(`${label} error:`, e);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  const dailyData = stats?.daily_sends || [];
  const responseData = stats?.response_breakdown
    ? Object.entries(stats.response_breakdown).map(([cat, count]) => ({
        name: cat.replace(/_/g, ' '),
        count,
        fill: cat === 'positive' ? '#22c55e' : cat === 'negative' ? '#ef4444' : cat === 'objection' ? '#f59e0b' : '#94a3b8',
      }))
    : [];

  const pendingColumns = [
    { key: 'company_name', label: 'Company', render: (v) => v || '—' },
    { key: 'contact_name', label: 'Contact', render: (v) => v || '—' },
    { key: 'contact_email', label: 'Email', render: (v) => v || '—' },
    {
      key: 'sequence_step',
      label: 'Step',
      render: (v) => <span className="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded">{v}/4</span>,
    },
    {
      key: 'status',
      label: 'Status',
      render: (v) => <Badge color={STATUS_COLORS[v] || 'gray'}>{v}</Badge>,
    },
    {
      key: 'next_send_at',
      label: 'Scheduled',
      render: (v) => v ? new Date(v).toLocaleDateString() : '—',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Outreach</h2>
          <p className="text-sm text-gray-500 mt-1">Email sequences and engagement tracking</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleAction(triggerAutoOutreach, 'outreach')}
            disabled={actionLoading !== null}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {actionLoading === 'outreach' ? (
              <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-white" />
            ) : (
              <Send size={14} />
            )}
            Run Outreach
          </button>
          <button
            onClick={() => handleAction(triggerFollowups, 'followups')}
            disabled={actionLoading !== null}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {actionLoading === 'followups' ? (
              <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-gray-600" />
            ) : (
              <Zap size={14} />
            )}
            Process Follow-ups
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Emails Sent" value={stats?.total_sent ?? '—'} sub="Last 30 days" icon={Mail} color="blue" />
        <StatCard label="Replies" value={stats?.total_replies ?? '—'} sub={stats?.reply_rate ? `${(stats.reply_rate * 100).toFixed(1)}% rate` : ''} icon={MessageSquare} color="green" />
        <StatCard label="Meetings Booked" value={stats?.meetings_booked ?? '—'} sub="From outreach" icon={Calendar} color="purple" />
        <StatCard label="Active Sequences" value={stats?.active_sequences ?? '—'} sub="In progress" icon={Send} color="amber" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Daily send volume */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Daily Send Volume</h3>
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={dailyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="sent" stroke="#3b82f6" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="replied" stroke="#22c55e" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-400 text-center py-12">No send data yet</p>
          )}
        </div>

        {/* Response breakdown */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Response Breakdown</h3>
          {responseData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={responseData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {responseData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-400 text-center py-12">No replies yet</p>
          )}
        </div>
      </div>

      {/* Pending outreach queue */}
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Pending Queue</h3>
        <DataTable
          columns={pendingColumns}
          rows={pending}
          emptyMessage="No pending outreach in the queue"
        />
      </div>
    </div>
  );
}
