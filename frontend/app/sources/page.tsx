'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, type Source, type PipelineConfig, type ScheduledJob } from '@/lib/api';
import { useMeta } from '@/lib/useMeta';
import { useToast } from '../components/Toast';

interface FormState {
  pipeline_name: string;
  pipeline_description: string;
  url: string;
  agent_id: string;
  name: string;
}
const emptyForm: FormState = { pipeline_name: '', pipeline_description: '', url: '', agent_id: 'competitors', name: '' };

interface PipelineView {
  config: PipelineConfig;
  sources: Source[];
}

export default function SourcesPage() {
  const { agents, agentBadge } = useMeta();
  const AGENT_OPTIONS = agents.map(a => ({ value: a.id, label: a.label }));

  const [pipelines, setPipelines] = useState<PipelineView[]>([]);
  const [orphanSources, setOrphanSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingConfigId, setEditingConfigId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const toast = useToast();

  const loadData = useCallback(async () => {
    try {
      const [configs, sources] = await Promise.all([
        api.pipelineConfigs.list(),
        api.sources.list(),
      ]);

      const views: PipelineView[] = configs.map(config => ({
        config,
        sources: sources.filter(s =>
          (s.name || '').toLowerCase() === config.pipeline_name.toLowerCase()
        ),
      }));

      const matchedSourceIds = new Set(views.flatMap(v => v.sources.map(s => s.id)));
      const orphans = sources.filter(s => !matchedSourceIds.has(s.id));

      setPipelines(views);
      setOrphanSources(orphans);
    } catch {
      setPipelines([]);
      setOrphanSources([]);
    }
  }, []);

  useEffect(() => {
    loadData().finally(() => setLoading(false));
  }, [loadData]);

  const resetForm = () => { setForm(emptyForm); setEditingConfigId(null); setShowForm(false); };

  const startEdit = (pv: PipelineView) => {
    const urls = pv.sources.map(s => s.url).join(', ');
    const firstSource = pv.sources[0];
    setForm({
      pipeline_name: pv.config.pipeline_name,
      pipeline_description: pv.config.pipeline_description || '',
      url: urls,
      agent_id: firstSource?.agent_id || 'competitors',
      name: firstSource?.name || '',
    });
    setEditingConfigId(pv.config.id);
    setShowForm(true);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.pipeline_name.trim()) {
      toast.show('Pipeline Name is required.', 'error');
      return;
    }
    if (!form.url.trim()) {
      toast.show('URLs are required.', 'error');
      return;
    }
    try {
      if (editingConfigId) {
        await api.pipelineConfigs.update(editingConfigId, {
          pipeline_name: form.pipeline_name.trim(),
          pipeline_description: form.pipeline_description.trim() || undefined,
        });

        const existingPV = pipelines.find(p => p.config.id === editingConfigId);
        if (existingPV) {
          for (const s of existingPV.sources) {
            await api.sources.delete(s.id);
          }
        }

        const urls = form.url.split(',').map(u => u.trim()).filter(Boolean);
        for (const url of urls) {
          await api.sources.create({
            url,
            agent_id: form.agent_id,
            name: form.pipeline_name.trim(),
          });
        }
        toast.show('Pipeline updated!', 'success');
      } else {
        const newConfig = await api.pipelineConfigs.create({
          pipeline_name: form.pipeline_name.trim(),
          pipeline_description: form.pipeline_description.trim() || undefined,
        });

        const urls = form.url.split(',').map(u => u.trim()).filter(Boolean);
        for (const url of urls) {
          await api.sources.create({
            url,
            agent_id: form.agent_id,
            name: form.pipeline_name.trim(),
          });
        }
        toast.show(`Pipeline added with ${urls.length} URL${urls.length > 1 ? 's' : ''}!`, 'success');
      }
      resetForm();
      await loadData();
    } catch { toast.show(editingConfigId ? 'Failed to update.' : 'Failed to add.', 'error'); }
  };

  const removePipeline = async (pv: PipelineView) => {
    try {
      const jobs: ScheduledJob[] = await api.scheduler.list();
      const linked = jobs.filter(j => j.pipeline_name === pv.config.pipeline_name);
      if (linked.length > 0) {
        const names = linked.map(j => `"${j.scheduler_name}"`).join(', ');
        toast.show(
          `Pipeline "${pv.config.pipeline_name}" can't be deleted — it is used by scheduler ${names}. Please delete the scheduler first.`,
          'error',
        );
        return;
      }
    } catch { /* proceed if scheduler check fails */ }

    if (!confirm(`Remove pipeline "${pv.config.pipeline_name}" and all its sources?`)) return;
    setDeletingId(pv.config.id);
    try {
      for (const s of pv.sources) {
        await api.sources.delete(s.id);
      }
      await api.pipelineConfigs.delete(pv.config.id);
      toast.show('Pipeline removed.', 'info');
      await loadData();
    } catch { toast.show('Failed to remove.', 'error'); }
    finally { setDeletingId(null); }
  };

  const removeOrphanSource = async (id: number) => {
    if (!confirm('Remove this source?')) return;
    setDeletingId(id);
    try { await api.sources.delete(id); toast.show('Source removed.', 'info'); await loadData(); }
    catch { toast.show('Failed to remove.', 'error'); }
    finally { setDeletingId(null); }
  };

  const togglePipelineEnabled = async (pv: PipelineView) => {
    const newEnabled = !pv.config.enabled;
    setPipelines(prev => prev.map(p =>
      p.config.id === pv.config.id ? { ...p, config: { ...p.config, enabled: newEnabled } } : p
    ));
    try {
      await api.pipelineConfigs.update(pv.config.id, { enabled: newEnabled });
      for (const s of pv.sources) {
        await api.sources.update(s.id, { enabled: newEnabled });
      }
      toast.show(`Pipeline "${pv.config.pipeline_name}" ${newEnabled ? 'activated' : 'deactivated'}.`, 'info');
      await loadData();
    } catch {
      toast.show('Failed to toggle pipeline.', 'error');
      await loadData();
    }
  };

  const toggleSourceEnabled = async (s: Source) => {
    try {
      await api.sources.update(s.id, { enabled: !s.enabled });
      toast.show(`Source ${!s.enabled ? 'activated' : 'deactivated'}.`, 'info');
      await loadData();
    } catch { toast.show('Failed to toggle.', 'error'); }
  };

  const hasPipelines = pipelines.length > 0 || orphanSources.length > 0;

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
          <h2 className="text-base font-bold" style={{ color: '#1A2238' }}>{editingConfigId ? 'Edit Pipeline' : 'New Pipeline'}</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-xs font-semibold" style={{ color: '#6b7394' }}>Pipeline Name <span className="text-red-500">*</span></label>
              <input type="text" placeholder="e.g. Morning Intelligence Sweep" required value={form.pipeline_name} onChange={e => setForm({...form, pipeline_name: e.target.value})} className="input-field" />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold" style={{ color: '#6b7394' }}>Pipeline Description</label>
              <input type="text" placeholder="e.g. Track competitor releases and model updates" value={form.pipeline_description} onChange={e => setForm({...form, pipeline_description: e.target.value})} className="input-field" />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1.5 block text-xs font-semibold" style={{ color: '#6b7394' }}>
                URLs <span className="text-red-500">*</span> <span className="font-normal text-[10px]">(separate multiple URLs with commas)</span>
              </label>
              <textarea
                placeholder={"https://openai.com/blog, https://deepmind.google/blog, https://anthropic.com/news"}
                required
                value={form.url}
                onChange={e => setForm({...form, url: e.target.value})}
                className="input-field min-h-[56px] resize-y"
                rows={2}
              />
              {form.url.includes(',') && (
                <p className="mt-1 text-[10px] font-medium" style={{ color: '#059669' }}>
                  {form.url.split(',').map(u => u.trim()).filter(Boolean).length} URLs will be added
                </p>
              )}
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold" style={{ color: '#6b7394' }}>Agent Type</label>
              <select value={form.agent_id} onChange={e => setForm({...form, agent_id: e.target.value})} className="input-field">
                {AGENT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-3 pt-1">
            <button type="submit" className="btn-primary">{editingConfigId ? 'Update Pipeline' : 'Save Pipeline'}</button>
            <button type="button" onClick={resetForm} className="btn-ghost">Cancel</button>
          </div>
        </form>
      )}

      {loading ? <div className="space-y-3">{[1,2,3,4].map(i => <div key={i} className="h-20 skeleton" />)}</div> : !hasPipelines ? (
        <div className="glass-card"><div className="empty-state">
          <div className="empty-state-icon"><svg className="h-6 w-6" style={{ color: '#9DAAF2' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.915-3.373a4.5 4.5 0 00-6.364-6.364L4.5 8.25" /></svg></div>
          <p className="text-sm font-semibold" style={{ color: '#3d4660' }}>No pipelines configured</p>
          <p className="text-xs" style={{ color: '#6b7394' }}>Add URLs to power your intelligence pipeline.</p>
          <button onClick={() => setShowForm(true)} className="btn-primary mt-3"><svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>Add Pipeline</button>
        </div></div>
      ) : (
        <div className="stagger-children space-y-4">
          {pipelines.map(pv => (
            <div key={pv.config.id} className={`glass-card overflow-hidden ${!pv.config.enabled ? 'opacity-60' : ''}`}>
              <div className="flex items-center gap-4 px-5 py-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: pv.config.enabled ? 'rgba(157,170,242,0.1)' : 'rgba(26,34,56,0.04)' }}>
                  <svg className="h-5 w-5" style={{ color: pv.config.enabled ? '#7580d4' : '#9ba2bc' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-bold" style={{ color: '#1A2238' }}>{pv.config.pipeline_name}</span>
                    <span className={`badge ${pv.config.enabled ? 'badge-emerald' : 'badge-zinc'}`}>{pv.config.enabled ? 'Active' : 'Inactive'}</span>
                    <span className="badge badge-indigo">{pv.sources.length} URL{pv.sources.length !== 1 ? 's' : ''}</span>
                    {pv.sources.length > 0 && (
                      <span className={`badge ${agentBadge(pv.sources[0].agent_id)}`}>{pv.sources[0].agent_id}</span>
                    )}
                  </div>
                  {pv.config.pipeline_description && (
                    <p className="mt-0.5 text-xs" style={{ color: '#6b7394' }}>{pv.config.pipeline_description}</p>
                  )}
                  {pv.sources.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {pv.sources.map(s => (
                        <div key={s.id} className="flex items-center gap-2 text-xs" style={{ color: '#9ba2bc' }}>
                          <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.915-3.373a4.5 4.5 0 00-6.364-6.364L4.5 8.25" />
                          </svg>
                          <span className="truncate">{s.url}</span>
                          <button
                            onClick={() => toggleSourceEnabled(s)}
                            className={`shrink-0 text-[10px] font-semibold transition-colors ${s.enabled ? 'text-emerald-600 hover:text-amber-600' : 'hover:text-emerald-600'}`}
                            style={s.enabled ? {} : { color: '#9ba2bc' }}
                          >
                            {s.enabled ? 'Active' : 'Inactive'}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {pv.sources.length === 0 && (
                    <p className="mt-1 text-[11px] italic" style={{ color: '#b0b5c8' }}>No source URLs linked — click Edit to add URLs</p>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => togglePipelineEnabled(pv)}
                    className={`text-xs font-semibold px-2 py-1 rounded-lg transition-colors ${pv.config.enabled ? 'text-emerald-600 hover:text-amber-600 hover:bg-amber-50' : 'hover:text-emerald-600 hover:bg-emerald-50'}`}
                    style={pv.config.enabled ? {} : { color: '#9ba2bc' }}
                    title={pv.config.enabled ? 'Set Inactive' : 'Set Active'}
                  >
                    {pv.config.enabled ? 'Active' : 'Inactive'}
                  </button>
                  <button onClick={() => startEdit(pv)} className="btn-ghost text-xs">Edit</button>
                  <button
                    onClick={() => removePipeline(pv)}
                    disabled={deletingId === pv.config.id}
                    className="btn-danger text-xs"
                  >
                    {deletingId === pv.config.id ? '...' : 'Delete'}
                  </button>
                </div>
              </div>
            </div>
          ))}

          {orphanSources.length > 0 && (
            <>
              <h3 className="text-xs font-bold uppercase tracking-wider pt-2" style={{ color: '#6b7394' }}>Unlinked Sources</h3>
              {orphanSources.map(s => (
                <div key={s.id} className="glass-card p-4 sm:px-5">
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: 'rgba(26,34,56,0.04)' }}>
                      <svg className="h-5 w-5" style={{ color: '#9ba2bc' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" /></svg>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold" style={{ color: '#1A2238' }}>
                        {s.name || (() => { try { return new URL(s.url.split(',')[0].trim()).hostname; } catch { return s.url.split(',')[0].trim(); } })()}
                      </div>
                      <div className="mt-0.5 text-xs truncate" style={{ color: '#9ba2bc' }}>{s.url}</div>
                    </div>
                    <span className={`hidden px-2 py-0.5 text-[11px] font-bold sm:inline-flex ${agentBadge(s.agent_id)}`}>{s.agent_id}</span>
                    <button
                      onClick={() => toggleSourceEnabled(s)}
                      className={`text-xs font-semibold transition-colors ${s.enabled ? 'text-emerald-600 hover:text-amber-600' : 'hover:text-emerald-600'}`}
                      style={s.enabled ? {} : { color: '#9ba2bc' }}
                    >
                      {s.enabled ? 'Active' : 'Inactive'}
                    </button>
                    <button onClick={() => removeOrphanSource(s.id)} disabled={deletingId === s.id} className="btn-danger text-xs">{deletingId === s.id ? '...' : 'Delete'}</button>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
