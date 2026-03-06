'use client';

import { useEffect, useState, useMemo, useCallback } from 'react';
import { api, type FindingSummary, type Run } from '@/lib/api';
import { useMeta } from '@/lib/useMeta';

function startOfDayIST(daysAgo = 0): string {
  const d = new Date();
  const istOffset = 5.5 * 60 * 60 * 1000;
  const istNow = new Date(d.getTime() + istOffset);
  istNow.setUTCHours(0, 0, 0, 0);
  istNow.setUTCDate(istNow.getUTCDate() - daysAgo);
  return new Date(istNow.getTime() - istOffset).toISOString();
}

function toIST(d: string) { return new Date(d).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' }); }
function todayIST() { return new Date().toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' }); }
function yesterdayIST() { const y = new Date(); y.setDate(y.getDate() - 1); return y.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' }); }
function isToday(d: string) { return toIST(d) === todayIST(); }
function isYesterday(d: string) { return toIST(d) === yesterdayIST(); }

export default function AnalyticsPage() {
  const [findings, setFindings] = useState<FindingSummary[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'diff' | 'sota' | 'heatmap'>('diff');
  const [diffFindings, setDiffFindings] = useState<FindingSummary[]>([]);
  const [diffLoading, setDiffLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.findings.list({}), api.runs.list()])
      .then(([f, r]) => { setFindings(f); setRuns(r); })
      .catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setDiffLoading(true);
    api.findings.list({ created_after: startOfDayIST(1), limit: 500 })
      .then(setDiffFindings)
      .catch(() => {})
      .finally(() => setDiffLoading(false));
  }, []);

  const tabs = [
    { id: 'diff' as const, label: 'What Changed', icon: <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" /></svg> },
    { id: 'sota' as const, label: 'SOTA Watch', icon: <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" /></svg> },
    { id: 'heatmap' as const, label: 'Entity Heatmap', icon: <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" /></svg> },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header relative">
        <div className="absolute inset-0 overflow-hidden rounded-2xl">
          <div className="absolute -top-16 -right-16 h-48 w-48 opacity-20" style={{ background: 'radial-gradient(circle, rgba(255,106,61,0.5) 0%, transparent 60%)' }} />
          <div className="absolute bottom-0 left-10 h-28 w-28 opacity-20" style={{ background: 'radial-gradient(circle, rgba(244,219,125,0.5) 0%, transparent 60%)' }} />
          <div className="absolute top-8 right-32 h-20 w-20 opacity-20" style={{ background: 'radial-gradient(circle, rgba(157,170,242,0.5) 0%, transparent 60%)' }} />
        </div>
        <div className="relative"><h1>Analytics</h1><p>Deep-dive: diff viewer, SOTA watch, entity heatmap.</p></div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 rounded-xl border p-1" style={{ borderColor: 'rgba(26,34,56,0.08)', background: '#ffffff' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-xs font-semibold transition-all ${activeTab === t.id ? 'text-white shadow-md' : ''}`}
            style={activeTab === t.id ? { background: '#1A2238' } : { color: '#6b7394' }}>
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {loading ? <div className="h-96 skeleton rounded-2xl" /> : (
        <>
          {activeTab === 'diff' && <DiffViewer findings={diffFindings} loading={diffLoading} />}
          {activeTab === 'sota' && <SOTAWatch findings={findings} runs={runs} />}
          {activeTab === 'heatmap' && <EntityHeatmap findings={findings} />}
        </>
      )}
    </div>
  );
}

/* ============== DIFF VIEWER ============== */
function DiffViewer({ findings, loading }: { findings: FindingSummary[]; loading: boolean }) {
  const { agentLabel } = useMeta();
  const todayFindings = useMemo(() => findings.filter(f => isToday(f.created_at)), [findings]);
  const yesterdayFindings = useMemo(() => findings.filter(f => isYesterday(f.created_at)), [findings]);

  const { added, removed, persisted } = useMemo(() => {
    const yTitles = new Set(yesterdayFindings.map(f => f.title.toLowerCase().trim()));
    const tTitles = new Set(todayFindings.map(f => f.title.toLowerCase().trim()));
    return {
      added: todayFindings.filter(f => !yTitles.has(f.title.toLowerCase().trim())),
      removed: yesterdayFindings.filter(f => !tTitles.has(f.title.toLowerCase().trim())),
      persisted: todayFindings.filter(f => yTitles.has(f.title.toLowerCase().trim())),
    };
  }, [todayFindings, yesterdayFindings]);

  if (loading) return <div className="h-64 skeleton rounded-2xl" />;

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="stat-card"><div className="stat-icon" style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981' }}><span className="text-base font-bold">+</span></div><div className="stat-value">{added.length}</div><div className="stat-label">New Today</div></div>
        <div className="stat-card"><div className="stat-icon" style={{ background: 'rgba(220,38,38,0.08)', color: '#dc2626' }}><span className="text-base font-bold">-</span></div><div className="stat-value">{removed.length}</div><div className="stat-label">Gone from Yesterday</div></div>
        <div className="stat-card"><div className="stat-icon" style={{ background: 'rgba(157,170,242,0.12)', color: '#7580d4' }}><span className="text-base font-bold">=</span></div><div className="stat-value">{persisted.length}</div><div className="stat-label">Persisted</div></div>
      </div>

      {added.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="flex items-center gap-2 border-b px-5 py-3" style={{ borderColor: 'rgba(26,34,56,0.06)' }}>
            <div className="h-2 w-2 rounded-full bg-emerald-500" />
            <h3 className="text-sm font-bold" style={{ color: '#1A2238' }}>Added ({added.length})</h3>
          </div>
          <ul className="divide-y" style={{ '--tw-divide-color': 'rgba(26,34,56,0.04)' } as React.CSSProperties}>
            {added.map(f => (
              <li key={f.id} className="flex items-center gap-3 px-5 py-3">
                <span className="text-emerald-500 text-xs font-bold">+</span>
                <div className="min-w-0 flex-1">
                  <a href={f.source_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:text-[#FF6A3D] line-clamp-1" style={{ color: '#1A2238' }}>{f.title}</a>
                  <p className="line-clamp-1 text-xs" style={{ color: '#9ba2bc' }}>{f.summary_short}</p>
                </div>
                <span className="text-[10px] font-medium" style={{ color: '#6b7394' }}>{agentLabel(f.agent_id)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {removed.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="flex items-center gap-2 border-b px-5 py-3" style={{ borderColor: 'rgba(26,34,56,0.06)' }}>
            <div className="h-2 w-2 rounded-full bg-red-500" />
            <h3 className="text-sm font-bold" style={{ color: '#1A2238' }}>Removed ({removed.length})</h3>
          </div>
          <ul className="divide-y" style={{ '--tw-divide-color': 'rgba(26,34,56,0.04)' } as React.CSSProperties}>
            {removed.map(f => (
              <li key={f.id} className="flex items-center gap-3 px-5 py-3" style={{ opacity: 0.6 }}>
                <span className="text-red-500 text-xs font-bold">-</span>
                <div className="min-w-0 flex-1">
                  <span className="text-sm font-medium line-clamp-1 line-through" style={{ color: '#6b7394' }}>{f.title}</span>
                </div>
                <span className="text-[10px] font-medium" style={{ color: '#9ba2bc' }}>{agentLabel(f.agent_id)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {persisted.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="flex items-center gap-2 border-b px-5 py-3" style={{ borderColor: 'rgba(26,34,56,0.06)' }}>
            <div className="h-2 w-2 rounded-full" style={{ background: '#7580d4' }} />
            <h3 className="text-sm font-bold" style={{ color: '#1A2238' }}>Persisted ({persisted.length})</h3>
          </div>
          <ul className="divide-y" style={{ '--tw-divide-color': 'rgba(26,34,56,0.04)' } as React.CSSProperties}>
            {persisted.map(f => (
              <li key={f.id} className="flex items-center gap-3 px-5 py-3" style={{ opacity: 0.7 }}>
                <span className="text-xs font-bold" style={{ color: '#7580d4' }}>=</span>
                <div className="min-w-0 flex-1">
                  <a href={f.source_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium hover:text-[#FF6A3D] line-clamp-1" style={{ color: '#1A2238' }}>{f.title}</a>
                  <p className="line-clamp-1 text-xs" style={{ color: '#9ba2bc' }}>{f.summary_short}</p>
                </div>
                <span className="text-[10px] font-medium" style={{ color: '#6b7394' }}>{agentLabel(f.agent_id)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {added.length === 0 && removed.length === 0 && persisted.length === 0 && (
        <div className="glass-card"><div className="empty-state"><p className="text-sm font-semibold" style={{ color: '#3d4660' }}>No changes detected</p><p className="text-xs" style={{ color: '#6b7394' }}>Run the pipeline on consecutive days to see diffs.</p></div></div>
      )}
    </div>
  );
}

/* ============== SOTA WATCH ============== */
function SOTAWatch({ findings, runs }: { findings: FindingSummary[]; runs: Run[] }) {
  const { agentLabel, agentIds } = useMeta();
  const benchmarkFindings = findings.filter(f => f.category === 'benchmark');
  const sortedRuns = [...runs].sort((a, b) => new Date(a.started_at || '').getTime() - new Date(b.started_at || '').getTime());
  const runData = sortedRuns.map(r => ({
    id: r.id,
    date: r.started_at ? new Date(r.started_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', timeZone: 'Asia/Kolkata' }) : `#${r.id}`,
    count: r.findings_count,
  }));
  const maxCount = Math.max(1, ...runData.map(r => r.count));

  return (
    <div className="space-y-5">
      {/* Chart */}
      <div className="glass-card p-5">
        <h3 className="text-sm font-bold mb-4" style={{ color: '#1A2238' }}>Total Findings Over Runs</h3>
        {runData.length === 0 ? (
          <div className="empty-state py-12"><p className="text-sm" style={{ color: '#6b7394' }}>No run data available yet.</p></div>
        ) : (
          <div className="flex items-end gap-2" style={{ height: '180px' }}>
            {runData.map((r, i) => (
              <div key={r.id} className="flex flex-1 flex-col items-center gap-1">
                <span className="text-[10px] font-bold" style={{ color: '#1A2238' }}>{r.count}</span>
                <div className="w-full rounded-t-lg transition-all duration-500" style={{
                  height: `${Math.max(8, (r.count / maxCount) * 140)}px`,
                  background: r.count > 0 ? 'linear-gradient(180deg, #FF6A3D, #F4DB7D)' : 'rgba(26,34,56,0.06)',
                  animationDelay: `${i * 0.1}s`,
                }} />
                <span className="text-[9px] font-medium" style={{ color: '#9ba2bc' }}>{r.date}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Benchmark findings list */}
      <div className="glass-card overflow-hidden">
        <div className="flex items-center justify-between border-b px-5 py-3" style={{ borderColor: 'rgba(26,34,56,0.06)' }}>
          <h3 className="text-sm font-bold" style={{ color: '#1A2238' }}>SOTA Benchmark Findings ({benchmarkFindings.length})</h3>
        </div>
        {benchmarkFindings.length === 0 ? (
          <div className="empty-state py-8"><p className="text-xs" style={{ color: '#6b7394' }}>No benchmark findings yet. Add leaderboard URLs as sources.</p></div>
        ) : (
          <ul className="divide-y" style={{ '--tw-divide-color': 'rgba(26,34,56,0.04)' } as React.CSSProperties}>
            {benchmarkFindings.map(f => (
              <li key={f.id}>
                <a href={f.source_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-[rgba(157,170,242,0.04)]">
                  <svg className="h-4 w-4 shrink-0" style={{ color: '#F4DB7D' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 01-.982-3.172M9.497 14.25a7.454 7.454 0 00.981-3.172M5.25 4.236c-.996.144-1.708.412-2.237.803-.53.392-.774.898-.774 1.432 0 .534.245 1.04.774 1.432.529.39 1.24.659 2.237.803M18.75 4.236c.997.144 1.708.412 2.237.803.53.392.775.898.775 1.432 0 .534-.245 1.04-.775 1.432-.529.39-1.24.659-2.237.803" /></svg>
                  <div className="min-w-0 flex-1">
                    <span className="text-sm font-medium line-clamp-1 hover:text-[#FF6A3D]" style={{ color: '#1A2238' }}>{f.title}</span>
                    <p className="line-clamp-1 text-xs" style={{ color: '#6b7394' }}>{f.summary_short}</p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-0.5">
                    <span className="text-[10px] font-bold" style={{ color: '#FF6A3D' }}>{f.confidence.toFixed(2)}</span>
                    {f.impact_score != null && <span className="text-[9px] font-bold" style={{ color: '#b8860b' }}>Impact {f.impact_score.toFixed(2)}</span>}
                  </div>
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/* ============== ENTITY HEATMAP ============== */
function EntityHeatmap({ findings }: { findings: FindingSummary[] }) {
  const { matrix, publishers, topics, maxCount } = useMemo(() => {
    const pubSet = new Set<string>();
    const topicSet = new Set<string>();
    const countMap: Record<string, number> = {};

    for (const f of findings) {
      const pub = f.publisher || f.agent_id;
      pubSet.add(pub);
      for (const tag of (f.tags || []).slice(0, 5)) {
        topicSet.add(tag);
        const key = `${pub}|||${tag}`;
        countMap[key] = (countMap[key] || 0) + 1;
      }
      if ((f.tags || []).length === 0) {
        const cat = f.category || 'other';
        topicSet.add(cat);
        const key = `${pub}|||${cat}`;
        countMap[key] = (countMap[key] || 0) + 1;
      }
    }
    const publishers = Array.from(pubSet).sort();
    const topics = Array.from(topicSet).sort();
    let maxCount = 0;
    const matrix: number[][] = publishers.map(p => topics.map(t => { const c = countMap[`${p}|||${t}`] || 0; if (c > maxCount) maxCount = c; return c; }));
    return { matrix, publishers, topics, maxCount };
  }, [findings]);

  const cellColor = (count: number) => {
    if (count === 0) return 'rgba(26,34,56,0.03)';
    const intensity = count / Math.max(1, maxCount);
    if (intensity < 0.25) return `rgba(255,106,61,0.12)`;
    if (intensity < 0.5) return `rgba(255,106,61,0.25)`;
    if (intensity < 0.75) return `rgba(255,106,61,0.45)`;
    return `rgba(255,106,61,0.7)`;
  };
  const textColor = (count: number) => {
    const intensity = count / Math.max(1, maxCount);
    return intensity >= 0.5 ? '#ffffff' : '#1A2238';
  };

  if (publishers.length === 0 || topics.length === 0) {
    return <div className="glass-card"><div className="empty-state"><p className="text-sm font-semibold" style={{ color: '#3d4660' }}>Not enough data for heatmap</p><p className="text-xs" style={{ color: '#6b7394' }}>Run the pipeline with multiple sources to generate entity-topic data.</p></div></div>;
  }

  return (
    <div className="glass-card overflow-x-auto p-5">
      <h3 className="text-sm font-bold mb-4" style={{ color: '#1A2238' }}>Providers vs Topics</h3>
      <table className="w-full text-[11px]">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 px-3 py-2 text-left font-semibold" style={{ color: '#6b7394', background: '#ffffff' }}>Provider / Topic</th>
            {topics.map(t => <th key={t} className="px-2 py-2 text-center font-semibold" style={{ color: '#6b7394', maxWidth: '80px' }}><span className="line-clamp-1">{t}</span></th>)}
          </tr>
        </thead>
        <tbody>
          {publishers.map((pub, pi) => (
            <tr key={pub}>
              <td className="sticky left-0 z-10 whitespace-nowrap px-3 py-2 font-semibold" style={{ color: '#1A2238', background: '#ffffff' }}>{pub}</td>
              {matrix[pi].map((count, ti) => (
                <td key={ti} className="px-2 py-2 text-center">
                  <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-lg text-[10px] font-bold transition-all"
                    style={{ background: cellColor(count), color: textColor(count) }}>
                    {count || ''}
                  </div>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-4 flex items-center gap-3 text-[10px]" style={{ color: '#9ba2bc' }}>
        <span>Intensity:</span>
        <div className="flex gap-1">
          {[0.12, 0.25, 0.45, 0.7].map((op, i) => (
            <div key={i} className="h-4 w-8 rounded" style={{ background: `rgba(255,106,61,${op})` }} />
          ))}
        </div>
        <span>Low → High</span>
      </div>
    </div>
  );
}
