import { useState, useEffect, useRef, useCallback } from 'react';
import { Upload, Trash2, FileText, Image, FileSpreadsheet, File, X, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { getUploads, deleteUpload, uploadFile } from '../lib/api';

const CATEGORIES = [
  { id: '', label: 'All Files' },
  { id: 'email_lists', label: 'Email Lists' },
  { id: 'social_data', label: 'Social Data' },
  { id: 'templates', label: 'Templates' },
  { id: 'images', label: 'Images' },
  { id: 'documents', label: 'Documents' },
];

function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

function getFileIcon(mimeType) {
  if (!mimeType) return File;
  if (mimeType.startsWith('image/')) return Image;
  if (mimeType.includes('spreadsheet') || mimeType.includes('csv') || mimeType.includes('excel')) return FileSpreadsheet;
  if (mimeType.includes('text') || mimeType.includes('pdf') || mimeType.includes('document')) return FileText;
  return File;
}

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

export default function AdminUploadsPage() {
  const [uploads, setUploads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragActive, setDragActive] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('email_lists');
  const [description, setDescription] = useState('');
  const [toast, setToast] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => { loadData(); }, [activeCategory]);

  async function loadData() {
    try {
      const params = activeCategory ? { category: activeCategory } : {};
      const data = await getUploads(params);
      setUploads(Array.isArray(data) ? data : data.uploads || []);
    } catch (e) {
      console.error('Failed to load uploads:', e);
      setToast({ message: 'Failed to load files', type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(files) {
    if (!files || files.length === 0) return;

    setUploading(true);
    setUploadProgress(0);

    try {
      for (let i = 0; i < files.length; i++) {
        setUploadProgress(Math.round(((i) / files.length) * 100));
        await uploadFile(files[i], selectedCategory, description);
      }
      setUploadProgress(100);
      setToast({ message: `${files.length} file${files.length > 1 ? 's' : ''} uploaded successfully`, type: 'success' });
      setDescription('');
      await loadData();
    } catch (e) {
      setToast({ message: e.message || 'Upload failed', type: 'error' });
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  }

  async function handleDelete(id, filename) {
    if (!window.confirm(`Delete "${filename}"? This cannot be undone.`)) return;
    try {
      await deleteUpload(id);
      setToast({ message: 'File deleted', type: 'success' });
      await loadData();
    } catch (e) {
      setToast({ message: e.message || 'Failed to delete file', type: 'error' });
    }
  }

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleUpload(e.dataTransfer.files);
    }
  }, [selectedCategory, description]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-2 spinner-navy" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <div>
        <h2 className="text-xl font-bold" style={{ color: '#1b2a4a' }}>File Manager</h2>
        <p className="text-sm mt-1" style={{ color: '#6b7a99' }}>Upload and manage data files, lists, and assets</p>
      </div>

      {/* Upload Zone */}
      <div
        className="rounded-xl p-8 text-center transition-all duration-200"
        style={{
          border: dragActive ? '2px dashed #5b7ec2' : '2px dashed rgba(91, 126, 194, 0.25)',
          background: dragActive ? 'rgba(91, 126, 194, 0.05)' : 'rgba(255, 255, 255, 0.6)',
          boxShadow: dragActive ? '0 0 0 4px rgba(91, 126, 194, 0.1)' : 'none',
        }}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <Upload size={32} style={{ color: dragActive ? '#5b7ec2' : '#9aa5bd' }} className="mx-auto mb-3" />
        <p className="text-sm font-medium" style={{ color: '#374a6d' }}>
          {dragActive ? 'Drop files here' : 'Drag and drop files, or click to browse'}
        </p>

        <div className="flex items-center justify-center gap-4 mt-4 flex-wrap">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Category</label>
            <select
              value={selectedCategory}
              onChange={e => setSelectedCategory(e.target.value)}
              className="block mt-1 px-3 py-2 rounded-lg text-sm outline-none"
              style={{
                border: '1px solid rgba(91, 126, 194, 0.2)',
                background: 'white',
                color: '#1b2a4a',
                minWidth: 160,
              }}
            >
              <option value="email_lists">Email Lists</option>
              <option value="social_data">Social Data</option>
              <option value="templates">Templates</option>
              <option value="images">Images</option>
              <option value="documents">Documents</option>
            </select>
          </div>
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Description (optional)</label>
            <input
              type="text"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Brief file description"
              className="block mt-1 px-3 py-2 rounded-lg text-sm outline-none"
              style={{
                border: '1px solid rgba(91, 126, 194, 0.2)',
                background: 'white',
                color: '#1b2a4a',
                minWidth: 220,
              }}
              onFocus={e => { e.target.style.borderColor = '#5b7ec2'; }}
              onBlur={e => { e.target.style.borderColor = 'rgba(91, 126, 194, 0.2)'; }}
            />
          </div>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={e => handleUpload(e.target.files)}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="mt-4 inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold text-white transition-all hover:shadow-lg disabled:opacity-50"
          style={{ background: 'linear-gradient(135deg, #3a5289, #5b7ec2)' }}
        >
          {uploading ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Uploading... {uploadProgress}%
            </>
          ) : (
            <>
              <Upload size={16} />
              Select Files
            </>
          )}
        </button>

        {uploading && (
          <div className="mt-3 w-full max-w-sm mx-auto">
            <div className="h-1.5 rounded-full" style={{ background: 'rgba(91, 126, 194, 0.15)' }}>
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%`, background: 'linear-gradient(90deg, #5b7ec2, #34d399)' }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Category Tabs */}
      <div className="flex gap-2 flex-wrap">
        {CATEGORIES.map(cat => (
          <button
            key={cat.id}
            onClick={() => { setActiveCategory(cat.id); setLoading(true); }}
            className="px-4 py-2 rounded-lg text-xs font-semibold transition-all"
            style={{
              background: activeCategory === cat.id
                ? 'linear-gradient(135deg, #3a5289, #5b7ec2)'
                : 'rgba(255, 255, 255, 0.8)',
              color: activeCategory === cat.id ? 'white' : '#6b7a99',
              border: activeCategory === cat.id ? 'none' : '1px solid rgba(91, 126, 194, 0.15)',
              boxShadow: activeCategory === cat.id ? '0 2px 8px rgba(91, 126, 194, 0.3)' : 'none',
            }}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Files Table */}
      <div className="glass-table rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(15, 26, 46, 0.06)', background: 'rgba(238, 241, 248, 0.5)' }}>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Filename</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Category</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Type</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Size</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Rows</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Date</th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider" style={{ color: '#6b7a99' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {uploads.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-sm" style={{ color: '#9aa5bd' }}>
                    <Upload size={32} className="mx-auto mb-2 opacity-40" />
                    No files uploaded yet
                  </td>
                </tr>
              ) : (
                uploads.map(file => {
                  const FileIcon = getFileIcon(file.mime_type);
                  return (
                    <tr
                      key={file.id}
                      className="transition-all duration-200"
                      style={{ borderBottom: '1px solid rgba(15, 26, 46, 0.04)' }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(91, 126, 194, 0.04)'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                    >
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <FileIcon size={16} style={{ color: '#5b7ec2' }} />
                          <span className="font-medium" style={{ color: '#374a6d' }}>{file.original_filename || file.filename}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize"
                          style={{ background: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', color: '#1e40af' }}
                        >
                          {(file.category || 'uncategorized').replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: '#6b7a99' }}>
                        {file.mime_type?.split('/').pop() || file.file_type || '—'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-xs font-mono" style={{ color: '#6b7a99' }}>
                        {formatFileSize(file.file_size)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-xs font-mono" style={{ color: '#6b7a99' }}>
                        {file.row_count || '—'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold"
                          style={{
                            background: file.status === 'processed'
                              ? 'linear-gradient(135deg, #d1fae5, #a7f3d0)'
                              : file.status === 'error'
                              ? 'linear-gradient(135deg, #fee2e2, #fecaca)'
                              : 'linear-gradient(135deg, #fef3c7, #fde68a)',
                            color: file.status === 'processed' ? '#065f46' : file.status === 'error' ? '#991b1b' : '#92400e',
                          }}
                        >
                          {file.status || 'pending'}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-xs" style={{ color: '#6b7a99' }}>
                        {file.created_at ? new Date(file.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-right">
                        <button
                          onClick={() => handleDelete(file.id, file.original_filename || file.filename)}
                          className="p-1.5 rounded-lg transition-all hover:shadow-md"
                          style={{ background: 'rgba(239, 68, 68, 0.08)' }}
                          title="Delete file"
                        >
                          <Trash2 size={14} style={{ color: '#ef4444' }} />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
