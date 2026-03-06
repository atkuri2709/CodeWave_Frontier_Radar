'use client';

import { useEffect, useState, useMemo } from 'react';
import { api, type FindingSummary } from '@/lib/api';
import { useMeta } from '@/lib/useMeta';

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.75 ? 'text-emerald-600' : value >= 0.55 ? 'text-amber-600' : value >= 0.35 ? 'text-orange-600' : 'text-red-600';
  const bg = value >= 0.75 ? 'bg-emerald-500' : value >= 0.55 ? 'bg-amber-500' : value >= 0.35 ? 'bg-orange-500' : 'bg-red-500';
  const label = value >= 0.75 ? 'High' : value >= 0.55 ? 'Medium' : value >= 0.35 ? 'Low' : 'Very Low';
  return (<span className={`flex items-center gap-2 text-xs font-medium ${color}`}><span className="confidence-meter"><span className={`confidence-fill ${bg}`} style={{ width: `${pct}%` }} /></span>{pct}% {label}</span>);
}

function toIST(d: string) { return new Date(d).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' }); }
function todayIST() { return new Date().toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' }); }
function yesterdayIST() { const y = new Date(); y.setDate(y.getDate() - 1); return y.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' }); }
function isToday(d: string) { return toIST(d) === todayIST(); }
function isYesterday(d: string) { return toIST(d) === yesterdayIST(); }

export default function FindingsPage() {
  const { agents, categories, agentBadge, agentLabel } = useMeta();
  const AGENTS = [{ value: '', label: 'All Agents' }, ...agents.map(a => ({ value: a.id, label: a.label }))];
  const CATEGORIES = [{ value: '', label: 'All Categories' }, ...categories.map(c => ({ value: c.id, label: c.label }))];

  const [findings, setFindings] = useState<FindingSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [agentFilter, setAgentFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [entityFilter, setEntityFilter] = useState('');
  const [publisherFilter, setPublisherFilter] = useState('');
  const [tagFilter, setTagFilter] = useState('');
  const [search, setSearch] = useState('');
  const [diffMode, setDiffMode] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.findings.list({ agent_id: agentFilter || undefined, category: categoryFilter || undefined })
      .then(setFindings).catch(() => {}).finally(() => setLoading(false));
  }, [agentFilter, categoryFilter]);

  const allEntities = useMemo(() => Array.from(new Set(findings.flatMap(f => f.entities || []))).sort(), [findings]);
  const allPublishers = useMemo(() => Array.from(new Set(findings.map(f => f.publisher).filter(Boolean) as string[])).sort(), [findings]);
  const allTags = useMemo(() => Array.from(new Set(findings.flatMap(f => f.tags || []))).sort(), [findings]);

  const filtered = useMemo(() => {
    let result = findings;
    if (search.trim()) result = result.filter(f => f.title.toLowerCase().includes(search.toLowerCase()) || f.summary_short.toLowerCase().includes(search.toLowerCase()));
    if (entityFilter) result = result.filter(f => (f.entities || []).includes(entityFilter));
    if (publisherFilter) result = result.filter(f => f.publisher === publisherFilter);
    if (tagFilter) result = result.filter(f => (f.tags || []).includes(tagFilter));
    return result;
  }, [findings, search, entityFilter, publisherFilter, tagFilter]);

  const todayFindings = useMemo(() => filtered.filter(f => isToday(f.created_at)), [filtered]);
  const yesterdayFindings = useMemo(() => filtered.filter(f => isYesterday(f.created_at)), [filtered]);
  const newToday = useMemo(() => {
    const yTitles = new Set(yesterdayFindings.map(f => f.title));
    return todayFindings.filter(f => !yTitles.has(f.title));
  }, [todayFindings, yesterdayFindings]);

  const hasActiveFilters = !!(agentFilter || categoryFilter || search || entityFilter || publisherFilter || tagFilter);
  const clearFilters = () => { setAgentFilter(''); setCategoryFilter(''); setSearch(''); setEntityFilter(''); setPublisherFilter(''); setTagFilter(''); };

  const renderFinding = (f: FindingSummary, isNew?: boolean) => (
    <a key={f.id} href={f.source_url} target="_blank" rel="noopener noreferrer" className="glass-card group flex items-start gap-4 p-5">
      <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors" style={{ background: isNew ? 'rgba(255,106,61,0.08)' : 'rgba(26,34,56,0.04)' }}>
        {isNew ? (
          <svg className="h-5 w-5" style={{ color: '#FF6A3D' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" /></svg>
        ) : (
          <svg className="h-5 w-5 transition-colors group-hover:text-[#FF6A3D]" style={{ color: '#9ba2bc' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" /></svg>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold transition-colors group-hover:text-[#FF6A3D] line-clamp-1" style={{ color: '#1A2238' }}>{f.title}</h3>
          {isNew && <span className="shrink-0 rounded-md px-1.5 py-0.5 text-[9px] font-bold uppercase" style={{ background: 'rgba(255,106,61,0.1)', color: '#FF6A3D' }}>New</span>}
        </div>
        <p className="mt-1 line-clamp-2 text-xs leading-relaxed" style={{ color: '#6b7394' }}>{f.summary_short}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className={`px-1.5 py-0.5 text-[10px] font-bold ${agentBadge(f.agent_id)}`}>{agentLabel(f.agent_id)}</span>
          <span className="rounded-lg px-1.5 py-0.5 text-[10px] font-medium" style={{ background: 'rgba(26,34,56,0.05)', color: '#6b7394' }}>{f.category}</span>
          {f.publisher && <span className="rounded-lg px-1.5 py-0.5 text-[10px] font-medium" style={{ background: 'rgba(157,170,242,0.08)', color: '#4c5aad' }}>{f.publisher}</span>}
          <ConfidenceBadge value={f.confidence} />
          <span className="text-[10px]" style={{ color: '#9ba2bc' }}>{new Date(f.created_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', timeZone: 'Asia/Kolkata' })}</span>
        </div>
        {(f.entities?.length > 0 || f.tags?.length > 0) && (
          <div className="mt-2 flex flex-wrap gap-1">
            {f.entities?.slice(0, 4).map((e, i) => <span key={`e-${i}`} className="rounded px-1.5 py-0.5 text-[9px] font-medium" style={{ background: 'rgba(244,219,125,0.12)', color: '#92700c' }}>{e}</span>)}
            {f.tags?.slice(0, 3).map((t, i) => <span key={`t-${i}`} className="rounded px-1.5 py-0.5 text-[9px] font-medium" style={{ background: 'rgba(26,34,56,0.04)', color: '#6b7394' }}>{t}</span>)}
          </div>
        )}
      </div>
    </a>
  );

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header relative">
        <div className="absolute inset-0 overflow-hidden rounded-2xl"><div className="absolute -top-16 -right-16 h-48 w-48 opacity-20" style={{ background: 'radial-gradient(circle, rgba(157,170,242,0.6) 0%, transparent 60%)' }} /><div className="absolute bottom-0 left-10 h-28 w-28 opacity-20" style={{ background: 'radial-gradient(circle, rgba(244,219,125,0.5) 0%, transparent 60%)' }} /></div>
        <div className="relative flex items-center justify-between">
          <div><h1>Findings Explorer</h1><p>Filter by entity, provider, topic. Compare with yesterday.</p></div>
          <button onClick={() => setDiffMode(!diffMode)} className={`btn-secondary text-xs ${diffMode ? '!border-[#FF6A3D] !text-[#FF6A3D]' : ''}`}>
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" /></svg>
            {diffMode ? 'Exit Diff View' : 'Compare Yesterday'}
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="glass-card space-y-3 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1 sm:max-w-xs">
            <svg className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" style={{ color: '#9ba2bc' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
            <input type="search" placeholder="Search findings..." value={search} onChange={e => setSearch(e.target.value)} className="input-field pl-9" />
          </div>
          <select value={agentFilter} onChange={e => setAgentFilter(e.target.value)} className="input-field w-full sm:w-44">{AGENTS.map(o => <option key={o.value || 'all'} value={o.value}>{o.label}</option>)}</select>
          <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)} className="input-field w-full sm:w-40">{CATEGORIES.map(o => <option key={o.value || 'all'} value={o.value}>{o.label}</option>)}</select>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <select value={entityFilter} onChange={e => setEntityFilter(e.target.value)} className="input-field w-full sm:w-48">
            <option value="">All Entities</option>
            {allEntities.map(e => <option key={e} value={e}>{e}</option>)}
          </select>
          <select value={publisherFilter} onChange={e => setPublisherFilter(e.target.value)} className="input-field w-full sm:w-44">
            <option value="">All Publishers</option>
            {allPublishers.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <select value={tagFilter} onChange={e => setTagFilter(e.target.value)} className="input-field w-full sm:w-40">
            <option value="">All Topics</option>
            {allTags.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          {hasActiveFilters && (
            <button onClick={clearFilters} className="btn-ghost text-xs" style={{ color: '#FF6A3D' }}>
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
              Clear all
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">{[1,2,3,4,5,6].map(i => <div key={i} className="h-28 skeleton" />)}</div>
      ) : diffMode ? (
        /* ====== DIFF VIEW ====== */
        <div className="space-y-6">
          {newToday.length > 0 && (
            <div>
              <div className="mb-3 flex items-center gap-2">
                <div className="h-2 w-2 rounded-full" style={{ background: '#FF6A3D' }} />
                <h2 className="text-sm font-bold" style={{ color: '#1A2238' }}>New Today ({newToday.length})</h2>
                <span className="text-[10px]" style={{ color: '#9ba2bc' }}>Not seen yesterday</span>
              </div>
              <div className="stagger-children space-y-3">{newToday.map(f => renderFinding(f, true))}</div>
            </div>
          )}
          {yesterdayFindings.length > 0 && (
            <div>
              <div className="mb-3 flex items-center gap-2">
                <div className="h-2 w-2 rounded-full" style={{ background: '#9ba2bc' }} />
                <h2 className="text-sm font-bold" style={{ color: '#1A2238' }}>Yesterday ({yesterdayFindings.length})</h2>
              </div>
              <div className="stagger-children space-y-3" style={{ opacity: 0.7 }}>{yesterdayFindings.map(f => renderFinding(f, false))}</div>
            </div>
          )}
          {newToday.length === 0 && yesterdayFindings.length === 0 && (
            <div className="glass-card"><div className="empty-state">
              <p className="text-sm font-semibold" style={{ color: '#3d4660' }}>No data for diff comparison</p>
              <p className="text-xs" style={{ color: '#6b7394' }}>Need findings from both today and yesterday.</p>
            </div></div>
          )}
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-card"><div className="empty-state">
          <div className="empty-state-icon"><svg className="h-6 w-6" style={{ color: '#9DAAF2' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" /></svg></div>
          <p className="text-sm font-semibold" style={{ color: '#3d4660' }}>{findings.length === 0 ? 'No findings yet' : 'No findings match your filters'}</p>
          <p className="text-xs" style={{ color: '#6b7394' }}>{findings.length === 0 ? 'Run the pipeline or add sources.' : 'Try adjusting your search or filters.'}</p>
        </div></div>
      ) : (
        <div className="stagger-children space-y-3">{filtered.map(f => renderFinding(f))}</div>
      )}
    </div>
  );
}
