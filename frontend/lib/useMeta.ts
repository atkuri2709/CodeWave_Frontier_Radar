'use client';

import { useEffect, useState } from 'react';
import { api, type AgentMeta, type CategoryMeta, type AppMeta } from './api';

const FALLBACK_AGENTS: AgentMeta[] = [
  { id: 'competitors', label: 'Competitors', badge: 'agent-orange', color: '#FF6A3D', description: '' },
  { id: 'model_providers', label: 'Model Providers', badge: 'agent-lavender', color: '#9DAAF2', description: '' },
  { id: 'research', label: 'Research', badge: 'agent-gold', color: '#F4DB7D', description: '' },
  { id: 'hf_benchmarks', label: 'HF Benchmarks', badge: 'agent-navy', color: '#1A2238', description: '' },
];

const FALLBACK_CATEGORIES: CategoryMeta[] = [
  { id: 'release', label: 'Release' },
  { id: 'research', label: 'Research' },
  { id: 'benchmark', label: 'Benchmark' },
];

let cachedMeta: AppMeta | null = null;

export function useMeta() {
  const [agents, setAgents] = useState<AgentMeta[]>(cachedMeta?.agents || FALLBACK_AGENTS);
  const [categories, setCategories] = useState<CategoryMeta[]>(cachedMeta?.categories || FALLBACK_CATEGORIES);
  const [loaded, setLoaded] = useState(!!cachedMeta);

  useEffect(() => {
    if (cachedMeta) return;
    api.meta.get()
      .then(meta => {
        cachedMeta = meta;
        if (meta.agents.length > 0) setAgents(meta.agents);
        if (meta.categories.length > 0) setCategories(meta.categories);
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  const agentLabel = (id: string) => agents.find(a => a.id === id)?.label || id.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  const agentBadge = (id: string) => agents.find(a => a.id === id)?.badge || 'badge-zinc';
  const agentColor = (id: string) => agents.find(a => a.id === id)?.color || '#6b7394';
  const agentIds = agents.map(a => a.id);
  const categoryLabel = (id: string) => categories.find(c => c.id === id)?.label || id.charAt(0).toUpperCase() + id.slice(1);

  return { agents, categories, loaded, agentLabel, agentBadge, agentColor, agentIds, categoryLabel };
}
