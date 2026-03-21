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

const chartTooltipStyle = {
  background: 'rgba(255,255,255,0.95)',
  border: '1px solid rgba(91,126,194,0.2)',
  borderRadius: '8px',
  boxShadow: '0 4px 12px rgba(15,26,46,0.1)',
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
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  const dailyData = stats?.daily_sends || [];
  const responseData = stats?.response_breakdown
    ? Object.entries(stats.response_breakdown).map(([cat, count]) => ({
        name: cat.replace(/_/g, ' '),
        count,
        fill: cat === 'positive' ? '#22c55e' : cat === 'negative' ? '#ef4444' : cat === 'objection' ? '#f59e0b' : '#9aa5bd',
      }))
    : [];

  const pendingColumns = [
    { key: 'company_name', label: 'Company', render: (v) => v || '—' },
    { key: 'contact_name', label: 'Contact', render: (v) => v || '—' },
    { key: 'contact_email', label: 'Email', render: (v) => v || '—' },
    {
      key: 'sequence_step',
      label: 'Step',
      render: (v) => (
        <span className="font-mono text-xs px-2 py-0.5 rounded" style={{
          background: 'rgba(58,82,137,0.08)',
          color: '#3a5289',
        }}>{v}/4</span>
      ),
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
          <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Outreach</h2>
          <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Email sequences and engagement tracking</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleAction(triggerAutoOutreach, 'outreach')}
            disabled={actionLoading !== null}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg text-white disabled:opacity-50 transition-all duration-200"
            style={{ background: 'linear-gradient(135deg, #3a5289, #2b3f6b)', boxShadow: '0 2px 8px rgba(58,82,137,0.3)' }}
            onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(58,82,137,0.4)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 2px 8px rgba(58,82,137,0.3)'; }}
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
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg disabled:opacity-50 transition-all duration-200"
            style={{ border: '1px solid rgba(91,126,194,0.2)', color: '#374a6d', background: 'rgba(255,255,255,0.8)' }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(91,126,194,0.08)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.8)'; }}
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
        <div className="lg:col-span-2 glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-4" style={{ color: '#374a6d' }}>Daily Send Volume</h3>
          {dailyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={dailyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,26,46,0.06)" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#6b7a99' }} />
                <YAxis tick={{ fill: '#6b7a99' }} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Line type="monotone" dataKey="sent" stroke="#3a5289" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="replied" stroke="#22c55e" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-center py-12" style={{ color: '#9aa5bd' }}>No send data yet</p>
          )}
        </div>

        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-4" style={{ color: '#374a6d' }}>Response Breakdown</h3>
          {responseData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={responseData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(15,26,46,0.06)" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6b7a99' }} />
                <YAxis tick={{ fill: '#6b7a99' }} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {responseData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-center py-12" style={{ color: '#9aa5bd' }}>No replies yet</p>
          )}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-3" style={{ color: '#374a6d' }}>Pending Queue</h3>
        <DataTable
          columns={pendingColumns}
          rows={pending}
          emptyMessage="No pending outreach in the queue"
        />
      </div>
    </div>
  );
}
