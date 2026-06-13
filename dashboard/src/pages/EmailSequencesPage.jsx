import { useState, useEffect, useCallback } from 'react';
import { GitBranch, Plus, ArrowLeft, Play, Pause, Trash2, X, CheckCircle, XCircle, Loader2, Clock, Mail, Filter, Zap, ChevronDown, ChevronUp, Users } from 'lucide-react';
import {
  getEmailSequences, getEmailSequence, createEmailSequence, updateEmailSequence,
  deleteEmailSequence, activateSequence, pauseSequence,
  getSequenceSteps, createSequenceStep, updateSequenceStep, deleteSequenceStep,
  getSequenceEnrollments, enrollContacts,
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

const STATUS_STYLES = {
  draft: { bg: '#e5e7eb', color: '#374151' },
  active: { bg: '#d1fae5', color: '#065f46' },
  paused: { bg: '#fef3c7', color: '#92400e' },
};

function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.draft;
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize"
      style={{ background: s.bg, color: s.color }}>
      {status}
    </span>
  );
}

const STEP_ICONS = {
  email: Mail,
  delay: Clock,
  condition: Filter,
  action: Zap,
};

function StepCard({ step, index, onEdit, onDelete, expanded, onToggle }) {
  const Icon = STEP_ICONS[step.type] || Zap;
  const bgColor = step.type === 'email' ? '#dbeafe' : step.type === 'delay' ? '#fef3c7' : step.type === 'condition' ? '#ede9fe' : '#d1fae5';
  const iconColor = step.type === 'email' ? '#1e40af' : step.type === 'delay' ? '#92400e' : step.type === 'condition' ? '#6d28d9' : '#065f46';

  return (
    <div className="relative">
      {/* Connector line */}
      {index > 0 && (
        <div className="absolute left-6 -top-4 w-0.5 h-4" style={{ background: 'rgba(91, 126, 194, 0.2)' }} />
      )}
      <div className="rounded-xl p-4 transition-all hover:shadow-md cursor-pointer"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
          borderLeft: `3px solid ${iconColor}`,
        }}
        onClick={onToggle}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: bgColor }}>
              <Icon size={16} style={{ color: iconColor }} />
            </div>
            <div>
              <p className="text-sm font-semibold capitalize" style={{ color: '#1b2a4a' }}>
                {step.type === 'email' ? (step.subject || 'Email Step') :
                 step.type === 'delay' ? `Wait ${step.delay_days || 0}d ${step.delay_hours || 0}h` :
                 step.type === 'condition' ? (step.condition_description || 'Condition') :
                 (step.action_type || 'Action')}
              </p>
              <div className="flex items-center gap-3 text-xs mt-0.5" style={{ color: '#9aa5bd' }}>
                <span>Step {index + 1}</span>
                {step.type === 'email' && step.sent_count !== undefined && (
                  <>
                    <span>Sent: {step.sent_count}</span>
                    <span>Opens: {step.open_count || 0}</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={e => { e.stopPropagation(); onDelete(step.id); }}
              className="p-1.5 rounded-lg hover:bg-red-50 transition-colors">
              <Trash2 size={14} style={{ color: '#991b1b' }} />
            </button>
            {expanded ? <ChevronUp size={16} style={{ color: '#9aa5bd' }} /> : <ChevronDown size={16} style={{ color: '#9aa5bd' }} />}
          </div>
        </div>
        {step.type === 'email' && step.preview_text && !expanded && (
          <p className="text-xs mt-2 ml-11 truncate" style={{ color: '#6b7a99' }}>{step.preview_text}</p>
        )}
      </div>
    </div>
  );
}

function StepEditor({ step, onSave, onCancel }) {
  const [form, setForm] = useState({
    type: 'email',
    subject: '', html_content: '', preview_text: '',
    delay_days: 1, delay_hours: 0,
    condition_description: '', condition_field: '', condition_operator: 'equals', condition_value: '',
    action_type: '', action_config: '',
    ...step,
  });
  const [saving, setSaving] = useState(false);

  function update(field, value) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(form);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-xl p-5 mt-2 space-y-4"
      style={{
        background: 'rgba(238, 241, 248, 0.7)',
        border: '1px solid rgba(91, 126, 194, 0.15)',
      }}>
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Step Type</label>
        <select value={form.type} onChange={e => update('type', e.target.value)}
          className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
          style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: '#fff', color: '#1b2a4a' }}>
          <option value="email">Email</option>
          <option value="delay">Delay</option>
          <option value="condition">Condition</option>
          <option value="action">Action</option>
        </select>
      </div>

      {form.type === 'email' && (
        <>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Subject</label>
            <input value={form.subject || ''} onChange={e => update('subject', e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: '#fff', color: '#1b2a4a' }}
              placeholder="Follow up on our conversation" />
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>HTML Content</label>
            <textarea value={form.html_content || ''} onChange={e => update('html_content', e.target.value)}
              rows={6}
              className="w-full px-4 py-3 rounded-lg text-sm outline-none font-mono"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: '#fff', color: '#1b2a4a', resize: 'vertical' }}
              placeholder="<p>Hello {{first_name}},</p>" />
          </div>
        </>
      )}

      {form.type === 'delay' && (
        <div className="flex gap-4">
          <div className="flex-1">
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Days</label>
            <input type="number" min="0" value={form.delay_days ?? 1} onChange={e => update('delay_days', parseInt(e.target.value) || 0)}
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: '#fff', color: '#1b2a4a' }} />
          </div>
          <div className="flex-1">
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Hours</label>
            <input type="number" min="0" max="23" value={form.delay_hours ?? 0} onChange={e => update('delay_hours', parseInt(e.target.value) || 0)}
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: '#fff', color: '#1b2a4a' }} />
          </div>
        </div>
      )}

      {form.type === 'condition' && (
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Condition Description</label>
          <input value={form.condition_description || ''} onChange={e => update('condition_description', e.target.value)}
            className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
            style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: '#fff', color: '#1b2a4a' }}
            placeholder="If contact opened previous email" />
        </div>
      )}

      {form.type === 'action' && (
        <>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Action Type</label>
            <select value={form.action_type || ''} onChange={e => update('action_type', e.target.value)}
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: '#fff', color: '#1b2a4a' }}>
              <option value="">Select action...</option>
              <option value="add_tag">Add Tag</option>
              <option value="remove_tag">Remove Tag</option>
              <option value="move_to_list">Move to List</option>
              <option value="webhook">Fire Webhook</option>
              <option value="notify">Send Notification</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Config (JSON)</label>
            <textarea value={form.action_config || ''} onChange={e => update('action_config', e.target.value)}
              rows={3}
              className="w-full px-4 py-3 rounded-lg text-sm outline-none font-mono"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: '#fff', color: '#1b2a4a' }}
              placeholder='{"tag": "engaged"}' />
          </div>
        </>
      )}

      <div className="flex justify-end gap-2 pt-2">
        <button onClick={onCancel} className="px-4 py-2 rounded-lg text-sm font-medium" style={{ color: '#6b7a99' }}>Cancel</button>
        <button onClick={handleSave} disabled={saving}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white disabled:opacity-50"
          style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>
          {saving ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} />}
          Save Step
        </button>
      </div>
    </div>
  );
}

function SequenceBuilder({ sequence, onBack, onToast }) {
  const [seqData, setSeqData] = useState(sequence);
  const [steps, setSteps] = useState([]);
  const [enrollments, setEnrollments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedStep, setExpandedStep] = useState(null);
  const [addingStep, setAddingStep] = useState(null); // index to insert after, or 'end'
  const [editingName, setEditingName] = useState(false);
  const [nameForm, setNameForm] = useState({ name: sequence.name || '', description: sequence.description || '', trigger_type: sequence.trigger_type || 'manual' });

  useEffect(() => { loadSteps(); }, []);

  async function loadSteps() {
    setLoading(true);
    try {
      const [stepsData, enrollData] = await Promise.all([
        getSequenceSteps(sequence.id),
        getSequenceEnrollments(sequence.id).catch(() => ({ enrollments: [] })),
      ]);
      setSteps(stepsData.steps || stepsData || []);
      setEnrollments(enrollData.enrollments || enrollData || []);
    } catch (e) {
      onToast({ message: 'Failed to load sequence steps', type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleStatus() {
    try {
      if (seqData.status === 'active') {
        await pauseSequence(sequence.id);
        setSeqData(prev => ({ ...prev, status: 'paused' }));
        onToast({ message: 'Sequence paused', type: 'success' });
      } else {
        await activateSequence(sequence.id);
        setSeqData(prev => ({ ...prev, status: 'active' }));
        onToast({ message: 'Sequence activated', type: 'success' });
      }
    } catch (e) {
      onToast({ message: e.message || 'Failed to update status', type: 'error' });
    }
  }

  async function handleSaveName() {
    try {
      await updateEmailSequence(sequence.id, nameForm);
      setSeqData(prev => ({ ...prev, ...nameForm }));
      setEditingName(false);
      onToast({ message: 'Sequence updated', type: 'success' });
    } catch (e) {
      onToast({ message: e.message || 'Failed to update', type: 'error' });
    }
  }

  async function handleSaveStep(form) {
    try {
      if (form.id) {
        await updateSequenceStep(sequence.id, form.id, form);
      } else {
        await createSequenceStep(sequence.id, { ...form, position: addingStep === 'end' ? steps.length : addingStep });
      }
      setAddingStep(null);
      setExpandedStep(null);
      onToast({ message: 'Step saved', type: 'success' });
      loadSteps();
    } catch (e) {
      onToast({ message: e.message || 'Failed to save step', type: 'error' });
    }
  }

  async function handleDeleteStep(stepId) {
    if (!window.confirm('Delete this step?')) return;
    try {
      await deleteSequenceStep(sequence.id, stepId);
      onToast({ message: 'Step deleted', type: 'success' });
      loadSteps();
    } catch (e) {
      onToast({ message: e.message || 'Failed to delete step', type: 'error' });
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-2 text-sm font-medium" style={{ color: '#2b5797' }}>
          <ArrowLeft size={16} /> Back to Sequences
        </button>
        <div className="flex items-center gap-2">
          <StatusBadge status={seqData.status || 'draft'} />
          <button onClick={handleToggleStatus}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
            style={{
              background: seqData.status === 'active'
                ? 'linear-gradient(135deg, #fef3c7, #fde68a)'
                : 'linear-gradient(135deg, #d1fae5, #a7f3d0)',
              color: seqData.status === 'active' ? '#92400e' : '#065f46',
            }}>
            {seqData.status === 'active' ? <><Pause size={14} /> Pause</> : <><Play size={14} /> Activate</>}
          </button>
        </div>
      </div>

      {/* Sequence Info */}
      <div className="rounded-xl p-5"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)', boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
        }}>
        {editingName ? (
          <div className="space-y-3">
            <input value={nameForm.name} onChange={e => setNameForm(p => ({ ...p, name: e.target.value }))}
              className="w-full px-4 py-2.5 rounded-lg text-sm font-semibold outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', color: '#1b2a4a' }} />
            <input value={nameForm.description} onChange={e => setNameForm(p => ({ ...p, description: e.target.value }))}
              className="w-full px-4 py-2 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', color: '#6b7a99' }}
              placeholder="Description..." />
            <div className="flex gap-2">
              <select value={nameForm.trigger_type} onChange={e => setNameForm(p => ({ ...p, trigger_type: e.target.value }))}
                className="px-3 py-2 rounded-lg text-sm outline-none"
                style={{ border: '1px solid rgba(91, 126, 194, 0.2)', color: '#1b2a4a' }}>
                <option value="manual">Manual</option>
                <option value="tag_added">Tag Added</option>
                <option value="list_joined">List Joined</option>
                <option value="form_submitted">Form Submitted</option>
              </select>
              <button onClick={handleSaveName} className="px-3 py-2 rounded-lg text-xs font-semibold text-white"
                style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>Save</button>
              <button onClick={() => setEditingName(false)} className="px-3 py-2 rounded-lg text-xs font-medium" style={{ color: '#6b7a99' }}>Cancel</button>
            </div>
          </div>
        ) : (
          <div className="flex items-start justify-between cursor-pointer" onClick={() => setEditingName(true)}>
            <div>
              <h2 className="text-lg font-bold" style={{ color: '#1b2a4a' }}>{seqData.name || 'Untitled Sequence'}</h2>
              {seqData.description && <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>{seqData.description}</p>}
              <p className="text-xs mt-1" style={{ color: '#9aa5bd' }}>Trigger: {seqData.trigger_type || 'manual'}</p>
            </div>
          </div>
        )}
      </div>

      {/* Steps Timeline */}
      <div>
        <h3 className="text-sm font-bold mb-4" style={{ color: '#1b2a4a' }}>Steps ({steps.length})</h3>
        <div className="space-y-4">
          {steps.map((step, i) => (
            <div key={step.id}>
              <StepCard
                step={step}
                index={i}
                expanded={expandedStep === step.id}
                onToggle={() => setExpandedStep(expandedStep === step.id ? null : step.id)}
                onEdit={() => setExpandedStep(step.id)}
                onDelete={handleDeleteStep}
              />
              {expandedStep === step.id && (
                <StepEditor step={step} onSave={handleSaveStep} onCancel={() => setExpandedStep(null)} />
              )}
              {/* Add step button between steps */}
              <div className="flex justify-center py-1">
                <button onClick={() => setAddingStep(i + 1)}
                  className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium opacity-40 hover:opacity-100 transition-opacity"
                  style={{ color: '#2b5797' }}>
                  <Plus size={12} /> Add Step
                </button>
              </div>
              {addingStep === i + 1 && (
                <StepEditor step={{}} onSave={handleSaveStep} onCancel={() => setAddingStep(null)} />
              )}
            </div>
          ))}
          {steps.length === 0 && (
            <div className="text-center py-8">
              <GitBranch size={32} className="mx-auto mb-2" style={{ color: '#d1d5db' }} />
              <p className="text-sm" style={{ color: '#6b7a99' }}>No steps yet. Add your first step below.</p>
            </div>
          )}
          {addingStep === 'end' && (
            <StepEditor step={{}} onSave={handleSaveStep} onCancel={() => setAddingStep(null)} />
          )}
          <button onClick={() => setAddingStep('end')}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold transition-all hover:shadow-md"
            style={{ border: '2px dashed rgba(91, 126, 194, 0.3)', color: '#2b5797' }}>
            <Plus size={16} /> Add Step
          </button>
        </div>
      </div>

      {/* Enrollments */}
      <div className="rounded-xl p-5"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)', boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
        }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold" style={{ color: '#1b2a4a' }}>Enrolled Contacts ({enrollments.length})</h3>
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
            style={{ background: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', color: '#1e40af' }}>
            <Users size={14} /> Enroll Contacts
          </button>
        </div>
        {enrollments.length > 0 ? (
          <div className="text-xs space-y-1" style={{ color: '#6b7a99' }}>
            {enrollments.slice(0, 10).map((e, i) => (
              <div key={i} className="flex justify-between py-1" style={{ borderBottom: '1px solid rgba(91, 126, 194, 0.06)' }}>
                <span style={{ color: '#374a6d' }}>{e.contact_email || e.contact_id}</span>
                <span>Step {e.current_step || 1} - {e.status || 'active'}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs" style={{ color: '#9aa5bd' }}>No contacts enrolled yet</p>
        )}
      </div>
    </div>
  );
}

export default function EmailSequencesPage() {
  const [sequences, setSequences] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [view, setView] = useState('list');
  const [selectedSequence, setSelectedSequence] = useState(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getEmailSequences();
      setSequences(data.sequences || []);
    } catch (e) {
      setToast({ message: 'Failed to load sequences', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  async function handleCreate() {
    try {
      const seq = await createEmailSequence({ name: 'New Sequence', status: 'draft', trigger_type: 'manual' });
      setSelectedSequence(seq);
      setView('builder');
    } catch (e) {
      setToast({ message: e.message || 'Failed to create sequence', type: 'error' });
    }
  }

  async function handleDelete(id) {
    if (!window.confirm('Delete this sequence?')) return;
    try {
      await deleteEmailSequence(id);
      setToast({ message: 'Sequence deleted', type: 'success' });
      loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to delete', type: 'error' });
    }
  }

  if (loading && sequences.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  if (view === 'builder' && selectedSequence) {
    return (
      <div>
        {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
        <SequenceBuilder
          sequence={selectedSequence}
          onBack={() => { setView('list'); setSelectedSequence(null); loadData(); }}
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
          <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Sequences</h2>
          <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Build drip email sequences and automated flows</p>
        </div>
        <button onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-md"
          style={{ background: 'linear-gradient(135deg, #1e3a5f, #2b5797)' }}>
          <Plus size={16} /> Create Sequence
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {sequences.map(seq => (
          <div key={seq.id} className="rounded-xl p-5 transition-all duration-200 hover:shadow-lg cursor-pointer"
            style={{
              background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
              border: '1px solid rgba(255, 255, 255, 0.6)',
              boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
            }}
            onClick={() => { setSelectedSequence(seq); setView('builder'); }}>
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'rgba(43, 87, 151, 0.1)' }}>
                  <GitBranch size={20} style={{ color: '#2b5797' }} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold" style={{ color: '#1b2a4a' }}>{seq.name}</h3>
                  {seq.description && <p className="text-xs mt-0.5" style={{ color: '#6b7a99' }}>{seq.description}</p>}
                </div>
              </div>
              <StatusBadge status={seq.status || 'draft'} />
            </div>
            <div className="flex items-center gap-4 text-xs" style={{ color: '#9aa5bd' }}>
              <span>Trigger: {seq.trigger_type || 'manual'}</span>
              <span>{seq.step_count ?? 0} steps</span>
              <span>{seq.enrolled_count ?? 0} enrolled</span>
            </div>
            <div className="flex items-center gap-1 mt-3 pt-3" style={{ borderTop: '1px solid rgba(91, 126, 194, 0.1)' }}>
              <button onClick={e => { e.stopPropagation(); handleDelete(seq.id); }}
                className="p-1.5 rounded-lg hover:bg-red-50 transition-colors" title="Delete">
                <Trash2 size={14} style={{ color: '#991b1b' }} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {sequences.length === 0 && (
        <div className="text-center py-16">
          <GitBranch size={40} className="mx-auto mb-3" style={{ color: '#d1d5db' }} />
          <p className="text-sm font-medium" style={{ color: '#6b7a99' }}>No sequences yet</p>
          <p className="text-xs mt-1" style={{ color: '#9aa5bd' }}>Create your first drip sequence to automate email flows</p>
        </div>
      )}
    </div>
  );
}
