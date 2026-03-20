import { useState, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, AreaChart, Area,
} from 'recharts';
import StatCard from '../components/StatCard';
import { FileText, TrendingUp, TrendingDown, Mail, Calendar, RefreshCw } from 'lucide-react';
import { getTodayReport, getReportHistory, getReportTrends, generateReport } from '../lib/api';

function TrendIndicator({ value, label }) {
  if (value == null) return null;
  const isUp = value >= 0;
  return (
    <div className="flex items-center gap-1">
      {isUp ? <TrendingUp size={14} className="text-green-600" /> : <TrendingDown size={14} className="text-red-600" />}
      <span className={`text-xs font-medium ${isUp ? 'text-green-600' : 'text-red-600'}`}>
        {isUp ? '+' : ''}{value}%
      </span>
      {label && <span className="text-xs text-gray-400 ml-0.5">{label}</span>}
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
      // Wait a moment then reload
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
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
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
          <h2 className="text-xl font-bold text-gray-900">Reports</h2>
          <p className="text-sm text-gray-500 mt-1">
            Daily pipeline analytics and trend tracking
            {rpt.report_date && <span className="ml-2 text-gray-400">· {rpt.report_date}</span>}
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          <RefreshCw size={14} className={generating ? 'animate-spin' : ''} />
          {generating ? 'Generating...' : 'Generate Report'}
        </button>
      </div>

      {/* Today's KPIs with trends */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm text-gray-500 font-medium">New Companies</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{pipeline.new_companies_today ?? '—'}</p>
          <p className="text-xs text-gray-400 mt-1">Discovered today</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm text-gray-500 font-medium">Emails Sent</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{outreach.sent_today ?? '—'}</p>
          <TrendIndicator value={trendData.emails_sent?.change_pct} label="vs prev period" />
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm text-gray-500 font-medium">Replies</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{outreach.replies_today ?? '—'}</p>
          <TrendIndicator value={trendData.replies?.change_pct} label="vs prev period" />
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm text-gray-500 font-medium">Meetings Booked</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{outreach.meetings_booked_today ?? '—'}</p>
          <TrendIndicator value={trendData.meetings?.change_pct} label="vs prev period" />
        </div>
      </div>

      {/* Attention bar */}
      {Object.values(attention).some(v => v > 0) && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-amber-800 mb-2">Attention Required</h3>
          <div className="flex flex-wrap gap-4 text-sm text-amber-700">
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
        {/* Emails & Replies over time */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-700">Outreach Over Time</h3>
            <select
              value={historyDays}
              onChange={(e) => setHistoryDays(Number(e.target.value))}
              className="text-xs border border-gray-200 rounded px-2 py-1 bg-white"
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
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="report_date" tick={{ fontSize: 10 }} />
                <YAxis />
                <Tooltip />
                <Area type="monotone" dataKey="emails_sent" stackId="1" stroke="#3b82f6" fill="#93c5fd" name="Sent" />
                <Area type="monotone" dataKey="replies_received" stackId="2" stroke="#22c55e" fill="#86efac" name="Replies" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-400 text-center py-12">Not enough history — reports build over time</p>
          )}
        </div>

        {/* Pipeline growth */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Pipeline Growth</h3>
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="report_date" tick={{ fontSize: 10 }} />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="pipeline_total" stroke="#6366f1" strokeWidth={2} dot={false} name="Total Pipeline" />
                <Line type="monotone" dataKey="new_companies" stroke="#f59e0b" strokeWidth={2} dot={false} name="New/day" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-400 text-center py-12">Not enough history — reports build over time</p>
          )}
        </div>
      </div>

      {/* Meetings and scoring trends */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Meetings Booked</h3>
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={history}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="report_date" tick={{ fontSize: 10 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="meetings_booked" fill="#a855f7" radius={[4, 4, 0, 0]} name="Meetings" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-400 text-center py-12">No meeting data yet</p>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-4">Average Score Trend</h3>
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="report_date" tick={{ fontSize: 10 }} />
                <YAxis domain={[0, 1]} />
                <Tooltip />
                <Line type="monotone" dataKey="avg_score" stroke="#f97316" strokeWidth={2} dot={false} name="Avg Score" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-gray-400 text-center py-12">No scoring data yet</p>
          )}
        </div>
      </div>

      {/* Today's top opportunities */}
      {topOpps.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Today's Top Discoveries</h3>
          <div className="divide-y divide-gray-100">
            {topOpps.slice(0, 5).map((opp, i) => (
              <div key={opp.id || i} className="flex items-center justify-between py-2.5">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400 w-4">{i + 1}.</span>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{opp.brand_name}</p>
                    <p className="text-xs text-gray-400">{opp.industry || opp.domain || ''}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-mono text-sm font-medium text-gray-900">{opp.composite_score?.toFixed(3)}</p>
                  <p className="text-xs text-gray-400 capitalize">{opp.priority_bucket?.replace(/_/g, ' ')}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Totals summary */}
      {trends?.totals && (
        <div className="bg-gray-50 rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Period Totals ({trends.period_days} days)</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-gray-500">Total Emails</p>
              <p className="text-lg font-bold text-gray-900">{trends.totals.total_emails}</p>
            </div>
            <div>
              <p className="text-gray-500">Total Replies</p>
              <p className="text-lg font-bold text-gray-900">{trends.totals.total_replies}</p>
            </div>
            <div>
              <p className="text-gray-500">Total Meetings</p>
              <p className="text-lg font-bold text-gray-900">{trends.totals.total_meetings}</p>
            </div>
            <div>
              <p className="text-gray-500">New Companies</p>
              <p className="text-lg font-bold text-gray-900">{trends.totals.total_new_companies}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
