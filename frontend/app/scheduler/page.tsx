'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, type ScheduledJob, type SchedulerStatus, type PipelineConfig, type Run } from '@/lib/api';
import { useToast } from '../components/Toast';

const TIMEZONES = [
  'Asia/Kolkata', 'UTC', 'US/Eastern', 'US/Central', 'US/Pacific',
  'Europe/London', 'Europe/Berlin', 'Europe/Paris',
  'Asia/Tokyo', 'Asia/Shanghai',
  'Australia/Sydney',
];

const FREQUENCY_OPTIONS = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'yearly', label: 'Yearly' },
  { value: 'interval', label: 'Repeat (Interval)' },
] as const;

const FREQ_BADGE: Record<string, string> = {
  daily: 'badge-emerald', weekly: 'badge-amber', monthly: 'agent-lavender', yearly: 'agent-gold', interval: 'agent-navy',
};

const FREQ_LABEL: Record<string, string> = {
  daily: 'Daily', weekly: 'Weekly (Mon)', monthly: 'Monthly (1st)', yearly: 'Yearly (Jan 1)', interval: 'Interval',
};

const inputStyle = { borderColor: 'rgba(26,34,56,0.12)', background: 'rgba(26,34,56,0.02)' };

export default function SchedulerPage() {
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [pipelines, setPipelines] = useState<PipelineConfig[]>([]);
  const [pipelineNames, setPipelineNames] = useState<string[]>([]);
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingJob, setEditingJob] = useState<ScheduledJob | null>(null);
  const [saving, setSaving] = useState(false);

  const [formPipeline, setFormPipeline] = useState('');
  const [formSchedulerName, setFormSchedulerName] = useState('');
  const [formFrequency, setFormFrequency] = useState<string>('daily');
  const [formRunTime, setFormRunTime] = useState('06:30');
  const [formTimezone, setFormTimezone] = useState('Asia/Kolkata');
  const [formStartDate, setFormStartDate] = useState('');
  const [formEndDate, setFormEndDate] = useState('');
  const [formStartTime, setFormStartTime] = useState('');
  const [formEndTime, setFormEndTime] = useState('');
  const [formInterval, setFormInterval] = useState(60);
  const [formEnabled, setFormEnabled] = useState(true);

  const toast = useToast();

  const refresh = useCallback(async () => {
    const [j, s, pcs, r] = await Promise.all([
      api.scheduler.list(),
      api.scheduler.status(),
      api.pipelineConfigs.list().catch(() => []),
      api.runs.list().catch(() => []),
    ]);
    setJobs(j);
    setStatus(s);
    setPipelines(pcs);
    setRuns(r);
    const configNames = pcs.map(p => p.pipeline_name);
    setPipelineNames(configNames.sort());
  }, []);

  useEffect(() => {
    refresh().catch(() => {}).finally(() => setLoading(false));
  }, [refresh]);

  const hasRunningJobs = runs.some(r => r.status === 'running' || r.status === 'pending');
  useEffect(() => {
    if (!hasRunningJobs) return;
    const interval = setInterval(() => { refresh().catch(() => {}); }, 5000);
    return () => clearInterval(interval);
  }, [hasRunningJobs, refresh]);

  const getLatestRun = (pipelineName: string): Run | undefined => {
    return runs.find(r => r.pipeline_name === pipelineName);
  };

  const formatRunTime = (dateStr: string | null) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short', timeZone: 'Asia/Kolkata' });
  };

  const runStatusBadge = (status: string) => {
    switch (status) {
      case 'success': return 'badge-emerald';
      case 'running': return 'badge-amber';
      case 'pending': return 'badge-amber';
      case 'failed': return 'badge-red';
      case 'partial': return 'badge-red';
      default: return 'badge-zinc';
    }
  };

  const runStatusLabel = (status: string) => {
    switch (status) {
      case 'success': return 'Completed';
      case 'running': return 'In Progress';
      case 'pending': return 'Pending';
      case 'failed': return 'Failed';
      case 'partial': return 'Partial';
      default: return status;
    }
  };

  const resetForm = () => {
    setFormPipeline('');
    setFormSchedulerName('');
    setFormFrequency('daily');
    setFormRunTime('06:30');
    setFormTimezone('Asia/Kolkata');
    setFormStartDate('');
    setFormEndDate('');
    setFormStartTime('');
    setFormEndTime('');
    setFormInterval(60);
    setFormEnabled(true);
    setEditingJob(null);
    setShowForm(false);
  };

  const openEdit = (job: ScheduledJob) => {
    setEditingJob(job);
    setFormPipeline(job.pipeline_name);
    setFormSchedulerName(job.scheduler_name);
    setFormFrequency(job.frequency);
    setFormRunTime(job.run_time || '06:30');
    setFormTimezone(job.timezone || 'Asia/Kolkata');
    setFormStartDate(job.start_date || '');
    setFormEndDate(job.end_date || '');
    setFormStartTime(job.start_time || '');
    setFormEndTime(job.end_time || '');
    setFormInterval(job.interval_minutes || 60);
    setFormEnabled(job.enabled);
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!formPipeline.trim()) { toast.show('Pipeline name is required', 'error'); return; }
    if (!formSchedulerName.trim()) { toast.show('Scheduler name is required', 'error'); return; }
    setSaving(true);
    try {
      const payload: any = {
        pipeline_name: formPipeline.trim(),
        scheduler_name: formSchedulerName.trim(),
        frequency: formFrequency,
        run_time: formFrequency !== 'interval' ? formRunTime : undefined,
        timezone: formTimezone,
        start_date: formStartDate || undefined,
        end_date: formEndDate || undefined,
        start_time: formStartTime || undefined,
        end_time: formEndTime || undefined,
        interval_minutes: formFrequency === 'interval' ? formInterval : undefined,
        enabled: formEnabled,
      };
      if (editingJob) {
        await api.scheduler.update(editingJob.id, payload);
        toast.show(`Schedule "${formSchedulerName}" updated`, 'success');
      } else {
        await api.scheduler.create(payload);
        toast.show(`Schedule "${formSchedulerName}" created`, 'success');
      }
      resetForm();
      await refresh();
    } catch (err: unknown) {
      toast.show(err instanceof Error ? err.message : 'Failed to save', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (job: ScheduledJob) => {
    if (!confirm(`Delete schedule "${job.scheduler_name}"?`)) return;
    try {
      await api.scheduler.delete(job.id);
      toast.show(`Schedule "${job.scheduler_name}" deleted`, 'success');
      await refresh();
    } catch { toast.show('Failed to delete schedule', 'error'); }
  };

  const handleToggle = async (job: ScheduledJob) => {
    const newEnabled = !job.enabled;
    setJobs(prev => prev.map(j => j.id === job.id ? { ...j, enabled: newEnabled } : j));
    if (status) {
      const enabledCount = jobs.filter(j => j.id === job.id ? newEnabled : j.enabled).length;
      setStatus({ ...status, running: enabledCount > 0, job_count: enabledCount });
    }
    try {
      await api.scheduler.update(job.id, { enabled: newEnabled });
      toast.show(`${job.scheduler_name} ${newEnabled ? 'enabled' : 'disabled'}`, 'success');
      await new Promise(r => setTimeout(r, 800));
      await refresh();
    } catch {
      setJobs(prev => prev.map(j => j.id === job.id ? { ...j, enabled: !newEnabled } : j));
      if (status) await refresh();
      toast.show('Failed to toggle', 'error');
    }
  };

  const formatSchedule = (job: ScheduledJob) => {
    if (job.frequency === 'interval') return `Every ${job.interval_minutes} min`;
    const time = job.run_time || '06:30';
    const tz = job.timezone || 'Asia/Kolkata';
    const base = FREQ_LABEL[job.frequency] || job.frequency;
    return `${base} at ${time} (${tz})`;
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header relative">
        <div className="absolute inset-0 overflow-hidden rounded-2xl">
          <div className="absolute -top-16 -right-16 h-48 w-48 opacity-20" style={{ background: 'radial-gradient(circle, rgba(157,170,242,0.5) 0%, transparent 60%)' }} />
        </div>
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1>Scheduler</h1>
            <p>Create and manage scheduled pipeline runs — daily, weekly, monthly, or custom intervals.</p>
          </div>
          <div className="flex gap-2">
            {status && (
              <span className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-bold ${status.running ? 'text-emerald-700' : 'text-zinc-500'}`}
                style={{ background: status.running ? 'rgba(16,185,129,0.1)' : 'rgba(26,34,56,0.05)' }}>
                <span className={`h-1.5 w-1.5 rounded-full ${status.running ? 'bg-emerald-500 animate-pulse-dot' : 'bg-zinc-400'}`} />
                {status.running ? `${status.job_count} active` : 'Stopped'}
              </span>
            )}
            <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg>
              New Schedule
            </button>
          </div>
        </div>
      </div>

      {/* Create / Edit Form */}
      {showForm && (
        <div className="glass-card p-6 animate-slide-up">
          <h2 className="text-sm font-bold mb-4" style={{ color: '#1A2238' }}>
            {editingJob ? 'Edit Schedule' : 'Create Schedule'}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {/* Pipeline Name — dropdown from DB */}
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: '#6b7394' }}>Pipeline Name</label>
              {pipelineNames.length > 0 ? (
                <select
                  value={formPipeline}
                  onChange={e => setFormPipeline(e.target.value)}
                  className="w-full rounded-xl border px-3 py-2 text-sm"
                  style={inputStyle}
                >
                  <option value="">— Select a pipeline —</option>
                  {pipelineNames.map(n => <option key={n} value={n}>{n}</option>)}
                </select>
              ) : (
                <input
                  type="text"
                  value={formPipeline}
                  onChange={e => setFormPipeline(e.target.value)}
                  placeholder=""
                  className="w-full rounded-xl border px-3 py-2 text-sm"
                  style={inputStyle}
                />
              )}
              {pipelineNames.length > 0 && (
                <p className="mt-1 text-[10px]" style={{ color: '#9ba2bc' }}>
                  {/* Or type a new name:
                  <input
                    type="text"
                    value={formPipeline}
                    onChange={e => setFormPipeline(e.target.value)}
                    placeholder="Custom name..."
                    className="ml-1 inline-block w-40 rounded border px-1.5 py-0.5 text-[10px]"
                    style={{ borderColor: 'rgba(26,34,56,0.1)' }}
                  /> */}
                </p>
              )}
            </div>

            {/* Scheduler Name */}
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: '#6b7394' }}>Scheduler Name</label>
              <input
                type="text"
                value={formSchedulerName}
                onChange={e => setFormSchedulerName(e.target.value)}
                className="w-full rounded-xl border px-3 py-2 text-sm"
                style={inputStyle}
              />
            </div>

            {/* Frequency */}
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: '#6b7394' }}>Frequency</label>
              <select
                value={formFrequency}
                onChange={e => setFormFrequency(e.target.value)}
                className="w-full rounded-xl border px-3 py-2 text-sm"
                style={inputStyle}
              >
                {FREQUENCY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>

            {/* Time & Timezone (for non-interval) */}
            {formFrequency !== 'interval' ? (
              <>
                <div>
                  <label className="block text-xs font-semibold mb-1" style={{ color: '#6b7394' }}>Run Time</label>
                  <input
                    type="time"
                    value={formRunTime}
                    onChange={e => setFormRunTime(e.target.value)}
                    className="w-full rounded-xl border px-3 py-2 text-sm"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold mb-1" style={{ color: '#6b7394' }}>Timezone</label>
                  <select
                    value={formTimezone}
                    onChange={e => setFormTimezone(e.target.value)}
                    className="w-full rounded-xl border px-3 py-2 text-sm"
                    style={inputStyle}
                  >
                    {TIMEZONES.map(tz => <option key={tz} value={tz}>{tz}</option>)}
                  </select>
                </div>
              </>
            ) : (
              <div>
                <label className="block text-xs font-semibold mb-1" style={{ color: '#6b7394' }}>Interval (minutes)</label>
                <input
                  type="number"
                  min={1}
                  value={formInterval}
                  onChange={e => setFormInterval(Math.max(1, +e.target.value))}
                  className="w-full rounded-xl border px-3 py-2 text-sm"
                  style={inputStyle}
                />
              </div>
            )}

            {/* Start / End Dates */}
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: '#6b7394' }}>Start Date <span className="font-normal">(optional)</span></label>
              <input
                type="date"
                value={formStartDate}
                onChange={e => setFormStartDate(e.target.value)}
                className="w-full rounded-xl border px-3 py-2 text-sm"
                style={inputStyle}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: '#6b7394' }}>End Date <span className="font-normal">(optional)</span></label>
              <input
                type="date"
                value={formEndDate}
                onChange={e => setFormEndDate(e.target.value)}
                className="w-full rounded-xl border px-3 py-2 text-sm"
                style={inputStyle}
              />
            </div>

            {/* Start / End Times */}
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: '#6b7394' }}>Start Time <span className="font-normal">(optional)</span></label>
              <input
                type="time"
                value={formStartTime}
                onChange={e => setFormStartTime(e.target.value)}
                className="w-full rounded-xl border px-3 py-2 text-sm"
                style={inputStyle}
              />
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1" style={{ color: '#6b7394' }}>End Time <span className="font-normal">(optional)</span></label>
              <input
                type="time"
                value={formEndTime}
                onChange={e => setFormEndTime(e.target.value)}
                className="w-full rounded-xl border px-3 py-2 text-sm"
                style={inputStyle}
              />
            </div>

            {/* Enabled toggle */}
            <div className="flex items-center gap-2 sm:col-span-2">
              <button
                type="button"
                onClick={() => setFormEnabled(!formEnabled)}
                className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${formEnabled ? 'bg-emerald-500' : 'bg-zinc-300'}`}
              >
                <span className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${formEnabled ? 'translate-x-5' : 'translate-x-0'}`} />
              </button>
              <span className="text-xs font-medium" style={{ color: '#6b7394' }}>{formEnabled ? 'Enabled — will run automatically' : 'Disabled — paused'}</span>
            </div>
          </div>

          <div className="mt-5 flex gap-2">
            <button onClick={handleSave} disabled={saving} className="btn-primary">
              {saving ? 'Saving...' : editingJob ? 'Update Schedule' : 'Create Schedule'}
            </button>
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
          </div>
        </div>
      )}

      {/* Jobs List */}
      {loading ? (
        <div className="space-y-3">{[1, 2, 3].map(i => <div key={i} className="h-20 skeleton" />)}</div>
      ) : jobs.length === 0 && !showForm ? (
        <div className="glass-card">
          <div className="empty-state">
            <div className="empty-state-icon">
              <svg className="h-6 w-6" style={{ color: '#9DAAF2' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <p className="text-sm font-semibold" style={{ color: '#3d4660' }}>No scheduled jobs yet</p>
            <p className="text-xs" style={{ color: '#6b7394' }}>Create a schedule to automatically run your pipeline.</p>
            <button onClick={() => setShowForm(true)} className="btn-primary mt-3">Create Schedule</button>
          </div>
        </div>
      ) : (
        <div className="stagger-children space-y-3">
          {jobs.map(job => {
            const nextRun = status?.jobs.find(j => j.id === _jobId(job.scheduler_name));
            const latestRun = getLatestRun(job.pipeline_name);
            const isRunning = latestRun?.status === 'running' || latestRun?.status === 'pending';
            return (
              <div key={job.id} className={`glass-card overflow-hidden ${!job.enabled ? 'opacity-60' : ''}`}>
                <div className="flex items-center gap-4 px-5 py-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl" style={{ background: isRunning ? 'rgba(245,158,11,0.1)' : job.enabled ? 'rgba(16,185,129,0.08)' : 'rgba(26,34,56,0.04)' }}>
                    {isRunning ? (
                      <span className="h-5 w-5 animate-spin rounded-full border-2 border-amber-500 border-t-transparent" />
                    ) : (
                      <svg className="h-5 w-5" style={{ color: job.enabled ? '#059669' : '#9ba2bc' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-bold" style={{ color: '#1A2238' }}>{job.scheduler_name}</span>
                      <span className={`badge ${job.enabled ? 'badge-emerald' : 'badge-zinc'}`}>{job.enabled ? 'Active' : 'Disabled'}</span>
                      <span className={`badge ${FREQ_BADGE[job.frequency] || 'badge-zinc'}`}>{FREQ_LABEL[job.frequency] || job.frequency}</span>
                      {latestRun && (
                        <span className={`badge ${runStatusBadge(latestRun.status)}`}>
                          {isRunning && <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse-dot" />}
                          {runStatusLabel(latestRun.status)}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-3 text-xs" style={{ color: '#6b7394' }}>
                      <span>Pipeline: <strong>{job.pipeline_name}</strong></span>
                      <span style={{ color: '#d0d3de' }}>&middot;</span>
                      <span>{formatSchedule(job)}</span>
                      {(job.start_date || job.start_time) && (
                        <>
                          <span style={{ color: '#d0d3de' }}>&middot;</span>
                          <span>From: {[job.start_date, job.start_time].filter(Boolean).join(' ')}</span>
                        </>
                      )}
                      {(job.end_date || job.end_time) && (
                        <>
                          <span style={{ color: '#d0d3de' }}>&middot;</span>
                          <span>Until: {[job.end_date, job.end_time].filter(Boolean).join(' ')}</span>
                        </>
                      )}
                    </div>
                    {/* Run status & next schedule row */}
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                      {latestRun && (
                        <span className="flex items-center gap-1.5 rounded-lg px-2 py-1" style={{
                          background: latestRun.status === 'success' ? 'rgba(16,185,129,0.08)' : latestRun.status === 'running' || latestRun.status === 'pending' ? 'rgba(245,158,11,0.08)' : latestRun.status === 'failed' ? 'rgba(220,38,38,0.06)' : 'rgba(26,34,56,0.04)',
                          color: latestRun.status === 'success' ? '#059669' : latestRun.status === 'running' || latestRun.status === 'pending' ? '#d97706' : latestRun.status === 'failed' ? '#dc2626' : '#6b7394',
                        }}>
                          {latestRun.status === 'success' && <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg>}
                          {isRunning && <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse-dot" />}
                          {latestRun.status === 'failed' && <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>}
                          Last run: {runStatusLabel(latestRun.status)}
                          {latestRun.finished_at && ` at ${formatRunTime(latestRun.finished_at)}`}
                          {isRunning && latestRun.started_at && ` (started ${formatRunTime(latestRun.started_at)})`}
                          {latestRun.status === 'success' && ` — ${latestRun.findings_count} findings`}
                        </span>
                      )}
                      {nextRun?.next_run && (
                        <span className="flex items-center gap-1.5 rounded-lg px-2 py-1" style={{ background: 'rgba(157,170,242,0.08)', color: '#4c5aad' }}>
                          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                          Next run: {new Date(nextRun.next_run).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' })}
                        </span>
                      )}
                      {!latestRun && !nextRun?.next_run && (
                        <span className="text-xs" style={{ color: '#9ba2bc' }}>No runs yet</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleToggle(job)}
                      className="rounded-lg p-2 text-xs transition-colors hover:bg-[rgba(26,34,56,0.04)]"
                      title={job.enabled ? 'Disable' : 'Enable'}
                    >
                      <svg className="h-4 w-4" style={{ color: job.enabled ? '#059669' : '#9ba2bc' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" /></svg>
                    </button>
                    <button
                      onClick={() => openEdit(job)}
                      className="rounded-lg p-2 text-xs transition-colors hover:bg-[rgba(26,34,56,0.04)]"
                      title="Edit"
                    >
                      <svg className="h-4 w-4" style={{ color: '#6b7394' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
                      </svg>
                    </button>
                    <button
                      onClick={() => handleDelete(job)}
                      className="rounded-lg p-2 text-xs transition-colors hover:bg-[rgba(220,38,38,0.06)]"
                      title="Delete"
                    >
                      <svg className="h-4 w-4" style={{ color: '#dc2626' }} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function _jobId(schedulerName: string) {
  return `scheduled_${schedulerName}`;
}
