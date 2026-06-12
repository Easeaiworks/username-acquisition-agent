import { useState, useEffect } from 'react';
import { FileText, Plus, Copy, Trash2, Eye, Edit3, X, CheckCircle, XCircle, Loader2, Tag } from 'lucide-react';
import { getTemplates, createTemplate, updateTemplate, deleteTemplate, duplicateTemplate, previewTemplate } from '../lib/api';

const TEMPLATE_TYPES = ['initial', 'follow_up', 'breakup', 'reply', 'custom'];

const MERGE_TAGS = [
  { tag: '{{first_name}}', desc: 'Contact first name' },
  { tag: '{{last_name}}', desc: 'Contact last name' },
  { tag: '{{full_name}}', desc: 'Contact full name' },
  { tag: '{{company}}', desc: 'Company name' },
  { tag: '{{title}}', desc: 'Job title' },
  { tag: '{{industry}}', desc: 'Company industry' },
  { tag: '{{email}}', desc: 'Contact email' },
  { tag: '{{website}}', desc: 'Company website' },
  { tag: '{{city}}', desc: 'Company city' },
  { tag: '{{sender_name}}', desc: 'Your name' },
  { tag: '{{sender_company}}', desc: 'Your company' },
  { tag: '{{unsubscribe_link}}', desc: 'Unsubscribe URL' },
];

const TYPE_COLORS = {
  initial: { bg: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', color: '#1e40af' },
  follow_up: { bg: 'linear-gradient(135deg, #fef3c7, #fde68a)', color: '#92400e' },
  breakup: { bg: 'linear-gradient(135deg, #fee2e2, #fecaca)', color: '#991b1b' },
  reply: { bg: 'linear-gradient(135deg, #d1fae5, #a7f3d0)', color: '#065f46' },
  custom: { bg: 'linear-gradient(135deg, #ede9fe, #ddd6fe)', color: '#5b21b6' },
};

function Toast({ message, type, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, [onClose]);

  return (
    <div
      className="fixed top-6 right-6 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-lg text-sm font-medium"
      style={{
        background: type === 'success' ? 'linear-gradient(135deg, #d1fae5, #a7f3d0)' : 'linear-gradient(135deg, #fee2e2, #fecaca)',
        color: type === 'success' ? '#065f46' : '#991b1b',
        border: type === 'success' ? '1px solid rgba(6, 95, 70, 0.15)' : '1px solid rgba(153, 27, 27, 0.15)',
      }}
    >
      {type === 'success' ? <CheckCircle size={16} /> : <XCircle size={16} />}
      {message}
      <button onClick={onClose} className="ml-2 opacity-60 hover:opacity-100"><X size={14} /></button>
    </div>
  );
}

function TemplateFormModal({ template, onClose, onSave }) {
  const isEdit = !!template?.id;
  const [form, setForm] = useState({
    name: template?.name || '',
    subject: template?.subject || '',
    body: template?.body || '',
    type: template?.type || 'initial',
    sequence_step: template?.sequence_step || 1,
    is_active: template?.is_active !== undefined ? template.is_active : true,
  });
  const [saving, setSaving] = useState(false);
  const [showMergeTags, setShowMergeTags] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave(form);
    } finally {
      setSaving(false);
    }
  }

  function insertTag(tag) {
    setForm(prev => ({ ...prev, body: prev.body + tag }));
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(15, 26, 46, 0.5)', backdropFilter: 'blur(4px)' }}>
      <div
        className="w-full max-w-2xl rounded-2xl p-6 max-h-[90vh] overflow-y-auto"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.98) 0%, rgba(243,245,252,0.95) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 24px 64px rgba(15, 26, 46, 0.2)',
        }}
      >
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold" style={{ color: '#1b2a4a' }}>
            {isEdit ? 'Edit Template' : 'Create Template'}
          </h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100"><X size={20} style={{ color: '#6b7a99' }} /></button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>
                Name <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <input
                type="text"
                required
                value={form.name}
                onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
                placeholder="Template name"
                className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                onFocus={e => { e.target.style.borderColor = '#5b7ec2'; }}
                onBlur={e => { e.target.style.borderColor = 'rgba(91, 126, 194, 0.2)'; }}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Type</label>
                <select
                  value={form.type}
                  onChange={e => setForm(prev => ({ ...prev, type: e.target.value }))}
                  className="w-full px-3 py-2.5 rounded-lg text-sm outline-none capitalize"
                  style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                >
                  {TEMPLATE_TYPES.map(t => (
                    <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>Step</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={form.sequence_step}
                  onChange={e => setForm(prev => ({ ...prev, sequence_step: parseInt(e.target.value) || 1 }))}
                  className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
                  style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
                />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-1.5" style={{ color: '#6b7a99' }}>
              Subject <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input
              type="text"
              required
              value={form.subject}
              onChange={e => setForm(prev => ({ ...prev, subject: e.target.value }))}
              placeholder="Email subject line (supports merge tags)"
              className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
              style={{ border: '1px solid rgba(91, 126, 194, 0.2)', background: 'rgba(238, 241, 248, 0.5)', color: '#1b2a4a' }}
              onFocus={e => { e.target.style.borderColor = '#5b7ec2'; }}
              onBlur={e => { e.target.style.borderColor = 'rgba(91, 126, 194, 0.2)'; }}
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>
                Body <span style={{ color: '#ef4444' }}>*</span>
              </label>
              <button
                type="button"
                onClick={() => setShowMergeTags(!showMergeTags)}
                className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-md transition-colors"
                style={{ color: '#5b7ec2', background: showMergeTags ? 'rgba(91, 126, 194, 0.1)' : 'transparent' }}
              >
                <Tag size={12} />
                Merge Tags
              </button>
            </div>

            {showMergeTags && (
              <div className="mb-2 flex flex-wrap gap-1.5 p-3 rounded-lg" style={{ background: 'rgba(91, 126, 194, 0.05)', border: '1px solid rgba(91, 126, 194, 0.1)' }}>
                {MERGE_TAGS.map(({ tag, desc }) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => insertTag(tag)}
                    className="px-2 py-1 rounded text-xs font-mono transition-all hover:shadow-sm"
                    style={{ background: 'white', border: '1px solid rgba(91, 126, 194, 0.15)', color: '#5b7ec2' }}
                    title={desc}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            )}

            <textarea
              required
              value={form.body}
              onChange={e => setForm(prev => ({ ...prev, body: e.target.value }))}
              placeholder="Email body (supports merge tags like {{first_name}})"
              rows={10}
              className="w-full px-4 py-3 rounded-lg text-sm outline-none font-mono resize-y"
              style={{
                border: '1px solid rgba(91, 126, 194, 0.2)',
                background: 'rgba(238, 241, 248, 0.5)',
                color: '#1b2a4a',
                lineHeight: 1.6,
              }}
              onFocus={e => { e.target.style.borderColor = '#5b7ec2'; }}
              onBlur={e => { e.target.style.borderColor = 'rgba(91, 126, 194, 0.2)'; }}
            />
          </div>

          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={e => setForm(prev => ({ ...prev, is_active: e.target.checked }))}
                className="rounded"
              />
              <span className="text-sm" style={{ color: '#374a6d' }}>Active</span>
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-4" style={{ borderTop: '1px solid rgba(91, 126, 194, 0.1)' }}>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm font-medium transition-colors hover:bg-gray-100"
              style={{ color: '#6b7a99' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-lg disabled:opacity-50"
              style={{ background: 'linear-gradient(135deg, #3a5289, #5b7ec2)' }}
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />}
              {isEdit ? 'Update Template' : 'Create Template'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function PreviewModal({ template, onClose }) {
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await previewTemplate({
          subject: template.subject,
          body: template.body,
          sample_data: {
            first_name: 'Alex',
            last_name: 'Johnson',
            full_name: 'Alex Johnson',
            company: 'TechCorp',
            title: 'VP of Engineering',
            industry: 'Technology',
            email: 'alex@techcorp.com',
            website: 'techcorp.com',
            city: 'San Francisco',
            sender_name: 'Sean',
            sender_company: 'Username Acquisition',
            unsubscribe_link: '#unsubscribe',
          },
        });
        setPreview(data);
      } catch (e) {
        // Fallback: simple local preview
        let subj = template.subject || '';
        let body = template.body || '';
        const sampleData = {
          first_name: 'Alex', last_name: 'Johnson', full_name: 'Alex Johnson',
          company: 'TechCorp', title: 'VP of Engineering', industry: 'Technology',
          email: 'alex@techcorp.com', website: 'techcorp.com', city: 'San Francisco',
          sender_name: 'Sean', sender_company: 'Username Acquisition', unsubscribe_link: '#',
        };
        Object.entries(sampleData).forEach(([key, val]) => {
          const re = new RegExp(`\\{\\{${key}\\}\\}`, 'g');
          subj = subj.replace(re, val);
          body = body.replace(re, val);
        });
        setPreview({ subject: subj, body });
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [template]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: 'rgba(15, 26, 46, 0.5)', backdropFilter: 'blur(4px)' }}>
      <div
        className="w-full max-w-xl rounded-2xl p-6 max-h-[80vh] overflow-y-auto"
        style={{
          background: 'linear-gradient(145deg, rgba(255,255,255,0.98) 0%, rgba(243,245,252,0.95) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.6)',
          boxShadow: '0 24px 64px rgba(15, 26, 46, 0.2)',
        }}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold" style={{ color: '#1b2a4a' }}>Template Preview</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100"><X size={20} style={{ color: '#6b7a99' }} /></button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 size={24} className="animate-spin" style={{ color: '#5b7ec2' }} />
          </div>
        ) : (
          <div className="space-y-4">
            <div className="p-4 rounded-lg" style={{ background: 'rgba(238, 241, 248, 0.7)', border: '1px solid rgba(91, 126, 194, 0.1)' }}>
              <p className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: '#6b7a99' }}>Subject</p>
              <p className="text-sm font-medium" style={{ color: '#1b2a4a' }}>{preview?.subject || template.subject}</p>
            </div>
            <div className="p-4 rounded-lg" style={{ background: 'rgba(238, 241, 248, 0.7)', border: '1px solid rgba(91, 126, 194, 0.1)' }}>
              <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: '#6b7a99' }}>Body</p>
              <div className="text-sm whitespace-pre-wrap" style={{ color: '#374a6d', lineHeight: 1.7 }}>
                {preview?.body || template.body}
              </div>
            </div>
            <p className="text-xs text-center" style={{ color: '#9aa5bd' }}>
              Preview uses sample data (Alex Johnson at TechCorp)
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AdminTemplatesPage() {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [previewingTemplate, setPreviewingTemplate] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);

  useEffect(() => { loadData(); }, []);

  async function loadData() {
    try {
      const data = await getTemplates();
      setTemplates(Array.isArray(data) ? data : data.templates || []);
    } catch (e) {
      console.error('Failed to load templates:', e);
      setToast({ message: 'Failed to load templates', type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(formData) {
    try {
      await createTemplate(formData);
      setToast({ message: 'Template created', type: 'success' });
      setShowCreateForm(false);
      await loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to create template', type: 'error' });
    }
  }

  async function handleUpdate(formData) {
    try {
      await updateTemplate(editingTemplate.id, formData);
      setToast({ message: 'Template updated', type: 'success' });
      setEditingTemplate(null);
      await loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to update template', type: 'error' });
    }
  }

  async function handleDuplicate(id) {
    try {
      await duplicateTemplate(id);
      setToast({ message: 'Template duplicated', type: 'success' });
      await loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to duplicate template', type: 'error' });
    }
  }

  async function handleDelete(id, name) {
    if (!window.confirm(`Delete template "${name}"? This cannot be undone.`)) return;
    try {
      await deleteTemplate(id);
      setToast({ message: 'Template deleted', type: 'success' });
      await loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to delete template', type: 'error' });
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  // Group templates by sequence step
  const grouped = {};
  templates.forEach(tmpl => {
    const step = tmpl.sequence_step || 1;
    if (!grouped[step]) grouped[step] = [];
    grouped[step].push(tmpl);
  });
  const sortedSteps = Object.keys(grouped).sort((a, b) => Number(a) - Number(b));

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>Email Templates</h2>
          <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Manage outreach email templates and sequences</p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-lg"
          style={{ background: 'linear-gradient(135deg, #3a5289, #5b7ec2)' }}
        >
          <Plus size={16} />
          Create Template
        </button>
      </div>

      {/* Merge Tag Quick Reference */}
      <div className="rounded-xl p-4" style={{ background: 'rgba(91, 126, 194, 0.05)', border: '1px solid rgba(91, 126, 194, 0.1)' }}>
        <p className="text-xs font-semibold uppercase tracking-wider mb-2 flex items-center gap-1.5" style={{ color: '#5b7ec2' }}>
          <Tag size={12} /> Available Merge Tags
        </p>
        <div className="flex flex-wrap gap-1.5">
          {MERGE_TAGS.map(({ tag, desc }) => (
            <span
              key={tag}
              className="px-2 py-0.5 rounded text-xs font-mono"
              style={{ background: 'white', border: '1px solid rgba(91, 126, 194, 0.12)', color: '#5b7ec2' }}
              title={desc}
            >
              {tag}
            </span>
          ))}
        </div>
      </div>

      {/* Templates grouped by step */}
      {sortedSteps.length === 0 ? (
        <div className="text-center py-16">
          <FileText size={40} style={{ color: '#d1d5db' }} className="mx-auto mb-3" />
          <p className="text-sm font-medium" style={{ color: '#6b7a99' }}>No templates yet</p>
          <p className="text-xs mt-1" style={{ color: '#9aa5bd' }}>Create your first email template to get started</p>
        </div>
      ) : (
        sortedSteps.map(step => (
          <div key={step}>
            <h3 className="text-sm font-semibold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: '#374a6d' }}>
              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold text-white" style={{ background: 'linear-gradient(135deg, #3a5289, #5b7ec2)' }}>
                {step}
              </span>
              Step {step}
              <span className="text-xs font-normal" style={{ color: '#9aa5bd' }}>({grouped[step].length} template{grouped[step].length !== 1 ? 's' : ''})</span>
            </h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {grouped[step].map(tmpl => {
                const typeStyle = TYPE_COLORS[tmpl.type] || TYPE_COLORS.custom;
                return (
                  <div
                    key={tmpl.id}
                    className="rounded-xl p-5 transition-all duration-200 hover:shadow-lg"
                    style={{
                      background: 'linear-gradient(145deg, rgba(255,255,255,0.95) 0%, rgba(243,245,252,0.9) 100%)',
                      border: '1px solid rgba(255, 255, 255, 0.6)',
                      boxShadow: '0 4px 24px rgba(15, 26, 46, 0.06)',
                    }}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="text-sm font-semibold truncate" style={{ color: '#1b2a4a' }}>{tmpl.name}</h4>
                          <span
                            className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold capitalize shrink-0"
                            style={{ background: typeStyle.bg, color: typeStyle.color }}
                          >
                            {(tmpl.type || 'custom').replace(/_/g, ' ')}
                          </span>
                          <span
                            className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold shrink-0"
                            style={{
                              background: tmpl.is_active
                                ? 'linear-gradient(135deg, #d1fae5, #a7f3d0)'
                                : 'linear-gradient(135deg, #f3f4f6, #e5e7eb)',
                              color: tmpl.is_active ? '#065f46' : '#6b7280',
                            }}
                          >
                            {tmpl.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </div>
                        <p className="text-xs truncate" style={{ color: '#6b7a99' }}>
                          Subject: {tmpl.subject || '(no subject)'}
                        </p>
                      </div>
                    </div>

                    <p className="text-xs mt-2 line-clamp-2" style={{ color: '#9aa5bd', lineHeight: 1.5 }}>
                      {tmpl.body ? tmpl.body.substring(0, 140) + (tmpl.body.length > 140 ? '...' : '') : '(empty body)'}
                    </p>

                    <div className="flex items-center gap-2 mt-4 pt-3" style={{ borderTop: '1px solid rgba(91, 126, 194, 0.08)' }}>
                      <button
                        onClick={() => setPreviewingTemplate(tmpl)}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all hover:shadow-sm"
                        style={{ background: 'rgba(91, 126, 194, 0.08)', color: '#5b7ec2' }}
                        title="Preview"
                      >
                        <Eye size={13} /> Preview
                      </button>
                      <button
                        onClick={() => setEditingTemplate(tmpl)}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all hover:shadow-sm"
                        style={{ background: 'rgba(91, 126, 194, 0.08)', color: '#5b7ec2' }}
                        title="Edit"
                      >
                        <Edit3 size={13} /> Edit
                      </button>
                      <button
                        onClick={() => handleDuplicate(tmpl.id)}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all hover:shadow-sm"
                        style={{ background: 'rgba(91, 126, 194, 0.08)', color: '#5b7ec2' }}
                        title="Duplicate"
                      >
                        <Copy size={13} /> Duplicate
                      </button>
                      <div className="flex-1" />
                      <button
                        onClick={() => handleDelete(tmpl.id, tmpl.name)}
                        className="p-1.5 rounded-lg transition-all hover:shadow-md"
                        style={{ background: 'rgba(239, 68, 68, 0.08)' }}
                        title="Delete"
                      >
                        <Trash2 size={13} style={{ color: '#ef4444' }} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))
      )}

      {/* Modals */}
      {showCreateForm && (
        <TemplateFormModal
          template={null}
          onClose={() => setShowCreateForm(false)}
          onSave={handleCreate}
        />
      )}
      {editingTemplate && (
        <TemplateFormModal
          template={editingTemplate}
          onClose={() => setEditingTemplate(null)}
          onSave={handleUpdate}
        />
      )}
      {previewingTemplate && (
        <PreviewModal
          template={previewingTemplate}
          onClose={() => setPreviewingTemplate(null)}
        />
      )}
    </div>
  );
}
