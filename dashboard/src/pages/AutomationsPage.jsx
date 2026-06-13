import { useState, useEffect, useCallback } from 'react';
import { Zap, Plus, ArrowLeft, Play, Trash2, X, CheckCircle, XCircle, Loader2, Clock, Mail, Globe, Tag, Users, GitBranch, Bell, ChevronDown, ToggleLeft, ToggleRight } from 'lucide-react';
import {
  getWorkflows, getWorkflow, createWorkflow, updateWorkflow, deleteWorkflow,
  toggleWorkflow, getWorkflowRuns,
} from '../lib/api';

function Toast({ message, type, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, [onClose]);
  return (
    <div className="fixed top-6 right-6 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-lg text-sm font-medium"
      style={{
        background: type === 'success' ? 'linear-gradient(135deg, #d1fae5, #a7f3d0)' : 'linear-gradient(135deg, #fee2e2, #fecaca)',
        color: type === 'success' ? '#065f46' : '#991b1b',
        border: type === 'success' ? '1px solid rgba(6, 95, 70, 0.15)' : '1px solid rgba(153, 27, 27, 0.15)',
      }}>
      {type === 'success' ? <CheckCircle size={16} /> : <XCircle size={16} />}
      {message}
      <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100"><X size={14} /></button>
    </div>
  );
}

const TRIGGER_TYPES = [
  { value: 'lead_scored', label: 'Lead Scored' },
  { value: 'company_approved', label: 'Company Approved' },
  { value: 'stage_changed', label: 'Stage Changed' },
  { value: 'outreach_sent', label: 'Outreach Sent' },
  { value: 'email_opened', label: 'Email Opened' },
  { value: 'email_clicked', label: 'Email Clicked' },
  { value: 'contact_created', label: 'Contact Created' },
  { value: 'tag_added', label: 'Tag Added' },
  { value: 'webhook_received', label: 'Webhook Received' },
  { value: 'schedule', label: 'Schedule (Cron)' },
  { value: 'manual', label: 'Manual' },
];

const ACTION_TYPES = [
  { value: 'email_add_contact', label: 'Add Contact', icon: Users },
  { value: 'email_send', label: 'Send Email', icon: Mail },
  { value: 'email_add_tags', label: 'Add Tags', icon: Tag },
  { value: 'email_enroll_sequence', label: 'Enroll in Sequence', icon: GitBranch },
  { value: 'webhook_fire', label: 'Fire Webhook', icon: Globe },
  { value: 'update_stage', label: 'Update Stage', icon: ChevronDown },
  { value: 'send_notification', label: 'Send Notification', icon: Bell },
];

const TRIGGER_COLORS = {
  lead_scored: '#7c3aed',
  company_approved: '#059669',
  stage_changed: '#2b5797',
  outreach_sent: '#0891b2',
  email_opened: '#d97706',
  email_clicked: '#dc2626',
  contact_created: '#059669',
  tag_added: '#7c3aed',
  webhook_received: '#374151',
  schedule: '#92400e',
  manual: '#6b7a99',
};

function TriggerBadge({ type }) {
  const item = TRIGGER_TYPES.find(t => t.value === type);
  const color = TRIGGER_COLORS[type] || '#6b7a99';
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold"
      style={{ background: `${color}15`, color }}>
      <Zap size={10} />
      {item?.label || type}
    </span>
  );
}

function ActionCard({ action, index, onUpdate, onDelete }) {
  const actionType = ACTION_TYPES.find(a => a.value === action.type);
  const Icon = actionType?.icon || Zap;

  return (
    <div className="relative">
      {/* Connector */}
      {index > 0 && (
        <div className="absolute left-6 -top-3 w-0.5 h-3" style={{ background: 'rgba(91, 126, 194, 0.2)' }} />
      )}
      <div className="rounded-lg p-4 flex items-start gap-3"
        style={{
          background: 'rgba(238, 241, 248, 0.5)',
          border: '1px solid rgba(91, 126, 194, 0.1)',
        }}>
        <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: 'rgba(43, 87, 151, 0.1)' }}>
          <Icon size={16} style={{ color: '#2b5797' }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <select value={action.type || ''} onChange={e => onUpdate({ ...action, type: e.target.value })}
              className="text-sm font-medium outline-none px-2 py-1 rounded"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', color: '#1b2a4a', background: '#fff' }}>
              <option value="">Select action...</option>
              {ACTION_TYPES.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
            </select>
          </div>
          <textarea
            value={action.config || ''}
            onChange={e => onUpdate({ ...action, config: e.target.value })}
            rows={2}
            className="w-full px-3 py-2 rounded text-xs font-mono outline-none"
            style={{ border: '1px solid rgba(91, 126, 194, 0.15)', background: '#fff', color: '#374a6d', resize: 'vertical' }}
            placeholder='{"key": "value"}'
          />
          {action.type && action.config && (
            <p className="text-xs mt-1" style={{ color: '#9aa5bd' }}>
              {actionType?.label}: {(() => {
                try { const c = JSON.parse(action.config); return Object.entries(c).map(([k,v]) => `${k}=${v}`).join(', '); }
                catch { return action.config.substring(0, 50); }
              })()}
            </p>
          )}
        </div>
        <button onClick={onDelete} className="p-1 rounded hover:bg-red-50 transition-colors flex-shrink-0">
          <Trash2 size={14} style={{ color: '#991b1b' }} />
        </button>
      </div>
    </div>
  );
}

function WorkflowEditor({ workflow, onSave, onBack, onToast }) {
  const [form, setForm] = useState({
    name: '', description: '', trigger_type: 'manual', trigger_config: '',
    conditions: [], actions: [], enabled: false,
    ...workflow,
  });
  const [saving, setSaving] = useState(false);
  const [runs, setRuns] = useState([]);
  const [activeTab, setActiveTab] = useState('builder');

  useEffect(() => {
    if (workflow?.id) {
      getWorkflowRuns(workflow.id).then(d => setRuns(d.runs || d || [])).catch(() => {});
    }
  }, [workflow?.id]);

  function update(field, value) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  function addCondition() {
    update('conditions', [...(form.conditions || []), { field: '', operator: 'equals', value: '' }]);
  }

  function updateCondition(index, cond) {
    const updated = [...(form.conditions || [])];
    updated[index] = cond;
    update('conditions', updated);
  }

  function removeCondition(index) {
    update('conditions', (form.conditions || []).filter((_, i) => i !== index));
  }

  function addAction() {
    update('actions', [...(form.actions || []), { type: '', config: '' }]);
  }

  function updateAction(index, action) {
    const updated = [...(form.actions || [])];
    updated[index] = action;
    update('actions', updated);
  }

  function removeAction(index) {
    update('actions', (form.actions || []).filter((_, i) => i !== index));
  }

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(form);
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle() {
    if (workflow?.id) {
      try {
        await toggleWorkflow(workflow.id);
        update('enabled', !form.enabled);
        onToast({ message: form.enabled ? 'Workflow disabled' : 'Workflow enabled', type: 'success' });
      } catch (e) {
        onToast({ message: e.message || 'Failed to toggle', type: 'error' });
      }
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-2 text-sm font-medium" style={{ color: '#2b5797' }}>
          <ArrowLeft size={16} /> Back to Automations
        </button>
        <div className="flex items-center gap-2">
          {workflow?.id && (
            <button onClick={handleToggle}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
              style={{
                background: form.enabled ? 'linear-gradient(135deg, #fef3c7, #fde68a)' : 'linear-gradient(135deg, #d1fae5, #a7f3d0)',
                color: form.enabled ? '#92400e' : '#065f46',
              }}>
              {form.enabled ? <><ToggleRight size={14} /> Disable</> : <><ToggleLeft size={14} /> Enable</>}
            </button>
          )}
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>
            {saving ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
            Save Workflow
          </button>
        </div>
      </div>

      {/* Tabs */}
      {workflow?.id && (
        <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'rgba(238, 241, 248, 0.7)' }}>
          {['builder', 'history'].map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className="px-4 py-2 rounded-md text-sm font-medium capitalize transition-all"
              style={{
                background: activeTab === tab ? '#fff' : 'transparent',
                color: activeTab === tab ? '#1b2a4a' : '#6b7a99',
                boxShadow: activeTab === tab ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              }}>
              {tab === 'history' ? 'Run History' : 'Builder'}
            </button>
          ))}
        </div>
      )}

      {activeTab === 'builder' ? (
        <>
          {/* Workflow Info */}
          <div className="rounded-xl p-5"
            style={{
              background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
              border: '1px solid rgba(255, 255, 255, 0.6)', boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
            }}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Name</label>
                <input value={form.name || ''} onChange={e => update('name', e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                  placeholder="My Workflow" />
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Description</label>
                <input value={form.description || ''} onChange={e => update('description', e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                  placeholder="Describe what this workflow does..." />
              </div>
            </div>
          </div>

          {/* Trigger */}
          <div className="rounded-xl p-5"
            style={{
              background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
              border: '1px solid rgba(255, 255, 255, 0.6)', boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
            }}>
            <h3 className="text-sm font-bold mb-4 flex items-center gap-2" style={{ color: '#1b2a4a' }}>
              <Zap size={16} style={{ color: '#7c3aed' }} /> Trigger
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Trigger Type</label>
                <select value={form.trigger_type || 'manual'} onChange={e => update('trigger_type', e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}>
                  {TRIGGER_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Trigger Config (JSON)</label>
                <input value={form.trigger_config || ''} onChange={e => update('trigger_config', e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none font-mono"
                  style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                  placeholder='{"min_score": 0.7}' />
              </div>
            </div>
          </div>

          {/* Conditions */}
          <div className="rounded-xl p-5"
            style={{
              background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
              border: '1px solid rgba(255, 255, 255, 0.6)', boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
            }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold flex items-center gap-2" style={{ color: '#1b2a4a' }}>
                Conditions ({(form.conditions || []).length})
              </h3>
              <button onClick={addCondition}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold"
                style={{ background: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', color: '#1e40af' }}>
                <Plus size={12} /> Add Condition
              </button>
            </div>
            {(form.conditions || []).length === 0 ? (
              <p className="text-xs" style={{ color: '#9aa5bd' }}>No conditions — workflow will run on every trigger</p>
            ) : (
              <div className="space-y-3">
                {(form.conditions || []).map((cond, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <input value={cond.field || ''} onChange={e => updateCondition(i, { ...cond, field: e.target.value })}
                      className="flex-1 px-3 py-2 rounded-lg text-sm outline-none"
                      style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                      placeholder="field" />
                    <select value={cond.operator || 'equals'} onChange={e => updateCondition(i, { ...cond, operator: e.target.value })}
                      className="px-3 py-2 rounded-lg text-sm outline-none"
                      style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}>
                      <option value="equals">equals</option>
                      <option value="not_equals">not equals</option>
                      <option value="contains">contains</option>
                      <option value="greater_than">greater than</option>
                      <option value="less_than">less than</option>
                      <option value="exists">exists</option>
                    </select>
                    <input value={cond.value || ''} onChange={e => updateCondition(i, { ...cond, value: e.target.value })}
                      className="flex-1 px-3 py-2 rounded-lg text-sm outline-none"
                      style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                      placeholder="value" />
                    <button onClick={() => removeCondition(i)} className="p-1.5 rounded-lg hover:bg-red-50">
                      <Trash2 size={14} style={{ color: '#991b1b' }} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="rounded-xl p-5"
            style={{
              background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
              border: '1px solid rgba(255, 255, 255, 0.6)', boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
            }}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold flex items-center gap-2" style={{ color: '#1b2a4a' }}>
                Actions ({(form.actions || []).length})
              </h3>
              <button onClick={addAction}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold"
                style={{ background: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', color: '#1e40af' }}>
                <Plus size={12} /> Add Action
              </button>
            </div>
            {(form.actions || []).length === 0 ? (
              <p className="text-xs" style={{ color: '#9aa5bd' }}>No actions configured</p>
            ) : (
              <div className="space-y-3">
                {(form.actions || []).map((action, i) => (
                  <ActionCard
                    key={i}
                    action={action}
                    index={i}
                    onUpdate={a => updateAction(i, a)}
                    onDelete={() => removeAction(i)}
                  />
                ))}
              </div>
            )}
          </div>
        </>
      ) : (
        /* Run History */
        <div className="rounded-xl overflow-hidden"
          style={{
            background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
            border: '1px solid rgba(255, 255, 255, 0.6)', boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
          }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(91, 126, 194, 0.1)' }}>
                {['Status', 'Trigger Event', 'Timestamp', 'Duration', 'Actions'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {runs.map((run, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(91, 126, 194, 0.06)' }}>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold"
                      style={{
                        background: run.status === 'success' ? '#d1fae5' : run.status === 'failed' ? '#fee2e2' : '#fef3c7',
                        color: run.status === 'success' ? '#065f46' : run.status === 'failed' ? '#991b1b' : '#92400e',
                      }}>
                      {run.status}
                    </span>
                  </td>
                  <td className="px-4 py-3" style={{ color: '#374a6d' }}>{run.trigger_event || '-'}</td>
                  <td className="px-4 py-3" style={{ color: '#6b7a99' }}>
                    {run.created_at ? new Date(run.created_at).toLocaleString() : '-'}
                  </td>
                  <td className="px-4 py-3" style={{ color: '#6b7a99' }}>{run.duration_ms ? `${run.duration_ms}ms` : '-'}</td>
                  <td className="px-4 py-3" style={{ color: '#374a6d' }}>{run.actions_executed ?? 0}</td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center py-12">
                    <Clock size={32} className="mx-auto mb-2" style={{ color: '#d1d5db' }} />
                    <p className="text-sm" style={{ color: '#6b7a99' }}>No runs yet</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function AutomationsPage() {
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [view, setView] = useState('list');
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getWorkflows();
      setWorkflows(data.workflows || data || []);
    } catch (e) {
      setToast({ message: 'Failed to load workflows', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  async function handleCreate() {
    setSelectedWorkflow(null);
    setView('editor');
  }

  async function handleSave(form) {
    try {
      if (form.id) {
        await updateWorkflow(form.id, form);
        setToast({ message: 'Workflow updated', type: 'success' });
      } else {
        await createWorkflow(form);
        setToast({ message: 'Workflow created', type: 'success' });
      }
      setView('list');
      setSelectedWorkflow(null);
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to save workflow', type: 'error' });
    }
  }

  async function handleToggle(id) {
    try {
      await toggleWorkflow(id);
      setToast({ message: 'Workflow toggled', type: 'success' });
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to toggle', type: 'error' });
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('Delete this workflow?')) return;
    try {
      await deleteWorkflow(id);
      setToast({ message: 'Workflow deleted', type: 'success' });
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to delete', type: 'error' });
    }
  }

  if (loading && workflows.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  if (view === 'editor') {
    return (
      <div>
        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
        <WorkflowEditor
          workflow={selectedWorkflow || {}}
          onSave={handleSave}
          onBack={() => { setView('list'); setSelectedWorkflow(null); }}
          onToast={setToast}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Automations</h2>
          <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Build automated workflows with triggers, conditions, and actions</p>
        </div>
        <button onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-md"
          style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>
          <Plus size={16} /> Create Workflow
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {workflows.map(w => (
          <div key={w.id} className="rounded-xl p-5 transition-all duration-200 hover:shadow-lg cursor-pointer"
            style={{
              background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
              border: '1px solid rgba(255, 255, 255, 0.6)',
              boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
              borderLeft: w.enabled ? '3px solid #22c55e' : '3px solid transparent',
            }}
            onClick={() => { setSelectedWorkflow(w); setView('editor'); }}>
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(124, 58, 237, 0.1)' }}>
                  <Zap size={20} style={{ color: '#7c3aed' }} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold" style={{ color: '#1b2a4a' }}>{w.name}</h3>
                  {w.description && <p className="text-xs mt-0.5" style={{ color: '#6b7a99' }}>{w.description}</p>}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 mb-3">
              <TriggerBadge type={w.trigger_type} />
              <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                style={{
                  background: w.enabled ? '#d1fae5' : '#e5e7eb',
                  color: w.enabled ? '#065f46' : '#374151',
                }}>
                {w.enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>

            <div className="flex items-center gap-4 text-xs" style={{ color: '#9aa5bd' }}>
              {w.last_triggered_at && <span>Last: {new Date(w.last_triggered_at).toLocaleDateString()}</span>}
              <span>Runs: {w.run_count ?? 0}</span>
            </div>

            <div className="flex items-center gap-1 mt-3 pt-3" style={{ borderTop: '1px solid rgba(91, 126, 194, 0.1)' }}>
              <button onClick={e => { e.stopPropagation(); handleToggle(w.id); }}
                className="p-1.5 rounded-lg hover:bg-green-50 transition-colors" title="Toggle">
                {w.enabled ? <ToggleRight size={14} style={{ color: '#059669' }} /> : <ToggleLeft size={14} style={{ color: '#9ca3af' }} />}
              </button>
              <button onClick={e => { e.stopPropagation(); handleDelete(w.id); }}
                className="p-1.5 rounded-lg hover:bg-red-50 transition-colors ml-auto" title="Delete">
                <Trash2 size={14} style={{ color: '#991b1b' }} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {workflows.length === 0 && (
        <div className="text-center py-16">
          <Zap size={40} className="mx-auto mb-3" style={{ color: '#d1d5db' }} />
          <p className="text-sm font-medium" style={{ color: '#6b7a99' }}>No automations yet</p>
          <p className="text-xs mt-1" style={{ color: '#9aa5bd' }}>Create your first workflow to automate repetitive tasks</p>
        </div>
      )}
    </div>
  );
}
