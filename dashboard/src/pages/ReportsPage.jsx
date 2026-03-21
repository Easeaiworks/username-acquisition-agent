import { useState, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, AreaChart, Area,
} from 'recharts';
import StatCard from '../components/StatCard';
import { FileText, TrendingUp, TrendingDown, Mail, Calendar, RefreshCw } from 'lucide-react';
import { getTodayReport, getReportHistory, getReportTrends, generateReport } from '../lib/api';

const chartTooltipStyle = {
  background: 'rgba(255,255,255,0.95)',
  border: '1px solid rgba(91,126,194,0.2)',
  borderRadius: '8px',
  boxShadow: '0 4px 12px rgba(15,26,46,0.1)',
};

function TrendIndicator({ value, label }) {
  if (value == null) return null;
  const isUp = value >= 0;
  return (
    <div className="flex items-center gap-1">
      {isUp ? <TrendingUp size={14} style={{ color: '#059669' }} /> : <TrendingDown size={14} style={{ color: '#dc2626' }} />}
      <span className="text-xs font-medium" style={{ color: isUp ? '#059669' : '#dc2626' }}>
        {isUp ? '+' : ''}{value}%
      </span>
      {label && <span className="text-xs ml-0.5" style={{ color: '#9aa5bd' }}>{label}</span>}
    </div>
  );
}

export default function ReportsPage() {
  const [todayReport, setTodayReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [trends, setTrends] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [historyDays, setHistoryDays] = useState(30);

  const load = async () => {
    setLoading(true);
    try {
      const [today, hist, tr] = await Promise.allSettled([
        getTodayReport(),
        getReportHistory(historyDays),
        getReportTrends(14),
      ]);
      if (today.status === 'fulfilled') setTodayReport(today.value?.report || today.value);
      if (hist.status === 'fulfilled') setHistory(hist.value?.reports || []);
      if (tr.status === 'fulfilled' && tr.value?.trends) setTrends(tr.value);
    } catch (e) {
      console.error('Reports load error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [historyDays]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await generateReport();
      setTimeout(load, 2000);
    } catch (e) {
      console.error('Generate error:', e);
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  const rpt = todayReport || {};
  const pipeline = rpt.pipeline || {};
  const outreach = rpt.outreach || {};
  const scoring = rpt.scoring || {};
  const attention = rpt.attention_required || {};
  const topOpps = rpt.top_opportunities || [];

  const trendData = trends?.trends || {};

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Reports</h2>
          <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>
            Daily pipeline analytics and trend tracking
            {rpt.report_date && <span className="ml-2" style={{ color: '#9aa5bd' }}>· {rpt.report_date}</span>}
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg text-white disabled:opacity-50 transition-all duration-200"
          style={{ background: 'linear-gradient(135deg, #3a5289, #2b3f6b)', boxShadow: '0 2px 8px rgba(58,82,137,0.3)' }}
          onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(58,82,137,0.4)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 2px 8px rgba(58,82,137,0.3)'; }}
        >
          <RefreshCw size={14} className={generating ? 'animate-spin' : ''} />
          {generating ? 'Generating...' : 'Generate Report'}
        </button>
      </div>

      {/* Today's KPIs with trends */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'New Companies', value: pipeline.new_companies_today, sub: 'Discovered today', trend: null },
          { label: 'Emails Sent', value: outreach.sent_today, sub: null, trend: trendData.emails_sent?.change_pct },
          { label: 'Replies', value: outreach.replies_today, sub: null, trend: trendData.replies?.change_pct },
          { label: 'Meetings Booked', value: outreach.meetings_booked_today, sub: null, trend: trendData.meetings?.change_pct },
        ].map(({ label, value, sub, trend }, i) => (
          <div key={i} className="glass-card rounded-xl p-5">
            <p className="text-sm font-medium" style={{ color: '#6b7a99' }}>{label}</p>
            <p className="text-2xl font-bold mt-1" style={{ color: '#1b2a4a' }}>{value ?? '—'}</p>
            {sub && <p className="text-xs mt-1" style={{ color: '#9aa5bd' }}>{sub}</p>}
            {trend != null && <TrendIndicator value={trend} label="vs prev period" />}
          </div>
        ))}
      </div>

      {/* Attention bar */}
      {Object.values(attention).some(v => v > 0) && (
        <div className="rounded-xl p-4" style={{
          background: 'linear-gradient(145deg, rgba(254,243,199,0.7), rgba(253,230,138,0.4))',
          border: '1px solid rgba(217,119,6,0.15)',
        }}>
          <h3 className="text-sm font-semibold mb-2" style={{ color: '#92400e' }}>Attention Required</h3>
          <div className="flex flex-wrap gap-4 text-sm" style={{ color: '#a16207' }}>
            {attention.pending_approvals > 0 && (
              <span>{attention.pending_approvals} pending approvals</span>
            )}
            {attention.hot_leads_no_meeting > 0 && (
              <span>{attention.hot_leads_no_meeting} hot leads need meeting</span>
            )}
            {attention.unreviewed_objections > 0 && (
              <span>{attention.unreviewed_objections} objections to review</span>
            )}
            {attention.stale_sequences > 0 && (
              <span>{attention.stale_sequences} stale sequences</span>
            )}
          </div>
        </div>
      )}

      {/* Historical trends */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-card rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold" style={{ color: '#374a6d' }}>Outreach Over Time</h3>
            <select
              value={historyDays}
              onChange={(e) => setHistoryDays(Number(e.target.value))}
              className="text-xs rounded px-2 py-1"
              style={{ border: '1px solid rgba(91,126,194,0.2)', background: 'rgba(255,255,255,0.8)', color: '#374a6d' }}
            >
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
              <option value={60}>60 days</option>
              <option value={90}>90 days</option>
            </select>
          </div>
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,26,46,0.06)" />
                <XAxis dataKey="report_date" tick={{ fontSize: 10, fill: '#6b7a99' }} />
                <YAxis tick={{ fill: '#6b7a99' }} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Area type="monotone" dataKey="emails_sent" stackId="1" stroke="#3a5289" fill="rgba(58,82,137,0.2)" name="Sent" />
                <Area type="monotone" dataKey="replies_received" stackId="2" stroke="#22c55e" fill="rgba(34,197,94,0.15)" name="Replies" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-center py-12" style={{ color: '#9aa5bd' }}>Not enough history — reports build over time</p>
          )}
        </div>

        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-4" style={{ color: '#374a6d' }}>Pipeline Growth</h3>
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,26,46,0.06)" />
                <XAxis dataKey="report_date" tick={{ fontSize: 10, fill: '#6b7a99' }} />
                <YAxis tick={{ fill: '#6b7a99' }} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Line type="monotone" dataKey="pipeline_total" stroke="#6366f1" strokeWidth={2} dot={false} name="Total Pipeline" />
                <Line type="monotone" dataKey="new_companies" stroke="#f59e0b" strokeWidth={2} dot={false} name="New/day" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-center py-12" style={{ color: '#9aa5bd' }}>Not enough history — reports build over time</p>
          )}
        </div>
      </div>

      {/* Meetings and scoring trends */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-4" style={{ color: '#374a6d' }}>Meetings Booked</h3>
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={history}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(15,26,46,0.06)" />
                <XAxis dataKey="report_date" tick={{ fontSize: 10, fill: '#6b7a99' }} />
                <YAxis tick={{ fill: '#6b7a99' }} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Bar dataKey="meetings_booked" fill="#a855f7" radius={[4, 4, 0, 0]} name="Meetings" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-center py-12" style={{ color: '#9aa5bd' }}>No meeting data yet</p>
          )}
        </div>

        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-4" style={{ color: '#374a6d' }}>Average Score Trend</h3>
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,26,46,0.06)" />
                <XAxis dataKey="report_date" tick={{ fontSize: 10, fill: '#6b7a99' }} />
                <YAxis domain={[0, 1]} tick={{ fill: '#6b7a99' }} />
                <Tooltip contentStyle={chartTooltipStyle} />
                <Line type="monotone" dataKey="avg_score" stroke="#f97316" strokeWidth={2} dot={false} name="Avg Score" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-center py-12" style={{ color: '#9aa5bd' }}>No scoring data yet</p>
          )}
        </div>
      </div>

      {/* Today's top opportunities */}
      {topOpps.length > 0 && (
        <div className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold mb-3" style={{ color: '#374a6d' }}>Today's Top Discoveries</h3>
          <div style={{ borderTop: '1px solid rgba(91,126,194,0.06)' }}>
            {topOpps.slice(0, 5).map((opp, i) => (
              <div
                key={opp.id || i}
                className="flex items-center justify-between py-2.5 transition-all duration-200"
                style={{ borderBottom: '1px solid rgba(15,26,46,0.04)' }}
                onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(91, 126, 194, 0.04)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
              >
                <div className="flex items-center gap-3 px-2">
                  <span className="text-xs w-4" style={{ color: '#9aa5bd' }}>{i + 1}.</span>
                  <div>
                    <p className="text-sm font-medium" style={{ color: '#1b2a4a' }}>{opp.brand_name}</p>
                    <p className="text-xs" style={{ color: '#9aa5bd' }}>{opp.industry || opp.domain || ''}</p>
                  </div>
                </div>
                <div className="text-right px-2">
                  <p className="font-mono text-sm font-medium" style={{ color: '#3a5289' }}>{opp.composite_score?.toFixed(3)}</p>
                  <p className="text-xs capitalize" style={{ color: '#9aa5bd' }}>{opp.priority_bucket?.replace(/_/g, ' ')}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Totals summary */}
      {trends?.totals && (
        <div className="glass-card rounded-xl p-5" style={{
          background: 'linear-gradient(145deg, rgba(238,241,248,0.9), rgba(224,230,242,0.7))',
        }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: '#374a6d' }}>Period Totals ({trends.period_days} days)</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            {[
              ['Total Emails', trends.totals.total_emails],
              ['Total Replies', trends.totals.total_replies],
              ['Total Meetings', trends.totals.total_meetings],
              ['New Companies', trends.totals.total_new_companies],
            ].map(([label, val]) => (
              <div key={label}>
                <p style={{ color: '#6b7a99' }}>{label}</p>
                <p className="text-lg font-bold" style={{ color: '#1b2a4a' }}>{val}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
