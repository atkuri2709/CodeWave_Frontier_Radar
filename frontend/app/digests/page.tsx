'use client';

import { useEffect, useState, useMemo } from 'react';
import { api, type Digest } from '@/lib/api';
import { useToast } from '../components/Toast';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
function isValidEmail(s: string) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s.trim()); }

export default function DigestsPage() {
  const [digests, setDigests] = useState<Digest[]>([]);
  const [loading, setLoading] = useState(true);
  const [recipients, setRecipients] = useState<string[]>([]);
  const [recipientsLoading, setRecipientsLoading] = useState(true);
  const [newEmail, setNewEmail] = useState('');
  const [saving, setSaving] = useState(false);
  const [recipientsSaved, setRecipientsSaved] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const toast = useToast();

  useEffect(() => {
    api.digests.list().then(setDigests).catch(() => {}).finally(() => setLoading(false));
    api.emailRecipients.list().then(setRecipients).catch(() => setRecipients([])).finally(() => setRecipientsLoading(false));
  }, []);

  const filteredDigests = useMemo(() => {
    if (!searchQuery.trim()) return digests;
    const q = searchQuery.toLowerCase();
    return digests.filter(d =>
      (d.executive_summary || '').toLowerCase().includes(q) ||
      `digest #${d.id}`.includes(q) ||
      `run #${d.run_id}`.includes(q) ||
      (d.created_at && new Date(d.created_at).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata' }).includes(q))
    );
  }, [digests, searchQuery]);

  const addEmail = () => { const e = newEmail.trim(); if (!e||!isValidEmail(e)||recipients.includes(e)) return; setRecipients([...recipients, e]); setNewEmail(''); };
  const removeEmail = (email: string) => setRecipients(recipients.filter(r => r !== email));
  const saveRecipients = async () => {
    setSaving(true); setRecipientsSaved(false);
    try { const u = await api.emailRecipients.update(recipients); setRecipients(u); setRecipientsSaved(true); setTimeout(() => setRecipientsSaved(false), 3000); toast.show('Recipients saved!', 'success'); }
    catch { toast.show('Failed to save recipients.', 'error'); } finally { setSaving(false); }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header relative">
        <div className="absolute inset-0 overflow-hidden rounded-2xl"><div className="absolute -top-16 -right-16 h-48 w-48 opacity-20" style={{ background: 'radial-gradient(circle, rgba(255,106,61,0.5) 0%, transparent 60%)' }} /><div className="absolute bottom-0 left-10 h-28 w-28 opacity-20" style={{ background: 'radial-gradient(circle, rgba(244,219,125,0.4) 0%, transparent 60%)' }} /></div>
        <div className="relative"><h1>Digest Archive</h1><p>Download past PDF digests, search summaries, manage email recipients.</p></div>
      </div>

      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl" style={{ background: 'rgba(157,170,242,0.12)', color: '#7580d4' }}>
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" /></svg>
          </div>
          <div><h2 className="text-sm font-bold" style={{ color: '#1A2238' }}>Email Recipients</h2><p className="text-[11px]" style={{ color: '#9ba2bc' }}>Who receives the daily digest PDF via email.</p></div>
        </div>
        {recipientsLoading ? <div className="h-16 skeleton" /> : (<>
          <div className="flex gap-2"><input type="email" placeholder="email@example.com" value={newEmail} onChange={e => setNewEmail(e.target.value)} onKeyDown={e => e.key==='Enter'&&(e.preventDefault(),addEmail())} className="input-field min-w-0 max-w-xs" /><button type="button" onClick={addEmail} className="btn-primary shrink-0 text-xs">Add</button></div>
          {recipients.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {recipients.map(email => (
                <span key={email} className="flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium" style={{ borderColor: 'rgba(26,34,56,0.08)', background: 'rgba(26,34,56,0.02)', color: '#3d4660' }}>
                  {email}
                  <button onClick={() => removeEmail(email)} className="ml-1 transition-colors hover:text-red-500" style={{ color: '#9ba2bc' }}><svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg></button>
                </span>
              ))}
            </div>
          )}
          {recipients.length > 0 && <div className="mt-4 flex items-center gap-3"><button onClick={saveRecipients} disabled={saving} className="btn-primary text-xs">{saving?'Saving...':'Save Recipients'}</button>{recipientsSaved && <span className="flex items-center gap-1 text-xs text-emerald-600"><svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>Saved</span>}</div>}
          {recipients.length === 0 && <p className="mt-2 text-xs" style={{ color: '#9ba2bc' }}>No recipients configured.</p>}
        </>)}
      </div>

      {/* Search digests */}
      {digests.length > 0 && (
        <div className="glass-card flex items-center gap-3 p-4">
          <svg className="h-4 w-4 shrink-0" style={{ color: '#9ba2bc' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" /></svg>
          <input type="search" placeholder="Search digests by summary, date, ID..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="input-field !shadow-none !border-none !bg-transparent !p-0 flex-1" />
          {searchQuery && (
            <button onClick={() => setSearchQuery('')} className="btn-ghost text-xs" style={{ color: '#FF6A3D' }}>Clear</button>
          )}
        </div>
      )}

      {loading ? <div className="grid gap-4 sm:grid-cols-2">{[1,2,3,4].map(i => <div key={i} className="h-40 skeleton" />)}</div> : filteredDigests.length === 0 ? (
        <div className="glass-card"><div className="empty-state">
          <div className="empty-state-icon"><svg className="h-6 w-6" style={{ color: '#9DAAF2' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg></div>
          <p className="text-sm font-semibold" style={{ color: '#3d4660' }}>{digests.length === 0 ? 'No digests yet' : 'No digests match your search'}</p>
          <p className="text-xs" style={{ color: '#6b7394' }}>{digests.length === 0 ? 'Run the pipeline to generate a PDF report.' : 'Try a different search term.'}</p>
        </div></div>
      ) : (
        <div className="stagger-children grid gap-4 sm:grid-cols-2">
          {filteredDigests.map(d => (
            <div key={d.id} className="glass-card flex flex-col p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-xl" style={{ background: 'rgba(255,106,61,0.1)', color: '#FF6A3D' }}><svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg></div>
                  <div><h3 className="text-sm font-bold" style={{ color: '#1A2238' }}>Digest #{d.id}</h3><p className="text-[11px]" style={{ color: '#9ba2bc' }}>Run #{d.run_id}</p></div>
                </div>
                <span className="text-[11px]" style={{ color: '#9ba2bc' }}>{d.created_at ? new Date(d.created_at).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }) : '—'}</span>
              </div>
              {d.executive_summary && <p className="mt-3 flex-1 line-clamp-3 text-xs leading-relaxed" style={{ color: '#6b7394' }}>{d.executive_summary}</p>}
              <a href={`${API_BASE}/digests/${d.id}/download`} target="_blank" rel="noopener noreferrer" className="btn-secondary mt-4 w-fit text-xs">
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" /></svg>Download PDF
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
