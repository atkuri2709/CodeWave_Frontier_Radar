'use client';

import { useEffect, useState } from 'react';
import { api, type Source } from '@/lib/api';
import { useToast } from '../components/Toast';

const AGENT_OPTIONS = [ { value: 'competitors', label: 'Competitors' }, { value: 'model_providers', label: 'Model Providers' }, { value: 'research', label: 'Research' }, { value: 'hf_benchmarks', label: 'HF Benchmarks' } ] as const;
const AGENT_BADGE: Record<string, string> = { competitors: 'agent-orange', model_providers: 'agent-lavender', research: 'agent-gold', hf_benchmarks: 'agent-navy' };

interface FormState { pipeline_name: string; pipeline_description: string; url: string; agent_id: string; name: string }
const emptyForm: FormState = { pipeline_name: '', pipeline_description: '', url: '', agent_id: 'competitors', name: '' };

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const toast = useToast();

  useEffect(() => { api.sources.list().then(setSources).catch(() => {}).finally(() => setLoading(false)); }, []);

  const resetForm = () => { setForm(emptyForm); setEditingId(null); setShowForm(false); };

  const startEdit = (s: Source) => {
    setForm({
      pipeline_name: '', pipeline_description: '',
      url: s.url, agent_id: s.agent_id, name: s.name || '',
    });
    setEditingId(s.id);
    setShowForm(true);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingId && !form.pipeline_name.trim()) {
      toast.show('Pipeline Name is required.', 'error');
      return;
    }
    if (!form.url.trim()) {
      toast.show('URLs are required.', 'error');
      return;
    }
    try {
      if (editingId) {
        await api.sources.update(editingId, { name: form.name || undefined });
        toast.show('Pipeline updated!', 'success');
      } else {
        const urlCount = form.url.split(',').map(u => u.trim()).filter(Boolean).length;
        await api.sources.create({ url: form.url, agent_id: form.agent_id, name: form.name || undefined });

        if (form.pipeline_name.trim()) {
          await api.pipelineConfigs.create({
            pipeline_name: form.pipeline_name.trim(),
            pipeline_description: form.pipeline_description.trim() || undefined,
          });
        }
        toast.show(`Pipeline added with ${urlCount} URL${urlCount > 1 ? 's' : ''}!`, 'success');
      }
      resetForm();
      setSources(await api.sources.list());
    } catch { toast.show(editingId ? 'Failed to update.' : 'Failed to add.', 'error'); }
  };

  const remove = async (id: number) => {
    if (!confirm('Remove this pipeline source?')) return;
    setDeletingId(id);
    try { await api.sources.delete(id); setSources(await api.sources.list()); toast.show('Pipeline source removed.', 'info'); }
    catch { toast.show('Failed to remove.', 'error'); }
    finally { setDeletingId(null); }
  };

  const toggleEnabled = async (s: Source) => {
    try { await api.sources.update(s.id, { enabled: !s.enabled }); setSources(await api.sources.list()); toast.show(`Pipeline ${!s.enabled ? 'enabled' : 'disabled'}.`, 'info'); }
    catch { toast.show('Failed to toggle.', 'error'); }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header relative">
        <div className="absolute inset-0 overflow-hidden rounded-2xl"><div className="absolute -top-16 -right-16 h-48 w-48 opacity-20" style={{ background: 'radial-gradient(circle, rgba(157,170,242,0.5) 0%, transparent 60%)' }} /></div>
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div><h1>Intelligence Pipeline</h1><p>Configure the pipelines powering your intelligence — blogs, changelogs, RSS, leaderboards. Set agent types and URLs.</p></div>
          <button onClick={() => { resetForm(); setShowForm(!showForm); }} className="btn-primary shrink-0">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>Add Pipeline
          </button>
        </div>
      </div>

      {showForm && (
        <form onSubmit={submit} className="glass-card animate-slide-up space-y-5 p-6">
          <h2 className="text-base font-bold" style={{ color: '#1A2238' }}>{editingId ? 'Edit Pipeline' : 'New Pipeline'}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {!editingId && (
              <>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold" style={{ color: '#6b7394' }}>Pipeline Name <span className="text-red-500">*</span></label>
                  <input type="text" placeholder="e.g. Morning Intelligence Sweep" required value={form.pipeline_name} onChange={e => setForm({...form, pipeline_name: e.target.value})} className="input-field" />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold" style={{ color: '#6b7394' }}>Pipeline Description</label>
                  <input type="text" placeholder="e.g. Track competitor releases and model updates" value={form.pipeline_description} onChange={e => setForm({...form, pipeline_description: e.target.value})} className="input-field" />
                </div>
              </>
            )}
            <div className="sm:col-span-2">
              <label className="mb-1.5 block text-xs font-semibold" style={{ color: '#6b7394' }}>
                URLs <span className="text-red-500">*</span> <span className="font-normal text-[10px]">(separate multiple URLs with commas)</span>
              </label>
              <textarea
                placeholder={"https://openai.com/blog, https://deepmind.google/blog, https://anthropic.com/news"}
                required
                disabled={!!editingId}
                value={form.url}
                onChange={e => setForm({...form, url: e.target.value})}
                className="input-field min-h-[56px] resize-y"
                rows={2}
                style={editingId ? { opacity: 0.6 } : {}}
              />
              {!editingId && form.url.includes(',') && (
                <p className="mt-1 text-[10px] font-medium" style={{ color: '#059669' }}>
                  {form.url.split(',').map(u => u.trim()).filter(Boolean).length} URLs will be added
                </p>
              )}
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold" style={{ color: '#6b7394' }}>Name (optional)</label>
              <input type="text" placeholder="e.g. OpenAI Blog" value={form.name} onChange={e => setForm({...form, name: e.target.value})} className="input-field" />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold" style={{ color: '#6b7394' }}>Agent Type</label>
              <select value={form.agent_id} disabled={!!editingId} onChange={e => setForm({...form, agent_id: e.target.value})} className="input-field" style={editingId ? { opacity: 0.6 } : {}}>
                {AGENT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-3 pt-1">
            <button type="submit" className="btn-primary">{editingId ? 'Update Pipeline' : 'Save Pipeline'}</button>
            <button type="button" onClick={resetForm} className="btn-ghost">Cancel</button>
          </div>
        </form>
      )}

      {loading ? <div className="space-y-3">{[1,2,3,4].map(i => <div key={i} className="h-20 skeleton" />)}</div> : sources.length === 0 ? (
        <div className="glass-card"><div className="empty-state">
          <div className="empty-state-icon"><svg className="h-6 w-6" style={{ color: '#9DAAF2' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.915-3.373a4.5 4.5 0 00-6.364-6.364L4.5 8.25" /></svg></div>
          <p className="text-sm font-semibold" style={{ color: '#3d4660' }}>No pipelines configured</p>
          <p className="text-xs" style={{ color: '#6b7394' }}>Add URLs to power your intelligence pipeline.</p>
          <button onClick={() => setShowForm(true)} className="btn-primary mt-3"><svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>Add Pipeline</button>
        </div></div>
      ) : (
        <div className="stagger-children space-y-3">
          {sources.map(s => (
            <div key={s.id} className="glass-card p-4 sm:px-5">
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: 'rgba(26,34,56,0.04)' }}>
                  <svg className="h-5 w-5" style={{ color: '#9ba2bc' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" /></svg>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold" style={{ color: '#1A2238' }}>{s.name || (() => { try { return new URL(s.url.split(',')[0].trim()).hostname; } catch { return s.url.split(',')[0].trim(); } })()}</div>
                  <div className="mt-0.5 text-xs space-y-0.5" style={{ color: '#9ba2bc' }}>
                    {s.url.split(',').map((u, i) => (
                      <div key={i} className="truncate">{u.trim()}</div>
                    ))}
                  </div>
                  {s.url.includes(',') && (
                    <span className="mt-1 inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded" style={{ background: 'rgba(157,170,242,0.15)', color: '#6366f1' }}>
                      {s.url.split(',').filter(u => u.trim()).length} URLs
                    </span>
                  )}
                </div>
                <span className={`hidden px-2 py-0.5 text-[11px] font-bold sm:inline-flex ${AGENT_BADGE[s.agent_id] || 'badge-zinc'}`}>{s.agent_id}</span>
                <button onClick={() => toggleEnabled(s)} className={`text-xs font-semibold transition-colors ${s.enabled ? 'text-emerald-600 hover:text-amber-600' : 'hover:text-emerald-600'}`} style={s.enabled ? {} : { color: '#9ba2bc' }}>{s.enabled ? 'Active' : 'Disabled'}</button>
                <button onClick={() => startEdit(s)} className="btn-ghost text-xs">Edit</button>
                <button onClick={() => remove(s.id)} disabled={deletingId === s.id} className="btn-danger text-xs">{deletingId === s.id ? '...' : 'Delete'}</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
