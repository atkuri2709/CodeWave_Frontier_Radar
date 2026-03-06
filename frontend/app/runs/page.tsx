'use client';

import { useEffect, useState } from 'react';
import { api, type Run, type LogEntry } from '@/lib/api';
import Link from 'next/link';

const AGENT_LABELS: Record<string, string> = { competitors: 'Competitors', model_providers: 'Model Providers', research: 'Research', hf_benchmarks: 'Benchmarks' };
const AGENT_BADGE: Record<string, string> = { competitors: 'agent-orange', model_providers: 'agent-lavender', research: 'agent-gold', hf_benchmarks: 'agent-navy' };
function statusColor(s: string) { return s === 'success' ? 'badge-emerald' : s === 'running' ? 'badge-amber' : s === 'failed' || s === 'partial' ? 'badge-red' : 'badge-zinc'; }

const LOG_LEVEL_STYLE: Record<string, { bg: string; color: string }> = {
  DEBUG: { bg: 'rgba(26,34,56,0.05)', color: '#9ba2bc' },
  INFO: { bg: 'rgba(16,185,129,0.08)', color: '#059669' },
  WARNING: { bg: 'rgba(245,158,11,0.1)', color: '#d97706' },
  ERROR: { bg: 'rgba(220,38,38,0.08)', color: '#dc2626' },
  CRITICAL: { bg: 'rgba(220,38,38,0.15)', color: '#991b1b' },
};

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedRun, setExpandedRun] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<Record<number, 'agents' | 'logs'>>({});
  const [runLogs, setRunLogs] = useState<Record<number, LogEntry[]>>({});
  const [logsLoading, setLogsLoading] = useState<Record<number, boolean>>({});

  useEffect(() => { api.runs.list().then(setRuns).catch(() => {}).finally(() => setLoading(false)); }, []);

  const formatDate = (d: string | null) => d ? new Date(d).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—';
  const formatDuration = (s: string | null, e: string | null) => { if (!s||!e) return '—'; const ms = new Date(e).getTime()-new Date(s).getTime(); if (ms<1000) return `${ms}ms`; if (ms<60000) return `${(ms/1000).toFixed(1)}s`; return `${Math.floor(ms/60000)}m ${Math.round((ms%60000)/1000)}s`; };
  const formatLogTime = (ts: string) => new Date(ts).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 } as Intl.DateTimeFormatOptions);

  const handleToggleRun = (runId: number) => {
    setExpandedRun(expandedRun === runId ? null : runId);
    if (!activeTab[runId]) {
      setActiveTab(prev => ({ ...prev, [runId]: 'agents' }));
    }
  };

  const [logFilter, setLogFilter] = useState<Record<number, string>>({});

  const handleShowLogs = async (runId: number, forceRefresh = false) => {
    setActiveTab(prev => ({ ...prev, [runId]: 'logs' }));
    if (runLogs[runId] && !forceRefresh) return;
    setLogsLoading(prev => ({ ...prev, [runId]: true }));
    try {
      const logs = await api.logs.forRun(runId);
      setRunLogs(prev => ({ ...prev, [runId]: logs }));
    } catch {
      setRunLogs(prev => ({ ...prev, [runId]: [] }));
    } finally {
      setLogsLoading(prev => ({ ...prev, [runId]: false }));
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header relative">
        <div className="absolute inset-0 overflow-hidden rounded-2xl"><div className="absolute -top-16 -right-16 h-48 w-48 opacity-20" style={{ background: 'radial-gradient(circle, rgba(244,219,125,0.5) 0%, transparent 60%)' }} /></div>
        <div className="relative"><h1>Run History</h1><p>Pipeline execution log with per-agent breakdown and live logs.</p></div>
      </div>

      {loading ? <div className="space-y-3">{[1,2,3,4,5].map(i => <div key={i} className="h-20 skeleton" />)}</div> : runs.length === 0 ? (
        <div className="glass-card"><div className="empty-state">
          <div className="empty-state-icon"><svg className="h-6 w-6" style={{ color: '#9DAAF2' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg></div>
          <p className="text-sm font-semibold" style={{ color: '#3d4660' }}>No runs yet</p>
          <p className="text-xs" style={{ color: '#6b7394' }}>Trigger a pipeline run from the Dashboard.</p>
          <Link href="/" className="btn-primary mt-3">Go to Dashboard</Link>
        </div></div>
      ) : (
        <div className="stagger-children space-y-3">
          {runs.map(r => (
            <div key={r.id} className="glass-card overflow-hidden">
              <button onClick={() => handleToggleRun(r.id)} className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-[rgba(157,170,242,0.04)]">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl font-mono text-xs" style={{ background: 'rgba(26,34,56,0.05)', color: '#6b7394' }}>#{r.id}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    {r.pipeline_name && <span className="text-xs font-bold" style={{ color: '#1A2238' }}>{r.pipeline_name}</span>}
                    <span className={`badge ${statusColor(r.status)}`}>{r.status==='running'&&<span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse-dot" />}{r.status}</span>
                    <span className="text-xs" style={{ color: '#9ba2bc' }}>{r.trigger}</span>
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs" style={{ color: '#9ba2bc' }}><span>{formatDate(r.started_at)}</span><span style={{ color: '#d0d3de' }}>&middot;</span><span>{formatDuration(r.started_at, r.finished_at)}</span></div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right"><div className="text-lg font-extrabold" style={{ color: '#1A2238' }}>{r.findings_count}</div><div className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: '#9ba2bc' }}>findings</div></div>
                  <svg className={`h-4 w-4 transition-transform duration-200 ${expandedRun===r.id?'rotate-180':''}`} style={{ color: '#9ba2bc' }} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>
                </div>
              </button>

              {expandedRun === r.id && (
                <div className="animate-slide-up border-t" style={{ borderColor: 'rgba(26,34,56,0.06)' }}>
                  {/* Tab bar */}
                  <div className="flex border-b px-5" style={{ borderColor: 'rgba(26,34,56,0.06)' }}>
                    <button
                      onClick={() => setActiveTab(prev => ({ ...prev, [r.id]: 'agents' }))}
                      className="relative px-4 py-2.5 text-xs font-semibold transition-colors"
                      style={{ color: (activeTab[r.id] || 'agents') === 'agents' ? '#1A2238' : '#9ba2bc' }}
                    >
                      Agent Results
                      {(activeTab[r.id] || 'agents') === 'agents' && <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full" style={{ background: '#FF6A3D' }} />}
                    </button>
                    <button
                      onClick={() => handleShowLogs(r.id)}
                      className="relative flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold transition-colors"
                      style={{ color: activeTab[r.id] === 'logs' ? '#1A2238' : '#9ba2bc' }}
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0021 18V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v12a2.25 2.25 0 002.25 2.25z" /></svg>
                      Logs
                      {activeTab[r.id] === 'logs' && <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full" style={{ background: '#FF6A3D' }} />}
                    </button>
                  </div>

                  {/* Agent Results Tab */}
                  {(activeTab[r.id] || 'agents') === 'agents' && (
                    <div className="px-5 py-4">
                      {r.agent_results ? (
                        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                          {(['competitors','model_providers','research','hf_benchmarks'] as const).map(key => {
                            const ar = r.agent_results?.[key]; if (!ar) return null;
                            const failed = ar.status === 'failed';
                            return (
                              <div key={key} className={`rounded-xl border p-3 ${failed?'border-red-200 bg-red-50':''}`} style={failed?{}:{borderColor:'rgba(26,34,56,0.06)',background:'rgba(26,34,56,0.02)'}}>
                                <div className="flex items-center justify-between"><span className={`px-1.5 py-0.5 text-[10px] font-bold ${AGENT_BADGE[key]}`}>{AGENT_LABELS[key]}</span><span className={`text-[10px] font-bold ${failed?'text-red-500':'text-emerald-600'}`}>{ar.status}</span></div>
                                <div className="mt-2 text-xs" style={{ color: '#6b7394' }}><span className="font-bold" style={{ color: '#1A2238' }}>{ar.count??0}</span> findings &middot; <span className="font-bold" style={{ color: '#1A2238' }}>{ar.pages_processed??0}</span> pages</div>
                                {ar.error && <p className="mt-1 line-clamp-2 text-[10px] text-red-400">{ar.error}</p>}
                              </div>
                            );
                          })}
                        </div>
                      ) : <p className="text-xs" style={{ color: '#9ba2bc' }}>No agent details available.</p>}
                      {r.error_message && <div className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-600">{r.error_message}</div>}
                    </div>
                  )}

                  {/* Logs Tab */}
                  {activeTab[r.id] === 'logs' && (
                    <div className="px-5 py-4">
                      {logsLoading[r.id] ? (
                        <div className="space-y-2">{[1,2,3,4].map(i => <div key={i} className="h-6 skeleton" />)}</div>
                      ) : !runLogs[r.id] || runLogs[r.id].length === 0 ? (
                        <div className="py-6 text-center">
                          <p className="text-xs font-medium" style={{ color: '#6b7394' }}>No logs available for this run.</p>
                          <p className="text-[10px] mt-1" style={{ color: '#9ba2bc' }}>Logs are captured when the pipeline executes.</p>
                          <button onClick={() => handleShowLogs(r.id, true)} className="btn-ghost text-xs mt-2">Refresh Logs</button>
                        </div>
                      ) : (() => {
                        const filter = logFilter[r.id] || 'ALL';
                        const filtered = filter === 'ALL' ? runLogs[r.id] : runLogs[r.id].filter(l => l.level === filter);
                        const counts = runLogs[r.id].reduce((acc, l) => { acc[l.level] = (acc[l.level] || 0) + 1; return acc; }, {} as Record<string, number>);
                        return (
                          <div>
                            <div className="mb-2 flex items-center gap-2 flex-wrap">
                              <span className="text-[10px] font-semibold" style={{ color: '#6b7394' }}>Filter:</span>
                              {['ALL', 'INFO', 'WARNING', 'ERROR', 'DEBUG'].map(lvl => (
                                <button
                                  key={lvl}
                                  onClick={() => setLogFilter(prev => ({ ...prev, [r.id]: lvl }))}
                                  className="rounded px-2 py-0.5 text-[10px] font-bold transition-colors"
                                  style={{
                                    background: filter === lvl ? (lvl === 'ERROR' ? 'rgba(220,38,38,0.15)' : lvl === 'WARNING' ? 'rgba(245,158,11,0.15)' : 'rgba(157,170,242,0.2)') : 'rgba(26,34,56,0.04)',
                                    color: filter === lvl ? (lvl === 'ERROR' ? '#dc2626' : lvl === 'WARNING' ? '#d97706' : '#1A2238') : '#9ba2bc',
                                  }}
                                >
                                  {lvl} {lvl !== 'ALL' && counts[lvl] ? `(${counts[lvl]})` : lvl === 'ALL' ? `(${runLogs[r.id].length})` : ''}
                                </button>
                              ))}
                              <button onClick={() => handleShowLogs(r.id, true)} className="ml-auto rounded px-2 py-0.5 text-[10px] font-bold transition-colors hover:bg-[rgba(157,170,242,0.1)]" style={{ color: '#6b7394' }}>
                                <svg className="inline h-3 w-3 mr-0.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" /></svg>
                                Refresh
                              </button>
                            </div>
                            <div className="max-h-[500px] overflow-y-auto rounded-xl border" style={{ borderColor: 'rgba(26,34,56,0.08)', background: '#0d1117' }}>
                              <div className="p-3 space-y-px font-mono text-[11px] leading-relaxed">
                                {filtered.map(log => {
                                  const style = LOG_LEVEL_STYLE[log.level] || LOG_LEVEL_STYLE.INFO;
                                  return (
                                    <div key={log.id} className="flex gap-2 rounded px-2 py-0.5 hover:bg-[rgba(255,255,255,0.03)]">
                                      <span className="shrink-0 tabular-nums" style={{ color: '#484f58' }}>{formatLogTime(log.timestamp)}</span>
                                      <span
                                        className="shrink-0 rounded px-1.5 py-px text-[10px] font-bold uppercase"
                                        style={{ background: style.bg, color: style.color, minWidth: '52px', textAlign: 'center' }}
                                      >
                                        {log.level}
                                      </span>
                                      {log.logger_name && (
                                        <span className="shrink-0" style={{ color: '#58a6ff' }}>
                                          [{log.logger_name.replace('app.', '')}]
                                        </span>
                                      )}
                                      <span className="break-all" style={{ color: log.level === 'ERROR' || log.level === 'CRITICAL' ? '#f85149' : '#c9d1d9' }}>
                                        {log.message}
                                      </span>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                            <div className="mt-1 text-[10px] text-right" style={{ color: '#6b7394' }}>
                              Showing {filtered.length} of {runLogs[r.id].length} log entries
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
