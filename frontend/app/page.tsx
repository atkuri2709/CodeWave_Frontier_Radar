'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { api, API_BASE, type Run, type FindingSummary, type PipelineConfig } from '@/lib/api';
import { useToast } from './components/Toast';
import Link from 'next/link';
import { useMeta } from '@/lib/useMeta';

function ConfidencePill({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.75 ? 'text-emerald-600' : value >= 0.55 ? 'text-amber-600' : value >= 0.35 ? 'text-orange-600' : 'text-red-600';
  const bg = value >= 0.75 ? 'bg-emerald-500' : value >= 0.55 ? 'bg-amber-500' : value >= 0.35 ? 'bg-orange-500' : 'bg-red-500';
  const label = value >= 0.75 ? 'High' : value >= 0.55 ? 'Medium' : value >= 0.35 ? 'Low' : 'Very Low';
  return (<span className={`flex items-center gap-2 text-xs font-medium ${color}`}><span className="confidence-meter"><span className={`confidence-fill ${bg}`} style={{ width: `${pct}%` }} /></span>{pct}% {label}</span>);
}

type RunMode = null | 'menu' | 'pipeline' | 'yaml-confirm' | 'json';

export default function DashboardPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [findings, setFindings] = useState<FindingSummary[]>([]);
  const [totalFindings, setTotalFindings] = useState(0);
  const [digests, setDigests] = useState<{ id: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);

  const [runMode, setRunMode] = useState<RunMode>(null);
  const [pipelineConfigs, setPipelineConfigs] = useState<PipelineConfig[]>([]);
  const [selectedConfigId, setSelectedConfigId] = useState<number | null>(null);
  const [jsonInput, setJsonInput] = useState('{\n  "agents": {}\n}');
  const [jsonSave, setJsonSave] = useState(false);
  const [jsonName, setJsonName] = useState('');
  const [jsonError, setJsonError] = useState('');

  const router = useRouter();
  const toast = useToast();
  const { agentLabel, agentBadge, agentIds } = useMeta();

  const refreshData = useCallback(async () => {
    const [r, f, d] = await Promise.all([
      api.runs.list(), api.findings.list({}), api.digests.list(),
    ]);
    setRuns(r); setTotalFindings(f.length); setFindings(f.slice(0, 10)); setDigests(d);
  }, []);

  useEffect(() => {
    refreshData().catch(() => {}).finally(() => setLoading(false));
  }, [refreshData]);

  const [, setTick] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => {
      setTick(t => t + 1);
      refreshData().catch(() => {});
    }, 60000);
    return () => clearInterval(timer);
  }, [refreshData]);

  const lastRun = runs[0];
  const latestDigestId = digests[0]?.id ?? lastRun?.digest_id ?? null;
  const downloadPdfUrl = latestDigestId ? `${API_BASE}/digests/${latestDigestId}/download` : null;

  const pollRun = async (runId: number): Promise<Run> => {
    const current = await api.runs.get(runId);
    if (current.status === 'running' || current.status === 'pending') {
      await new Promise(r => setTimeout(r, 3000));
      await refreshData();
      return pollRun(runId);
    }
    return current;
  };

  const finishRun = async (run: Run) => {
    const finished = await pollRun(run.id);
    await refreshData();
    if (finished.status === 'success') {
      toast.show(`Pipeline completed — ${finished.findings_count} findings discovered!`, 'success');
    } else if (finished.status === 'partial') {
      toast.show(`Pipeline partially completed — ${finished.findings_count} findings. Some agents failed.`, 'info');
    } else {
      toast.show(`Pipeline finished with status: ${finished.status}. Check Runs page for details.`, 'error');
    }
  };

  // --- YAML run ---
  const handleRunYaml = async () => {
    setTriggering(true);
    setRunMode(null);
    const randomName = `YAML-Run-${Date.now().toString(36).toUpperCase()}`;
    try {
      const run = await api.runs.trigger({ trigger: 'manual', pipeline_name: randomName, use_yaml: true });
      await finishRun(run);
    } catch {
      toast.show('YAML pipeline run failed.', 'error');
    } finally {
      setTriggering(false);
    }
  };

  // --- Pipeline run ---
  const handleRunPipeline = async () => {
    if (!selectedConfigId) return;
    const cfg = pipelineConfigs.find(c => c.id === selectedConfigId);
    if (!cfg) return;
    setTriggering(true);
    setRunMode(null);
    try {
      const run = await api.runs.trigger({
        trigger: 'manual',
        pipeline_name: cfg.pipeline_name,
        pipeline_description: cfg.pipeline_description || undefined,
        config_json: cfg.config_json as Record<string, unknown> | undefined,
      });
      await finishRun(run);
    } catch {
      toast.show('Pipeline run failed.', 'error');
    } finally {
      setTriggering(false);
    }
  };

  // --- JSON run ---
  const handleRunJson = async () => {
    setJsonError('');
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(jsonInput);
    } catch {
      setJsonError('Invalid JSON. Please check your syntax.');
      return;
    }
    setTriggering(true);
    setRunMode(null);
    try {
      const run = await api.runs.trigger({
        trigger: 'manual',
        pipeline_name: jsonSave && jsonName.trim() ? jsonName.trim() : 'JSON Config',
        config_json: parsed,
        save_config: jsonSave && !!jsonName.trim(),
      });
      await finishRun(run);
    } catch {
      toast.show('JSON pipeline run failed.', 'error');
    } finally {
      setTriggering(false);
    }
  };

  const openPipelineSelect = async () => {
    setRunMode('pipeline');
    try {
      const configs = await api.pipelineConfigs.list();
      setPipelineConfigs(configs);
      if (configs.length > 0) setSelectedConfigId(configs[0].id);
    } catch {
      setPipelineConfigs([]);
    }
  };

  const formatRelative = (dateStr: string | null) => {
    if (!dateStr) return '—';
    const diffM = Math.floor((Date.now() - new Date(dateStr).getTime()) / 60000);
    if (diffM < 1) return 'Just now'; if (diffM < 60) return `${diffM}m ago`;
    const diffH = Math.floor(diffM / 60); if (diffH < 24) return `${diffH}h ago`;
    return new Date(dateStr).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' });
  };

  const statusColor = (s: string) => s === 'success' ? 'badge-emerald' : s === 'running' ? 'badge-amber' : s === 'failed' || s === 'partial' ? 'badge-red' : 'badge-zinc';

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header relative">
        <div className="absolute inset-0 overflow-hidden rounded-2xl">
          <div className="absolute -top-20 -right-20 h-60 w-60 opacity-20" style={{ background: 'radial-gradient(circle, rgba(255,106,61,0.5) 0%, transparent 60%)' }} />
          <div className="absolute bottom-0 left-0 h-40 w-40 opacity-15" style={{ background: 'radial-gradient(circle, rgba(157,170,242,0.5) 0%, transparent 60%)' }} />
          <div className="absolute top-10 right-40 h-32 w-32 opacity-20" style={{ background: 'radial-gradient(circle, rgba(244,219,125,0.4) 0%, transparent 60%)' }} />
        </div>
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1>Dashboard</h1>
              {lastRun?.status === 'running' && (
                <span className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold" style={{ background: 'rgba(244,219,125,0.15)', color: '#F4DB7D' }}>
                  <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse-dot" />Pipeline running
                </span>
              )}
            </div>
          </div>

          {/* Run Pipeline + Dropdown */}
          <div className="relative shrink-0 flex gap-2">
            <button
              onClick={() => triggering ? undefined : setRunMode(runMode === 'menu' ? null : 'menu')}
              disabled={triggering}
              className="btn-primary"
            >
              {triggering ? (
                <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" /> Running...</>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" /></svg>
                  Run Pipeline
                  <svg className="h-3 w-3 ml-1" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>
                </>
              )}
            </button>

            {/* Dropdown Menu */}
            {runMode === 'menu' && !triggering && (
              <div className="absolute right-0 top-full z-30 mt-2 w-52 rounded-xl border bg-white shadow-xl animate-slide-up overflow-hidden" style={{ borderColor: 'rgba(26,34,56,0.1)' }}>
                <button onClick={() => setRunMode('yaml-confirm')} className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm font-medium transition-colors hover:bg-[rgba(157,170,242,0.06)]" style={{ color: '#1A2238' }}>
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg text-[10px] font-bold" style={{ background: 'rgba(244,219,125,0.15)', color: '#b8960a' }}>YML</span>
                  YAML
                </button>
                <button onClick={openPipelineSelect} className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm font-medium transition-colors hover:bg-[rgba(157,170,242,0.06)]" style={{ color: '#1A2238', borderTop: '1px solid rgba(26,34,56,0.06)' }}>
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg text-[10px] font-bold" style={{ background: 'rgba(255,106,61,0.1)', color: '#FF6A3D' }}>
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" /></svg>
                  </span>
                  Pipeline
                </button>
              </div>
            )}

            {/* YAML Confirm Modal */}
            {runMode === 'yaml-confirm' && (
              <div className="absolute right-0 top-full z-30 mt-2 w-72 rounded-xl border bg-white p-5 shadow-xl animate-slide-up" style={{ borderColor: 'rgba(26,34,56,0.1)' }}>
                <div className="flex items-center gap-2 mb-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold" style={{ background: 'rgba(244,219,125,0.15)', color: '#b8960a' }}>YML</span>
                  <div>
                    <p className="text-sm font-bold" style={{ color: '#1A2238' }}>Run from YAML</p>
                    <p className="text-[10px]" style={{ color: '#9ba2bc' }}>Uses radar.yaml + DB sources</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={handleRunYaml} className="btn-primary flex-1 text-xs">
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" /></svg>
                    Run Pipeline
                  </button>
                  <button onClick={() => setRunMode(null)} className="btn-secondary text-xs">Cancel</button>
                </div>
              </div>
            )}

            {/* Pipeline Select Modal */}
            {runMode === 'pipeline' && (
              <div className="absolute right-0 top-full z-30 mt-2 w-80 rounded-xl border bg-white p-5 shadow-xl animate-slide-up" style={{ borderColor: 'rgba(26,34,56,0.1)' }}>
                <p className="text-sm font-bold mb-3" style={{ color: '#1A2238' }}>Select Pipeline</p>
                {pipelineConfigs.length === 0 ? (
                  <div className="py-4 text-center">
                    <p className="text-xs" style={{ color: '#6b7394' }}>No saved pipelines yet.</p>
                    <p className="text-[10px] mt-1" style={{ color: '#9ba2bc' }}>Add feeds on the Pipeline page to create one.</p>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-48 overflow-y-auto mb-3">
                    {pipelineConfigs.map(c => (
                      <button
                        key={c.id}
                        onClick={() => setSelectedConfigId(c.id)}
                        className={`w-full rounded-lg border p-3 text-left transition-all ${selectedConfigId === c.id ? 'border-[#FF6A3D]' : ''}`}
                        style={{ borderColor: selectedConfigId === c.id ? '#FF6A3D' : 'rgba(26,34,56,0.08)', background: selectedConfigId === c.id ? 'rgba(255,106,61,0.03)' : 'transparent' }}
                      >
                        <div className="text-xs font-bold" style={{ color: '#1A2238' }}>{c.pipeline_name}</div>
                        {c.pipeline_description && <p className="text-[10px] mt-0.5 line-clamp-1" style={{ color: '#6b7394' }}>{c.pipeline_description}</p>}
                      </button>
                    ))}
                  </div>
                )}
                <div className="flex gap-2">
                  <button onClick={handleRunPipeline} disabled={!selectedConfigId || pipelineConfigs.length === 0} className="btn-primary flex-1 text-xs">
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" /></svg>
                    Run Pipeline
                  </button>
                  <button onClick={() => setRunMode(null)} className="btn-secondary text-xs">Cancel</button>
                </div>
              </div>
            )}

            {/* JSON Input Modal */}
            {runMode === 'json' && (
              <div className="absolute right-0 top-full z-30 mt-2 w-96 rounded-xl border bg-white p-5 shadow-xl animate-slide-up" style={{ borderColor: 'rgba(26,34,56,0.1)' }}>
                <p className="text-sm font-bold mb-3" style={{ color: '#1A2238' }}>Run from JSON</p>
                <textarea
                  value={jsonInput}
                  onChange={e => { setJsonInput(e.target.value); setJsonError(''); }}
                  rows={8}
                  className="w-full rounded-lg border px-3 py-2 font-mono text-xs mb-2 resize-y"
                  style={{ borderColor: jsonError ? '#dc2626' : 'rgba(26,34,56,0.12)', background: '#0d1117', color: '#c9d1d9' }}
                  placeholder={`{"agents": {"${agentIds[0] || 'agent'}": [...]}}`}
                />
                {jsonError && <p className="text-[10px] text-red-500 mb-2">{jsonError}</p>}
                <div className="flex items-center gap-2 mb-3">
                  <button
                    type="button"
                    onClick={() => setJsonSave(!jsonSave)}
                    className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${jsonSave ? 'bg-emerald-500' : 'bg-zinc-300'}`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${jsonSave ? 'translate-x-4' : 'translate-x-0'}`} />
                  </button>
                  <span className="text-[11px] font-medium" style={{ color: '#6b7394' }}>Save to database</span>
                </div>
                {jsonSave && (
                  <input
                    type="text"
                    value={jsonName}
                    onChange={e => setJsonName(e.target.value)}
                    placeholder="Pipeline name for saved config"
                    className="w-full rounded-lg border px-3 py-2 text-xs mb-3"
                    style={{ borderColor: 'rgba(26,34,56,0.12)' }}
                  />
                )}
                <div className="flex gap-2">
                  <button onClick={handleRunJson} className="btn-primary flex-1 text-xs">
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" /></svg>
                    Run Pipeline
                  </button>
                  <button onClick={() => setRunMode(null)} className="btn-secondary text-xs">Cancel</button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="space-y-4"><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[1,2,3,4].map(i=><div key={i} className="h-28 skeleton" />)}</div><div className="h-64 skeleton" /></div>
      ) : (
        <div className="stagger-children space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="stat-card flex flex-col">
              <div className="stat-icon" style={{ background: 'rgba(255,106,61,0.1)', color: '#FF6A3D' }}><svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" /></svg></div>
              <div className="stat-value flex-1 flex items-end">{totalFindings}</div>
              <div className="stat-label">Total Findings</div>
            </div>
            <div className="stat-card flex flex-col">
              <div className="stat-icon" style={{ background: 'rgba(157,170,242,0.12)', color: '#7580d4' }}><svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.915-3.373a4.5 4.5 0 00-6.364-6.364L4.5 8.25" /></svg></div>
              <div className="stat-value flex-1 flex items-end">{runs.length}</div>
              <div className="stat-label">Total Runs</div>
            </div>
            <div className="stat-card flex flex-col">
              <div className="stat-icon" style={{ background: 'rgba(244,219,125,0.15)', color: '#b8960a' }}><svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg></div>
              <div className="stat-value flex-1 flex items-end">{digests.length}</div>
              <div className="stat-label">Digests</div>
            </div>
            <div className="stat-card flex flex-col">
              <div className="stat-icon" style={{ background: lastRun?.status==='success'?'#ecfdf5':lastRun?.status==='failed'?'#fef2f2':'rgba(26,34,56,0.06)', color: lastRun?.status==='success'?'#059669':lastRun?.status==='failed'?'#dc2626':'#6b7394' }}><svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg></div>
              <div className="stat-value flex-1 flex items-end">{lastRun ? <span className={`badge ${statusColor(lastRun.status)}`}>{lastRun.status==='running' && <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse-dot" />}{lastRun.status.toUpperCase()}</span> : '—'}</div>
              <div className="stat-label">Last Run {lastRun ? formatRelative(lastRun.status === 'running' ? lastRun.started_at : (lastRun.finished_at || lastRun.started_at)) : ''}</div>
            </div>
          </div>

          {runs.length > 0 && (() => {
            const agentTotals: Record<string, { count: number; pages: number; lastStatus: string; lastError?: string }> = {};
            for (const run of runs) {
              if (!run.agent_results) continue;
              for (const key of agentIds) {
                const ar = run.agent_results[key];
                if (!ar) continue;
                if (!agentTotals[key]) agentTotals[key] = { count: 0, pages: 0, lastStatus: ar.status, lastError: ar.error };
                agentTotals[key].count += (ar.count ?? 0);
                agentTotals[key].pages += (ar.pages_processed ?? 0);
              }
            }
            const keys = Object.keys(agentTotals);
            if (keys.length === 0) return null;
            return (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {agentIds.map(key => {
                  const t = agentTotals[key]; if (!t) return null;
                  const failed = t.lastStatus === 'failed';
                  return (
                    <div key={key} className={`glass-card p-4 ${failed ? '!border-red-200' : ''}`}>
                      <div className="flex items-center justify-between">
                        <span className={`px-2 py-0.5 text-[11px] font-bold ${agentBadge(key)}`}>{agentLabel(key)}</span>
                        <span className={`text-[11px] font-bold ${failed?'text-red-500':'text-emerald-600'}`}>{t.lastStatus}</span>
                      </div>
                      <div className="mt-3 flex items-baseline gap-2"><span className="text-xl font-extrabold" style={{ color: '#1A2238' }}>{t.count}</span><span className="text-xs" style={{ color: '#6b7394' }}>findings</span></div>
                      <div className="mt-1 text-[10px]" style={{ color: '#9ba2bc' }}>{t.pages} pages crawled</div>
                      {t.lastError && <p className="mt-1.5 line-clamp-1 text-[11px] text-red-400">{t.lastError}</p>}
                    </div>
                  );
                })}
              </div>
            );
          })()}

          <div className="glass-card overflow-hidden">
            <div className="flex items-center justify-between border-b px-5 py-4" style={{ borderColor: 'rgba(26,34,56,0.06)' }}>
              <h2 className="text-sm font-bold" style={{ color: '#1A2238' }}>Latest Findings</h2>
              <Link href="/findings" className="text-xs font-semibold transition-colors hover:opacity-80" style={{ color: '#FF6A3D' }}>View all &rarr;</Link>
            </div>
            {findings.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon"><svg className="h-6 w-6" style={{ color: '#9DAAF2' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" /></svg></div>
                <p className="text-sm font-medium" style={{ color: '#3d4660' }}>No findings yet</p>
                <p className="text-xs" style={{ color: '#6b7394' }}>Add feeds and run the pipeline to discover insights.</p>
              </div>
            ) : (
              <ul className="divide-y" style={{ '--tw-divide-opacity': '1', '--tw-divide-color': 'rgba(26,34,56,0.05)' } as React.CSSProperties}>
                {findings.map(f => (
                  <li key={f.id} className="group">
                    <a href={f.source_url} target="_blank" rel="noopener noreferrer" className="flex items-start gap-4 px-5 py-4 transition-colors hover:bg-[rgba(157,170,242,0.04)]">
                      <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl" style={{ background: 'rgba(26,34,56,0.04)' }}>
                        <svg className="h-4 w-4 transition-colors group-hover:text-[#FF6A3D]" style={{ color: '#9ba2bc' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" /></svg>
                      </div>
                      <div className="min-w-0 flex-1">
                        <span className="text-sm font-semibold transition-colors group-hover:text-[#FF6A3D] line-clamp-1" style={{ color: '#1A2238' }}>{f.title}</span>
                        <p className="mt-0.5 line-clamp-1 text-xs" style={{ color: '#6b7394' }}>{f.summary_short}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <span className={`px-1.5 py-0.5 text-[10px] font-bold ${agentBadge(f.agent_id)}`}>{agentLabel(f.agent_id)}</span>
                          <span className="rounded-lg px-1.5 py-0.5 text-[10px] font-medium" style={{ background: 'rgba(26,34,56,0.05)', color: '#6b7394' }}>{f.category}</span>
                          <ConfidencePill value={f.confidence} />
                        </div>
                      </div>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex flex-wrap gap-3">
            {downloadPdfUrl ? <a href={downloadPdfUrl} target="_blank" rel="noopener noreferrer" className="btn-secondary"><svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>Download PDF</a> :
            <Link href="/digests" className="btn-secondary"><svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>Download PDF</Link>}
            <Link href="/sources" className="btn-secondary"><svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" /></svg>Manage Pipeline</Link>
            <Link href="/runs" className="btn-secondary"><svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>Run History</Link>
          </div>
        </div>
      )}
    </div>
  );
}
