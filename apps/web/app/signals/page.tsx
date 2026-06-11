"use client";

import { useState, useCallback, useMemo, useRef, useEffect, Fragment } from "react";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

// Throw on non-2xx so SWR sets error state properly; also apply a 20s timeout
// so the spinner doesn't hang forever when the API / DB is unreachable.
const fetcher = async (url: string) => {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), 20_000);
  try {
    const r = await fetch(url, { signal: controller.signal });
    if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`);
    return r.json();
  } finally {
    clearTimeout(id);
  }
};

// ── Source metadata ───────────────────────────────────────────────────────────

const SOURCE_META: Record<string, { icon: string; label: string; color: string; dot: string }> = {
  prices:    { icon: "💹", label: "Prices",    color: "bg-amber-50 text-amber-700 border-amber-200",   dot: "bg-amber-400" },
  gdelt:     { icon: "🌍", label: "GDELT",     color: "bg-purple-50 text-purple-700 border-purple-200", dot: "bg-purple-400" },
  logistics: { icon: "🚢", label: "Logistics", color: "bg-blue-50 text-blue-700 border-blue-200",       dot: "bg-blue-400" },
  press:     { icon: "📰", label: "Press",     color: "bg-slate-50 text-slate-600 border-slate-200",     dot: "bg-slate-400" },
  demand:    { icon: "📈", label: "Demand",    color: "bg-teal-50 text-teal-700 border-teal-200",        dot: "bg-teal-400" },
  sec:       { icon: "📄", label: "SEC",       color: "bg-gray-50 text-gray-600 border-gray-200",        dot: "bg-gray-400" },
  ir:        { icon: "🏭", label: "IR / OEM",  color: "bg-orange-50 text-orange-700 border-orange-200",  dot: "bg-orange-400" },
};

// ── Event class metadata ──────────────────────────────────────────────────────

const EVENT_CLASS_META: Record<string, { label: string; color: string }> = {
  commodity_price_move:    { label: "Price Move",     color: "bg-amber-50 text-amber-700 border-amber-200" },
  geopolitical_disruption: { label: "Geopolitical",   color: "bg-red-50 text-red-700 border-red-200" },
  supplier_capacity:       { label: "OEM Capacity",   color: "bg-violet-50 text-violet-700 border-violet-200" },
  logistics_disruption:    { label: "Logistics",      color: "bg-blue-50 text-blue-700 border-blue-200" },
  regulatory_trade:        { label: "Regulatory",     color: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  demand_surge:            { label: "Demand Surge",   color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  financial_disclosure:    { label: "Disclosure",     color: "bg-gray-50 text-gray-600 border-gray-200" },
  natural_disaster:        { label: "Natural Disaster", color: "bg-orange-50 text-orange-700 border-orange-200" },
  other:                   { label: "Other",          color: "bg-slate-50 text-slate-400 border-slate-200" },
};

// ── Signal kind metadata ──────────────────────────────────────────────────────

const SIGNAL_KIND_META: Record<string, { label: string; color: string }> = {
  price_move:            { label: "Price Move",   color: "bg-amber-50 text-amber-700 border-amber-200" },
  capacity_change:       { label: "Capacity",     color: "bg-violet-50 text-violet-700 border-violet-200" },
  logistics_disruption:  { label: "Logistics",    color: "bg-blue-50 text-blue-700 border-blue-200" },
  regulatory_action:     { label: "Regulatory",   color: "bg-indigo-50 text-indigo-700 border-indigo-200" },
  demand_shift:          { label: "Demand",       color: "bg-teal-50 text-teal-700 border-teal-200" },
  geopolitical:          { label: "Geopolitical", color: "bg-red-50 text-red-700 border-red-200" },
  financial_disclosure:  { label: "Disclosure",   color: "bg-gray-50 text-gray-600 border-gray-200" },
  weather_climate:       { label: "Weather",      color: "bg-sky-50 text-sky-700 border-sky-200" },
  other:                 { label: "Other",        color: "bg-slate-50 text-slate-400 border-slate-200" },
};

// ── Impact type colors ────────────────────────────────────────────────────────

const IMPACT_COLORS: Record<string, string> = {
  "GOES input cost":     "bg-red-50 text-red-700 border-red-200",
  "Winding metal cost":  "bg-orange-50 text-orange-700 border-orange-200",
  "Insulation material": "bg-amber-50 text-amber-700 border-amber-200",
  "OEM capacity":        "bg-violet-50 text-violet-700 border-violet-200",
  "OEM disruption":      "bg-rose-50 text-rose-700 border-rose-200",
  "Sub-tier supplier":   "bg-pink-50 text-pink-700 border-pink-200",
  "Lane disruption":     "bg-blue-50 text-blue-700 border-blue-200",
  "Demand surge":        "bg-emerald-50 text-emerald-700 border-emerald-200",
  "Regulatory / trade":  "bg-indigo-50 text-indigo-700 border-indigo-200",
  "Macro proxy":         "bg-slate-100 text-slate-500 border-slate-200",
  "No TP impact":        "bg-slate-50 text-slate-400 border-slate-200",
};
const IMPACT_FALLBACK = "bg-slate-50 text-slate-400 border-slate-200";

// ── Graph entity type colors ──────────────────────────────────────────────────

const ENTITY_COLORS: Record<string, string> = {
  suppliers:   "bg-orange-50 text-orange-700 border-orange-200",
  commodities: "bg-amber-50 text-amber-700 border-amber-200",
  ports:       "bg-blue-50 text-blue-700 border-blue-200",
  countries:   "bg-purple-50 text-purple-700 border-purple-200",
};

// ── Tier accent system (drives the row priority rail + tier badges) ────────────

const TIER_RAIL: Record<number, string> = {
  1: "border-l-red-500",
  2: "border-l-orange-400",
  3: "border-l-amber-300",
  4: "border-l-slate-200",
};
const TIER_METER: Record<number, string> = {
  1: "bg-red-500",
  2: "bg-orange-400",
  3: "bg-amber-400",
  4: "bg-slate-300",
};
// Composite-priority weighting (relevance + tier + corroboration + recency)
const TIER_WEIGHT: Record<number, number> = { 1: 1.0, 2: 0.7, 3: 0.4, 4: 0.15 };

// ── Small reusable components ─────────────────────────────────────────────────

function Chip({ label, color }: { label: string; color: string }) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-medium border whitespace-nowrap ${color}`}>
      {label}
    </span>
  );
}

function TierBadge({ tier }: { tier: number | null | undefined }) {
  if (tier == null) return <span className="text-xs text-slate-300">—</span>;
  const colors: Record<number, string> = {
    1: "bg-red-50 text-red-600 border-red-200",
    2: "bg-orange-50 text-orange-600 border-orange-200",
    3: "bg-amber-50 text-amber-600 border-amber-200",
    4: "bg-slate-50 text-slate-400 border-slate-200",
  };
  return <Chip label={`T${tier}`} color={colors[tier] ?? IMPACT_FALLBACK} />;
}

function ScorePill({ score, overridden }: { score: number; overridden?: boolean }) {
  const color =
    score >= 0.8 ? "bg-red-50 text-red-700 border-red-200" :
    score >= 0.6 ? "bg-orange-50 text-orange-700 border-orange-200" :
    score >= 0.4 ? "bg-amber-50 text-amber-700 border-amber-200" :
                   "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (overridden) {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[11px] font-semibold border border-dashed border-violet-300 bg-violet-50 text-violet-700 whitespace-nowrap font-mono">
        {score.toFixed(2)} <span className="opacity-60 font-normal not-italic">·ed</span>
      </span>
    );
  }
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-[11px] font-semibold font-mono border whitespace-nowrap ${color}`}>
      {score.toFixed(2)}
    </span>
  );
}

// Compact priority meter + numeric, used in the leading PRI column.
function PriorityMeter({ score, tier, rank, showRank }: {
  score: number; tier: number | null | undefined; rank: number; showRank: boolean;
}) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);
  const meter = TIER_METER[tier ?? 4] ?? "bg-slate-300";
  const top = showRank && rank <= 3;
  return (
    <div className="flex flex-col gap-1 min-w-[52px]">
      <div className="flex items-baseline gap-1">
        {showRank && (
          <span className={`text-[11px] font-bold tabular-nums ${top ? "text-amber-500" : "text-slate-400"}`}>
            {top ? "★" : ""}{rank}
          </span>
        )}
        <span className="text-[11px] font-mono font-semibold text-slate-700 tabular-nums">
          {score.toFixed(2)}
        </span>
      </div>
      <div className="h-1 w-full rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-full rounded-full ${meter}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function DirectionBadge({ dir }: { dir: string | undefined }) {
  if (!dir) return <span className="text-slate-300 text-xs">—</span>;
  const map: Record<string, { icon: string; color: string }> = {
    negative: { icon: "▼", color: "bg-red-50 text-red-700 border-red-200" },
    positive: { icon: "▲", color: "bg-emerald-50 text-emerald-700 border-emerald-200" },
    neutral:  { icon: "→", color: "bg-slate-100 text-slate-500 border-slate-200" },
  };
  const m = map[dir] ?? map.neutral;
  return <Chip label={`${m.icon} ${dir}`} color={m.color} />;
}

function MagnitudeBadge({ mag }: { mag: string | undefined }) {
  if (!mag) return <span className="text-slate-300 text-xs">—</span>;
  const map: Record<string, string> = {
    severe:   "bg-red-50 text-red-700 border-red-200",
    major:    "bg-orange-50 text-orange-700 border-orange-200",
    moderate: "bg-amber-50 text-amber-700 border-amber-200",
    minor:    "bg-slate-100 text-slate-500 border-slate-200",
  };
  return <Chip label={mag} color={map[mag] ?? IMPACT_FALLBACK} />;
}

// Mini sparkline for price moves: bars per horizon (1d / 5d / 30d) + headline %.
// Degrades to a plain trend chip when per-horizon data isn't present.
function PriceTrend({ moves, label }: { moves: Record<string, number> | null | undefined; label: string | null }) {
  const order = ["1d", "5d", "30d"];
  const pts = moves ? order.filter((k) => moves[k] != null).map((k) => ({ k, v: moves[k] })) : [];
  const headlinePct = (() => {
    const m = (label ?? "").match(/([+-]?\d+(?:\.\d+)?)%/);
    return m ? parseFloat(m[1]) : (pts.length ? pts[pts.length - 1].v : null);
  })();
  const up = (headlinePct ?? 0) >= 0;

  if (!pts.length && headlinePct == null) {
    return label ? <span className="text-xs text-slate-500 font-mono">{label}</span> : null;
  }
  const maxAbs = Math.max(1, ...pts.map((p) => Math.abs(p.v)));
  return (
    <div className="flex items-center gap-2">
      {pts.length > 0 && (
        <div className="flex items-end gap-0.5 h-5" title={pts.map((p) => `${p.k}: ${p.v > 0 ? "+" : ""}${p.v}%`).join("  ")}>
          {pts.map((p) => {
            const h = Math.max(3, Math.round((Math.abs(p.v) / maxAbs) * 18));
            return (
              <div key={p.k} className={`w-1.5 rounded-sm ${p.v >= 0 ? "bg-emerald-400" : "bg-red-400"}`} style={{ height: `${h}px` }} />
            );
          })}
        </div>
      )}
      {headlinePct != null && (
        <span className={`text-[11px] font-mono font-semibold tabular-nums ${up ? "text-emerald-600" : "text-red-600"}`}>
          {up ? "▲" : "▼"} {Math.abs(headlinePct).toFixed(1)}%
        </span>
      )}
    </div>
  );
}

function EntityPills({ entities }: { entities: Record<string, string[]> | null | undefined }) {
  if (!entities) return <span className="text-slate-300 text-xs">—</span>;
  const items: { type: string; name: string }[] = [];
  for (const [type, names] of Object.entries(entities)) {
    if (Array.isArray(names)) names.forEach((n) => items.push({ type, name: n }));
  }
  if (items.length === 0) return <span className="text-slate-300 text-xs">—</span>;
  return (
    <div className="flex flex-wrap gap-0.5 max-w-[200px]">
      {items.slice(0, 6).map((e, i) => (
        <Chip key={i} label={e.name} color={ENTITY_COLORS[e.type] ?? IMPACT_FALLBACK} />
      ))}
      {items.length > 6 && (
        <span className="text-[10px] text-slate-400">+{items.length - 6}</span>
      )}
    </div>
  );
}

function GeoTags({ tags }: { tags: string[] | null | undefined }) {
  if (!tags || tags.length === 0) return <span className="text-slate-300 text-xs">—</span>;
  return (
    <div className="flex flex-wrap gap-0.5 max-w-[160px]">
      {tags.slice(0, 4).map((t, i) => (
        <Chip key={i} label={t} color="bg-purple-50 text-purple-700 border-purple-200" />
      ))}
      {tags.length > 4 && <span className="text-[10px] text-slate-400">+{tags.length - 4}</span>}
    </div>
  );
}

// ── Assess cell (hover-reveal score slider) ───────────────────────────────────

function AssessCell({ signal, onSaved }: { signal: any; onSaved: (id: string, score: number) => void }) {
  const seed = signal.analyst_score ?? signal.llm_score ?? 0.5;
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<number>(seed);
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await fetch(`${API}/api/signals/${signal.id}/score`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ score: draft }),
      });
      onSaved(signal.id, draft);
      setOpen(false);
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={(e) => { e.stopPropagation(); setDraft(seed); setOpen(true); }}
        className="text-xs text-slate-400 hover:text-violet-600 hover:underline transition-colors whitespace-nowrap"
      >
        {signal.analyst_score != null ? "Change" : "Set score"}
      </button>
    );
  }
  return (
    <div className="flex flex-col gap-1.5 min-w-[140px]" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center gap-2">
        <input type="range" min={0} max={1} step={0.01} value={draft}
          onChange={(e) => setDraft(parseFloat(e.target.value))}
          className="w-20 accent-violet-500 cursor-pointer" />
        <span className="text-xs font-mono text-slate-700 w-9">{draft.toFixed(2)}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <button onClick={handleSave} disabled={saving}
          className="text-xs px-2 py-0.5 bg-violet-600 text-white rounded hover:bg-violet-700 disabled:opacity-50">
          {saving ? "…" : "Save"}
        </button>
        <button onClick={() => setOpen(false)} className="text-xs text-slate-400 hover:text-slate-600">
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── Column definition ─────────────────────────────────────────────────────────

type ColDef = {
  key: string;
  label: string;
  section: "general" | "scorer" | "triage";
  essential: boolean;
  width: string;
  sortValue?: (s: any) => any;
};

const SECTION_COLORS = {
  general: "",
  scorer:  "text-violet-500",
  triage:  "text-teal-600",
};

const COLUMNS: ColDef[] = [
  // I. GENERAL
  { key: "priority",    label: "Pri",          section: "general", essential: true,  width: "w-[72px]",
    sortValue: (s) => s._priority ?? 0 },
  { key: "source",      label: "Source",       section: "general", essential: true,  width: "w-[120px]",
    sortValue: (s) => s.source },
  { key: "description", label: "Signal",        section: "general", essential: true,  width: "min-w-[260px] max-w-[380px]" },
  { key: "occurred_at", label: "Time",           section: "general", essential: true,  width: "w-[84px]",
    sortValue: (s) => s.occurred_at },
  { key: "ingested_at", label: "Ingested",       section: "general", essential: false, width: "w-[96px]",
    sortValue: (s) => s.ingested_at },

  // II. SCORER
  { key: "impact_tier",      label: "Tier",         section: "scorer", essential: true,  width: "w-[56px]",
    sortValue: (s) => s.impact_tier ?? 99 },
  { key: "llm_score",        label: "Relevance",    section: "scorer", essential: true,  width: "w-[88px]",
    sortValue: (s) => s.llm_score ?? 0 },
  { key: "mechanism",        label: "Mechanism",    section: "scorer", essential: true,  width: "min-w-[200px] max-w-[280px]" },
  { key: "what_changed",     label: "What Changed", section: "scorer", essential: false, width: "min-w-[160px] max-w-[240px]" },
  { key: "signal_kind",      label: "Kind",         section: "scorer", essential: false, width: "w-[110px]",
    sortValue: (s) => s.signal_kind ?? "" },
  { key: "impact_type",      label: "Impact Type",  section: "scorer", essential: false, width: "w-[150px]",
    sortValue: (s) => s.impact_type ?? "" },
  { key: "scorer_reasoning", label: "Reasoning",    section: "scorer", essential: false, width: "min-w-[180px] max-w-[260px]" },

  // III. TRIAGE
  { key: "graph_entities",          label: "Entities",      section: "triage", essential: true,  width: "min-w-[160px] max-w-[220px]" },
  { key: "geo_tags",                label: "Geo",           section: "triage", essential: false, width: "min-w-[120px] max-w-[180px]" },
  { key: "triage_reasoning",        label: "Reasoning",     section: "triage", essential: false, width: "min-w-[180px] max-w-[260px]" },
  { key: "event_class",             label: "Event Class",   section: "triage", essential: false, width: "w-[120px]",
    sortValue: (s) => s.event_class ?? "" },
  { key: "secondary_event_classes", label: "Secondary",     section: "triage", essential: false, width: "w-[140px]" },
  { key: "state_what",              label: "What",          section: "triage", essential: false, width: "min-w-[140px]" },
  { key: "state_direction",         label: "Direction",     section: "triage", essential: false, width: "w-[90px]",
    sortValue: (s) => s.state_change?.direction ?? "" },
  { key: "state_magnitude",         label: "Scale",         section: "triage", essential: false, width: "w-[90px]",
    sortValue: (s) => { const m: string = s.state_change?.magnitude ?? ""; return ({ severe:0, major:1, moderate:2, minor:3 } as Record<string,number>)[m] ?? 9; } },
  { key: "confidence",              label: "Confidence",    section: "triage", essential: false, width: "w-[80px]",
    sortValue: (s) => s.confidence ?? 0 },

  // ACTION
  { key: "assess", label: "Assess", section: "general", essential: true, width: "w-[120px]" },
];

// ── Sort helpers ──────────────────────────────────────────────────────────────

type SortState = { col: string; dir: "asc" | "desc" };

function sortSignals(signals: any[], sort: SortState | null): any[] {
  if (!sort) return signals;
  const col = COLUMNS.find((c) => c.key === sort.col);
  if (!col?.sortValue) return signals;
  return [...signals].sort((a, b) => {
    const av = col.sortValue!(a);
    const bv = col.sortValue!(b);
    if (av == null && bv == null) return 0;
    if (av == null) return 1;
    if (bv == null) return -1;
    let cmp = av < bv ? -1 : av > bv ? 1 : 0;
    return sort.dir === "asc" ? cmp : -cmp;
  });
}

// ── Event grouping + composite priority ───────────────────────────────────────
// Collapse signals that cover the same real-world event into one row.
// Signals are grouped by event_id (falling back to their own id when NULL).
// The event's displayed attributes come from its highest-relevance member
// ("highest relevance wins"); every member is retained under `_members`.

function effScore(s: any): number {
  return s.analyst_score ?? s.llm_score ?? 0;
}

// Composite priority: relevance×0.4 + tier×0.3 + corroboration×0.2 + recency×0.1.
// All terms normalised to 0..1 so the result is a clean 0..1 priority rank.
function priorityScore(e: any): number {
  const rel = Math.max(0, Math.min(1, effScore(e)));
  const tier = TIER_WEIGHT[e.impact_tier as number] ?? 0.4;          // unknown → mid
  const n = e._sourceCount ?? 1;
  const corroboration = Math.min(1, Math.log2(n) / 3);               // 1→0, 8+ sources→1
  const ageH = e.occurred_at
    ? (Date.now() - new Date(e.occurred_at).getTime()) / 3.6e6
    : 9999;
  const recency = Math.exp(-ageH / 168);                             // ~1-week characteristic decay
  return rel * 0.4 + tier * 0.3 + corroboration * 0.2 + recency * 0.1;
}

function groupIntoEvents(signals: any[]): any[] {
  const buckets = new Map<string, any[]>();
  for (const s of signals) {
    const key = s.event_id ?? s.id;
    const arr = buckets.get(key);
    if (arr) arr.push(s); else buckets.set(key, [s]);
  }
  const events: any[] = [];
  for (const [eventId, members] of buckets) {
    const rep = members.reduce((best, s) => (effScore(s) > effScore(best) ? s : best), members[0]);
    const newest = members.reduce((a, b) =>
      (new Date(b.occurred_at ?? 0) > new Date(a.occurred_at ?? 0) ? b : a), members[0]);
    const evt: any = {
      ...rep,
      occurred_at:   newest.occurred_at ?? rep.occurred_at,
      _eventId:      eventId,
      _members:      members,
      _sourceCount:  members.length,
      _memberSources: Array.from(new Set(members.map((m) => m.source))),
    };
    evt._priority = priorityScore(evt);
    events.push(evt);
  }
  return events;
}

// Tiny inline source badge (used in the expanded sources panel).
function SourceBadge({ source }: { source: string }) {
  const m = SOURCE_META[source] ?? { icon: "📌", label: source, color: "bg-slate-50 text-slate-500 border-slate-200" };
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium border shrink-0 ${m.color}`}>
      {m.icon} {m.label}
    </span>
  );
}

// ── Cell renderer ─────────────────────────────────────────────────────────────

function CellContent({ colKey, signal, onScoreSaved, expanded, rank, rankByPriority }: {
  colKey: string;
  signal: any;
  onScoreSaved: (id: string, score: number) => void;
  expanded: boolean;
  rank: number;
  rankByPriority: boolean;
}) {
  const src = SOURCE_META[signal.source] ?? { icon: "📌", label: signal.source, color: "bg-slate-50 text-slate-500 border-slate-200" };

  switch (colKey) {
    case "priority":
      return <PriorityMeter score={signal._priority ?? 0} tier={signal.impact_tier} rank={rank} showRank={rankByPriority} />;

    case "source": {
      // One badge per unique source type with ×N count.
      const memberSources: string[] = signal._memberSources ?? [signal.source];
      const counts: Record<string, number> = {};
      for (const s of memberSources) counts[s] = (counts[s] ?? 0) + 1;
      // _memberSources is already de-duplicated, so recompute true per-source counts from members.
      const trueCounts: Record<string, number> = {};
      for (const m of (signal._members ?? [signal])) trueCounts[m.source] = (trueCounts[m.source] ?? 0) + 1;
      const entries = Object.entries(trueCounts);
      return (
        <div className="flex flex-col gap-0.5 items-start">
          {entries.map(([srcKey, cnt]) => {
            const m = SOURCE_META[srcKey] ?? { icon: "📌", label: srcKey, color: "bg-slate-50 text-slate-500 border-slate-200" };
            return (
              <span key={srcKey}
                className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[11px] font-medium border ${m.color}`}>
                {m.icon} {m.label}
                {cnt > 1 && <span className="opacity-60 font-semibold text-[10px]">×{cnt}</span>}
              </span>
            );
          })}
        </div>
      );
    }

    case "description": {
      // Synthesised event meaning: prefer what_changed (LLM-generated at ingest).
      const eventTitle = signal.what_changed || signal.description;
      const rawTitle = (signal.description || "")
        .replace(/\s*[-–|]\s*[A-Z][^-–|]{2,40}$/, "")
        .trim();
      const showRaw = rawTitle && rawTitle !== eventTitle && rawTitle.length > 10;

      return (
        <div className="flex flex-col gap-1">
          <div className={`text-sm font-semibold text-slate-800 leading-snug tracking-tight ${expanded ? "" : "line-clamp-2"}`}>
            {eventTitle || <span className="text-slate-400 italic font-normal">No description</span>}
          </div>
          {showRaw && (
            <div className={`text-[11px] text-slate-400 leading-snug ${expanded ? "" : "line-clamp-1"}`}>
              {rawTitle}
            </div>
          )}
          {(signal.price_move || signal.moves_pct) && (
            <PriceTrend moves={signal.moves_pct} label={signal.price_move} />
          )}
          {signal._sourceCount > 1 ? (
            <div className="flex flex-wrap items-center gap-1 mt-0.5">
              {(signal._members ?? []).slice(0, expanded ? undefined : 3).map((m: any, i: number) => (
                m.url ? (
                  <a key={i} href={m.url} target="_blank" rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="inline-flex items-center gap-0.5 text-[10px] text-slate-400 hover:text-blue-600 transition-colors"
                    title={m.description}>
                    ↗ {(SOURCE_META[m.source]?.label ?? m.source)}
                  </a>
                ) : null
              ))}
              {!expanded && (signal._members ?? []).length > 3 && (
                <span className="text-[10px] text-slate-300">+{signal._members.length - 3} more</span>
              )}
            </div>
          ) : (
            signal.url && (
              <a href={signal.url} target="_blank" rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="text-[10px] text-slate-400 hover:text-blue-600 transition-colors">
                ↗ source
              </a>
            )
          )}
        </div>
      );
    }

    case "occurred_at":
      return signal.occurred_at ? (
        <span className="text-xs text-slate-600 whitespace-nowrap font-medium">
          {new Date(signal.occurred_at).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
        </span>
      ) : <span className="text-slate-300 text-xs">—</span>;

    case "ingested_at":
      return signal.ingested_at ? (
        <span className="text-[10px] text-slate-400 whitespace-nowrap">
          {formatDistanceToNow(new Date(signal.ingested_at), { addSuffix: true })}
        </span>
      ) : <span className="text-slate-300 text-xs">—</span>;

    case "impact_tier":
      return <TierBadge tier={signal.impact_tier} />;

    case "what_changed":
      return signal.what_changed ? (
        <span className={`text-xs text-slate-700 leading-snug ${expanded ? "" : "line-clamp-3"}`}>{signal.what_changed}</span>
      ) : <span className="text-slate-300 text-xs">—</span>;

    case "mechanism":
      return signal.mechanism ? (
        <span className={`text-xs text-slate-600 leading-snug ${expanded ? "" : "line-clamp-3"}`}>{signal.mechanism}</span>
      ) : <span className="text-slate-300 text-xs">—</span>;

    case "llm_score": {
      const isOvr = signal.analyst_score != null;
      const score = isOvr ? signal.analyst_score : signal.llm_score;
      return score != null ? <ScorePill score={score} overridden={isOvr} /> : <span className="text-slate-300 text-xs">—</span>;
    }

    case "signal_kind": {
      const m = SIGNAL_KIND_META[signal.signal_kind ?? ""];
      return m ? <Chip label={m.label} color={m.color} /> : <span className="text-slate-300 text-xs">—</span>;
    }

    case "impact_type": {
      const label = signal.impact_type ?? "";
      return label ? (
        <Chip label={label} color={IMPACT_COLORS[label] ?? IMPACT_FALLBACK} />
      ) : <span className="text-slate-300 text-xs">—</span>;
    }

    case "scorer_reasoning":
      return signal.scorer_reasoning ? (
        <span className={`text-[10px] text-slate-500 leading-snug ${expanded ? "" : "line-clamp-3"}`}>{signal.scorer_reasoning}</span>
      ) : <span className="text-slate-300 text-xs">—</span>;

    case "graph_entities":
      return <EntityPills entities={signal.graph_entities} />;

    case "geo_tags":
      return <GeoTags tags={signal.geo_tags} />;

    case "triage_reasoning":
      return signal.triage_reasoning ? (
        <span className={`text-[10px] text-slate-500 leading-snug ${expanded ? "" : "line-clamp-3"}`}>{signal.triage_reasoning}</span>
      ) : <span className="text-slate-300 text-xs">—</span>;

    case "event_class": {
      const ec = EVENT_CLASS_META[signal.event_class ?? ""];
      return ec ? <Chip label={ec.label} color={ec.color} /> : <span className="text-slate-300 text-xs">—</span>;
    }

    case "secondary_event_classes": {
      const sec: string[] = signal.secondary_event_classes ?? [];
      if (sec.length === 0) return <span className="text-slate-300 text-xs">—</span>;
      return (
        <div className="flex flex-col gap-0.5">
          {sec.slice(0, 2).map((ec, i) => {
            const m = EVENT_CLASS_META[ec];
            return m ? <Chip key={i} label={m.label} color={m.color} /> : null;
          })}
        </div>
      );
    }

    case "state_what":
      return signal.state_change?.what ? (
        <span className={`text-xs text-slate-700 leading-snug ${expanded ? "" : "line-clamp-2"}`}>{signal.state_change.what}</span>
      ) : <span className="text-slate-300 text-xs">—</span>;

    case "state_direction":
      return <DirectionBadge dir={signal.state_change?.direction} />;

    case "state_magnitude":
      return <MagnitudeBadge mag={signal.state_change?.magnitude} />;

    case "confidence":
      return signal.confidence != null ? (
        <span className={`text-xs font-mono font-semibold tabular-nums ${
          signal.confidence >= 0.8 ? "text-emerald-700" :
          signal.confidence >= 0.5 ? "text-amber-700" : "text-slate-500"
        }`}>
          {(signal.confidence * 100).toFixed(0)}%
        </span>
      ) : <span className="text-slate-300 text-xs">—</span>;

    case "assess":
      return <AssessCell signal={signal} onSaved={onScoreSaved} />;

    default:
      return null;
  }
}

// ── Sortable column header ────────────────────────────────────────────────────

function ColHeader({ col, sort, onSort }: { col: ColDef; sort: SortState | null; onSort: (key: string) => void; }) {
  const active = sort?.col === col.key;
  const canSort = !!col.sortValue;
  return (
    <th
      className={`px-2.5 py-2.5 text-left text-[10px] font-semibold uppercase tracking-wider select-none
        ${SECTION_COLORS[col.section]}
        ${canSort ? "cursor-pointer hover:text-slate-900" : ""}
        ${col.key === "priority" ? "pl-4" : ""}
        ${col.key === "assess" ? "pr-4" : ""}`}
      onClick={canSort ? () => onSort(col.key) : undefined}
    >
      <span className="flex items-center gap-1">
        {col.label}
        {canSort && (
          <span className={`text-[10px] ${active ? "opacity-100 text-slate-700" : "opacity-25"}`}>
            {active && sort?.dir === "asc" ? "↑" : active && sort?.dir === "desc" ? "↓" : "↕"}
          </span>
        )}
      </span>
    </th>
  );
}

// ── Filter pill button ────────────────────────────────────────────────────────

function FilterPill({ label, count, active, onClick }: {
  label: string; count?: number; active: boolean; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5
        ${active
          ? "bg-slate-900 text-white shadow-sm"
          : "bg-white text-slate-600 border border-slate-200 hover:border-slate-300 hover:bg-slate-50"}`}
    >
      {label}
      {count != null && (
        <span className={`text-[10px] tabular-nums ${active ? "text-slate-300" : "text-slate-400"}`}>{count}</span>
      )}
    </button>
  );
}

// ── KPI card ──────────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, accent, active, onClick }: {
  label: string; value: string | number; sub?: string;
  accent?: "red" | "blue" | "amber" | "slate"; active?: boolean; onClick?: () => void;
}) {
  const accentBar: Record<string, string> = {
    red: "bg-red-500", blue: "bg-blue-500", amber: "bg-amber-500", slate: "bg-slate-400",
  };
  const valueColor: Record<string, string> = {
    red: "text-red-600", blue: "text-blue-600", amber: "text-amber-600", slate: "text-slate-900",
  };
  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      className={`group relative text-left bg-white rounded-2xl border p-4 overflow-hidden transition-all
        ${onClick ? "hover:border-slate-300 hover:shadow-md cursor-pointer" : "cursor-default"}
        ${active ? "border-slate-900 shadow-sm ring-1 ring-slate-900/10" : "border-slate-200"}`}
    >
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${accentBar[accent ?? "slate"]} ${active ? "opacity-100" : "opacity-60"}`} />
      <div className="pl-1.5">
        <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-1.5">{label}</div>
        <div className={`text-2xl font-bold tabular-nums leading-none ${valueColor[accent ?? "slate"]}`}>{value}</div>
        {sub && <div className="text-[11px] text-slate-400 mt-1.5 truncate">{sub}</div>}
      </div>
    </button>
  );
}

// ── Add Signal Modal ──────────────────────────────────────────────────────────

type IngestResult = {
  relevance: number; tier: number | null;
  impact_type: string | null; what_changed: string | null;
  decision: string | null; persisted: boolean;
};
type IngestResponse = { title: string; excerpt: string; result: IngestResult | null };

function AddSignalModal({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [tab,      setTab]      = useState<"url" | "file">("url");
  const [url,      setUrl]      = useState("");
  const [status,   setStatus]   = useState<"idle" | "loading" | "done" | "error">("idle");
  const [message,  setMessage]  = useState("");
  const [result,   setResult]   = useState<IngestResponse | null>(null);
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const urlRef  = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [onClose]);

  useEffect(() => { urlRef.current?.focus(); }, []);

  async function submit(body: BodyInit, endpoint: string, isForm = false) {
    setStatus("loading"); setMessage(""); setResult(null);
    try {
      const r = await fetch(`${API}/api/ingest/${endpoint}`, {
        method: "POST",
        body,
        ...(isForm ? {} : { headers: { "Content-Type": "application/json" } }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail ?? `Error ${r.status}`);
      setResult(data);
      setStatus("done");
      if (data.result?.persisted) onAdded();
    } catch (e: any) {
      setStatus("error");
      setMessage(e.message ?? "Something went wrong");
    }
  }

  function handleUrl(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    submit(JSON.stringify({ url: url.trim() }), "url");
  }

  function handleFile(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    submit(fd, "file", true);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault(); setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  const TIER_COLOR: Record<number, string> = {
    1: "text-red-600 bg-red-50 border-red-200",
    2: "text-amber-600 bg-amber-50 border-amber-200",
    3: "text-slate-500 bg-slate-50 border-slate-200",
    4: "text-slate-400 bg-slate-50 border-slate-200",
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
         onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg flex flex-col overflow-hidden">

        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-900">Add Signal Manually</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 transition-colors">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22z"/>
            </svg>
          </button>
        </div>

        <div className="flex border-b border-slate-100">
          {(["url", "file"] as const).map((t) => (
            <button key={t} onClick={() => { setTab(t); setStatus("idle"); setResult(null); }}
              className={`flex-1 py-2.5 text-sm font-medium transition-colors
                ${tab === t ? "text-blue-600 border-b-2 border-blue-600" : "text-slate-500 hover:text-slate-800"}`}>
              {t === "url" ? "🔗  Paste URL" : "📎  Upload File"}
            </button>
          ))}
        </div>

        <div className="p-6">
          {tab === "url" && (
            <form onSubmit={handleUrl} className="flex flex-col gap-3">
              <label className="text-xs font-medium text-slate-600">Web page URL</label>
              <input
                ref={urlRef}
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/article"
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm
                  focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-400"
              />
              <button type="submit" disabled={status === "loading" || !url.trim()}
                className="w-full py-2 rounded-lg bg-blue-600 text-white text-sm font-semibold
                  hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                {status === "loading" ? "Analysing…" : "Analyse & Add"}
              </button>
            </form>
          )}

          {tab === "file" && (
            <div className="flex flex-col gap-3">
              <label className="text-xs font-medium text-slate-600">
                PDF, DOCX, TXT, or image (PNG / JPG / WEBP) — max 20 MB
              </label>
              <div
                onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                onClick={() => fileRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors
                  ${dragging ? "border-blue-400 bg-blue-50" : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"}`}
              >
                <p className="text-3xl mb-2">📂</p>
                <p className="text-sm font-medium text-slate-600">Drop file here</p>
                <p className="text-xs text-slate-400 mt-1">or click to browse</p>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.webp,.gif"
                  className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
                />
              </div>
              {status === "loading" && (
                <p className="text-sm text-slate-400 text-center animate-pulse">Extracting and analysing…</p>
              )}
            </div>
          )}

          {status === "error" && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex flex-col gap-1">
              <p className="text-sm font-medium text-red-700">
                {message.includes("404") ? "Page not found" :
                 message.includes("403") ? "Access denied" :
                 message.includes("too short") || message.includes("JavaScript") ? "Content unavailable" :
                 "Failed to fetch"}
              </p>
              <p className="text-xs text-red-600 leading-relaxed">{message}</p>
            </div>
          )}

          {status === "done" && result && (
            <div className="mt-4 bg-slate-50 border border-slate-200 rounded-xl p-4 flex flex-col gap-2">
              <p className="text-sm font-semibold text-slate-800 leading-snug">{result.title}</p>
              <p className="text-xs text-slate-500 leading-relaxed">{result.excerpt}</p>
              {result.result && (
                <div className="flex flex-wrap gap-2 mt-1 items-center">
                  <span className="text-xs font-mono font-bold text-slate-700">
                    {(result.result.relevance * 100).toFixed(0)}%
                  </span>
                  {result.result.tier && (
                    <span className={`text-[11px] font-bold px-2 py-0.5 rounded border ${TIER_COLOR[result.result.tier] ?? ""}`}>
                      T{result.result.tier}
                    </span>
                  )}
                  {result.result.impact_type && (
                    <span className="text-[11px] bg-violet-50 border border-violet-200 text-violet-700 px-2 py-0.5 rounded">
                      {result.result.impact_type}
                    </span>
                  )}
                  {result.result.persisted ? (
                    <span className="ml-auto text-xs text-emerald-600 font-semibold">✓ Added to signals</span>
                  ) : (
                    <span className="ml-auto text-xs text-slate-400">Below threshold — not saved</span>
                  )}
                </div>
              )}
              {result.result?.what_changed && (
                <p className="text-xs text-slate-600 italic">{result.result.what_changed}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Constants ─────────────────────────────────────────────────────────────────

const HOUR_OPTIONS = [
  { label: "24 h", value: 24 },
  { label: "48 h", value: 48 },
  { label: "7 d",  value: 168 },
  { label: "30 d", value: 720 },
];

const TIER_OPTS = [1, 2, 3, 4];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SignalsPage() {
  const [hours,          setHours]          = useState(720);  // 30d default — data cadence is sparse/manual
  const [isFull,         setIsFull]         = useState(false);
  const [sort,           setSort]           = useState<SortState | null>({ col: "priority", dir: "desc" });
  const [filterSource,     setFilterSource]     = useState<string | null>(null);
  const [filterTiers,      setFilterTiers]      = useState<Set<number>>(new Set());
  const [filterClass,      setFilterClass]      = useState<string | null>(null);
  const [filterDecision,   setFilterDecision]   = useState<string | null>(null);
  const [filterImpactType, setFilterImpactType] = useState<string | null>(null);
  const [filterMultiSrc,   setFilterMultiSrc]   = useState(false);
  const [searchText,       setSearchText]       = useState("");
  const [overrides,      setOverrides]      = useState<Record<string, number>>({});
  const [expandedRows,   setExpandedRows]   = useState<Set<string>>(new Set());
  const [showAddModal,   setShowAddModal]   = useState(false);
  const [selectedEvents, setSelectedEvents] = useState<Set<string>>(new Set());
  const [merging,        setMerging]        = useState(false);
  const [mergeError,     setMergeError]     = useState<string | null>(null);

  function toggleRow(id: string) {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleSelect(eventId: string) {
    setSelectedEvents((prev) => {
      const next = new Set(prev);
      next.has(eventId) ? next.delete(eventId) : next.add(eventId);
      return next;
    });
  }

  const url = `${API}/api/signals?hours=${hours}&limit=500`;
  const { data: rawSignals, isLoading, error, mutate } = useSWR(url, fetcher, { refreshInterval: 30_000 });

  const signals: any[] = useMemo(() =>
    (rawSignals ?? []).map((s: any) => ({
      ...s,
      analyst_score: overrides[s.id] ?? s.analyst_score,
    })),
    [rawSignals, overrides]
  );

  const events = useMemo(() => groupIntoEvents(signals), [signals]);

  // ── Filter (operates on events) ─────────────────────────────────────────────
  const needle = searchText.trim().toLowerCase();

  const filtered = useMemo(() => events.filter((e) => {
    if (filterSource     && !e._memberSources.includes(filterSource))  return false;
    if (filterTiers.size > 0 && !filterTiers.has(e.impact_tier))       return false;
    if (filterClass      && e.event_class !== filterClass)             return false;
    if (filterDecision   && e.decision !== filterDecision)             return false;
    if (filterImpactType && e.impact_type !== filterImpactType)        return false;
    if (filterMultiSrc   && (e._sourceCount ?? 1) < 2)                 return false;
    if (needle) {
      const hay = e._members.map((m: any) => [
        m.description, m.what_changed, m.mechanism,
        m.scorer_reasoning, m.triage_reasoning, m.url,
        m.impact_type, m.source,
      ].filter(Boolean).join(" ")).join(" ").toLowerCase();
      if (!hay.includes(needle)) return false;
    }
    return true;
  }), [events, filterSource, filterTiers, filterClass, filterDecision, filterImpactType, filterMultiSrc, needle]);

  const visible = useMemo(() => sortSignals(filtered, sort), [filtered, sort]);
  const rankByPriority = sort?.col === "priority" && sort?.dir === "desc";

  function handleSort(key: string) {
    setSort((prev) =>
      prev?.col === key
        ? { col: key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { col: key, dir: key === "priority" || key === "llm_score" ? "desc" : "asc" }
    );
  }

  // ── Merge / detach handlers ─────────────────────────────────────────────────

  async function mergeSelected() {
    if (selectedEvents.size < 2) return;
    setMerging(true);
    setMergeError(null);
    try {
      const ids: string[] = [];
      for (const e of events) {
        if (selectedEvents.has(e._eventId)) {
          for (const m of e._members) ids.push(m.id);
        }
      }
      const r = await fetch(`${API}/api/signals/merge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signal_ids: ids }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail ?? `HTTP ${r.status}`);
      }
      setSelectedEvents(new Set());
      await mutate();
    } catch (err: any) {
      setMergeError(err?.message ?? "Merge failed — check console");
      console.error("merge error:", err);
    } finally {
      setMerging(false);
    }
  }

  async function detachSignal(signalId: string) {
    try {
      const r = await fetch(`${API}/api/signals/${signalId}/unlink`, { method: "POST" });
      if (!r.ok) throw new Error(`Detach failed (${r.status})`);
      await mutate();
    } catch (err) {
      console.error(err);
    }
  }

  // ── Counts for filter pills (event-level) ───────────────────────────────────

  const sourceCounts = useMemo(() => {
    const a: Record<string, number> = {};
    for (const e of events) for (const src of e._memberSources) a[src] = (a[src] || 0) + 1;
    return a;
  }, [events]);

  const classCounts = useMemo(() =>
    events.reduce((a: Record<string, number>, e: any) => {
      if (e.event_class) a[e.event_class] = (a[e.event_class] || 0) + 1; return a;
    }, {}), [events]);

  const tierCounts = useMemo(() =>
    events.reduce((a: Record<number, number>, e: any) => {
      if (e.impact_tier) a[e.impact_tier] = (a[e.impact_tier] || 0) + 1; return a;
    }, {}), [events]);

  const impactTypeCounts = useMemo(() =>
    events.reduce((a: Record<string, number>, e: any) => {
      if (e.impact_type) a[e.impact_type] = (a[e.impact_type] || 0) + 1; return a;
    }, {}), [events]);

  // ── KPI metrics ─────────────────────────────────────────────────────────────

  const kpis = useMemo(() => {
    const t1 = events.filter((e) => e.impact_tier === 1).length;
    const corroborated = events.filter((e) => (e._sourceCount ?? 1) > 1).length;
    const escalated = events.filter((e) => effScore(e) >= 0.6).length;
    const lead = events.reduce((best: any, e: any) =>
      (!best || (e._priority ?? 0) > (best._priority ?? 0)) ? e : best, null);
    const leadTitle = lead ? (lead.what_changed || lead.description || "—") : "—";
    return { t1, corroborated, escalated, leadTitle };
  }, [events]);

  const handleScoreSaved = useCallback(
    (id: string, score: number) => setOverrides((p) => ({ ...p, [id]: score })),
    []
  );

  const hasActiveFilters = filterSource || filterTiers.size > 0 || filterClass ||
    filterImpactType || filterMultiSrc || searchText;

  function clearAllFilters() {
    setFilterSource(null); setFilterTiers(new Set()); setFilterClass(null);
    setFilterImpactType(null); setFilterMultiSrc(false); setSearchText("");
  }

  // ── Active columns ──────────────────────────────────────────────────────────

  const activeCols = COLUMNS.filter((c) => isFull || c.essential);

  type SectionSpan = { section: "general" | "scorer" | "triage"; span: number; label: string };
  const sectionRow = useMemo((): SectionSpan[] => {
    if (!isFull) return [];
    const spans: SectionSpan[] = [];
    let cur: SectionSpan | null = null;
    for (const c of activeCols) {
      if (cur && cur.section === c.section) {
        cur.span++;
      } else {
        const labels = { general: "General", scorer: "II · Relevance Scorer", triage: "III · Triage Classifier" };
        cur = { section: c.section, span: 1, label: labels[c.section] };
        spans.push(cur);
      }
    }
    return spans;
  }, [activeCols, isFull]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100/50">
    <div className="p-6 lg:p-8 max-w-[1700px] mx-auto">

      {/* ── Header row ─────────────────────────────────────────────────── */}
      <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" title="Live · auto-refreshes every 30s" />
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Signal Intelligence</h1>
          </div>
          <p className="text-slate-500 text-sm">
            <span className="font-semibold text-slate-700 tabular-nums">{visible.length}</span> events
            {" · "}
            <span className="tabular-nums">{signals.length}</span> source signals
            {" · "}
            ranked by composite priority · live
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-900 text-white text-xs font-semibold
              hover:bg-slate-800 transition-colors shadow-sm"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
              <path d="M6 1a.75.75 0 0 1 .75.75v3.5h3.5a.75.75 0 0 1 0 1.5h-3.5v3.5a.75.75 0 0 1-1.5 0v-3.5H1.75a.75.75 0 0 1 0-1.5h3.5v-3.5A.75.75 0 0 1 6 1z"/>
            </svg>
            Add Signal
          </button>

          <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-xl p-1 shadow-sm">
            <button
              onClick={() => setIsFull(false)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors
                ${!isFull ? "bg-slate-900 text-white shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
            >
              Essential
            </button>
            <button
              onClick={() => setIsFull(true)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors
                ${isFull ? "bg-slate-900 text-white shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
            >
              Full
            </button>
          </div>
        </div>
      </div>

      {/* ── KPI strip ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <KpiCard label="Events Tracked" value={events.length} sub={`${signals.length} source signals`} accent="slate" />
        <KpiCard label="Critical · Tier 1" value={kpis.t1} sub="highest-impact events" accent="red"
          active={filterTiers.has(1) && filterTiers.size === 1}
          onClick={() => setFilterTiers((prev) => (prev.has(1) && prev.size === 1) ? new Set() : new Set([1]))} />
        <KpiCard label="Corroborated" value={kpis.corroborated} sub="multi-source events" accent="blue"
          active={filterMultiSrc}
          onClick={() => setFilterMultiSrc((v) => !v)} />
        <KpiCard label="Escalated · ≥0.60" value={kpis.escalated} sub={kpis.leadTitle} accent="amber" />
      </div>

      {/* ── Filter bar ─────────────────────────────────────────────────── */}
      <div className="bg-white border border-slate-200 rounded-2xl shadow-sm p-3.5 mb-5 flex flex-col gap-2.5">

        {/* Row 0: Search + time window */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative flex-1 min-w-[240px] max-w-md">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
              width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
              <path d="M6.5 1a5.5 5.5 0 1 0 3.89 9.453l3.329 3.329a.75.75 0 1 0 1.06-1.06l-3.328-3.33A5.5 5.5 0 0 0 6.5 1zm-4 5.5a4 4 0 1 1 8 0 4 4 0 0 1-8 0z"/>
            </svg>
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Search description, mechanism, reasoning, URL…"
              className="w-full pl-9 pr-8 py-2 text-xs rounded-xl border border-slate-200
                bg-slate-50 placeholder-slate-400 text-slate-700
                focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-300 focus:bg-white
                transition-colors"
            />
            {searchText && (
              <button
                onClick={() => setSearchText("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                aria-label="Clear search"
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
                  <path d="M1.72 1.72a.75.75 0 0 1 1.06 0L6 4.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L7.06 6l3.22 3.22a.75.75 0 1 1-1.06 1.06L6 7.06 2.78 10.28a.75.75 0 0 1-1.06-1.06L4.94 6 1.72 2.78a.75.75 0 0 1 0-1.06z"/>
                </svg>
              </button>
            )}
          </div>

          <div className="ml-auto flex items-center gap-1 bg-slate-100 rounded-xl p-1">
            {HOUR_OPTIONS.map((o) => (
              <button key={o.value} onClick={() => setHours(o.value)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors
                  ${hours === o.value ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}>
                {o.label}
              </button>
            ))}
          </div>
        </div>

        {/* Row 1: Source */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider w-14 shrink-0">Source</span>
          <FilterPill label="All" count={events.length} active={!filterSource} onClick={() => setFilterSource(null)} />
          {Object.keys(SOURCE_META).map((src) => {
            const m = SOURCE_META[src];
            const cnt = sourceCounts[src] ?? 0;
            if (!cnt) return null;
            return (
              <FilterPill key={src}
                label={`${m.icon} ${m.label}`}
                count={cnt}
                active={filterSource === src}
                onClick={() => setFilterSource(filterSource === src ? null : src)}
              />
            );
          })}
        </div>

        {/* Row 2: Tier */}
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider w-14 shrink-0">Tier</span>
          <FilterPill label="All" active={filterTiers.size === 0}
            onClick={() => setFilterTiers(new Set())} />
          {TIER_OPTS.map((t) => {
            const cnt = tierCounts[t] ?? 0;
            if (!cnt) return null;
            const active = filterTiers.has(t);
            return (
              <FilterPill key={t} label={`T${t}`} count={cnt} active={active}
                onClick={() => setFilterTiers((prev) => {
                  const next = new Set(prev);
                  active ? next.delete(t) : next.add(t);
                  return next;
                })}
              />
            );
          })}
        </div>

        {/* Row 3: Event class */}
        {Object.keys(classCounts).length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider w-14 shrink-0">Class</span>
            <FilterPill label="All" active={!filterClass} onClick={() => setFilterClass(null)} />
            {Object.entries(classCounts).map(([ec, cnt]) => {
              const m = EVENT_CLASS_META[ec];
              if (!m) return null;
              return (
                <FilterPill key={ec} label={m.label} count={cnt as number}
                  active={filterClass === ec}
                  onClick={() => setFilterClass(filterClass === ec ? null : ec)}
                />
              );
            })}
          </div>
        )}

        {/* Row 4: Impact type */}
        {Object.keys(impactTypeCounts).length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider w-14 shrink-0">Impact</span>
            <FilterPill label="All" active={!filterImpactType} onClick={() => setFilterImpactType(null)} />
            {Object.entries(impactTypeCounts)
              .sort((a, b) => (b[1] as number) - (a[1] as number))
              .map(([type, cnt]) => (
                <FilterPill key={type}
                  label={type}
                  count={cnt as number}
                  active={filterImpactType === type}
                  onClick={() => setFilterImpactType(filterImpactType === type ? null : type)}
                />
              ))}
          </div>
        )}
      </div>

      {/* ── Merge action bar ───────────────────────────────────────────── */}
      {selectedEvents.size > 0 && (
        <div className="mb-4 flex flex-col gap-1.5">
          <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-blue-50 border border-blue-200">
            <span className="text-sm font-medium text-blue-900">
              {selectedEvents.size} event{selectedEvents.size !== 1 ? "s" : ""} selected
            </span>
            <button
              onClick={mergeSelected}
              disabled={selectedEvents.size < 2 || merging}
              className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold
                hover:bg-blue-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {merging ? "Merging…" : "Merge into one event"}
            </button>
            {selectedEvents.size < 2 && (
              <span className="text-xs text-blue-500">Select at least 2 events to merge</span>
            )}
            <button
              onClick={() => { setSelectedEvents(new Set()); setMergeError(null); }}
              className="ml-auto px-2.5 py-1 text-xs text-slate-500 hover:text-slate-800 hover:bg-white/60 rounded-lg transition-colors"
            >
              Clear selection
            </button>
          </div>
          {mergeError && (
            <div className="px-4 py-2 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700 font-medium">
              ✗ {mergeError}
            </div>
          )}
        </div>
      )}

      {/* ── Table ──────────────────────────────────────────────────────── */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-x-auto">
        <table className="w-full text-sm border-collapse">

          {isFull && sectionRow.length > 0 && (
            <thead>
              <tr className="border-b border-slate-100">
                {sectionRow.map((s, i) => (
                  <th key={i} colSpan={s.span}
                    className={`px-2.5 py-1.5 text-left text-[9px] font-bold uppercase tracking-widest
                      ${i === 0 ? "pl-4" : ""}
                      ${s.section === "scorer" ? "text-violet-500 bg-violet-50/40 border-l-2 border-l-violet-200" : ""}
                      ${s.section === "triage"  ? "text-teal-600  bg-teal-50/40  border-l-2 border-l-teal-200"  : ""}
                      ${s.section === "general" ? "text-slate-400" : ""}`}
                  >
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
          )}

          <thead className="sticky top-0 z-10">
            <tr className="border-b border-slate-200 bg-slate-50/95 backdrop-blur supports-[backdrop-filter]:bg-slate-50/80">
              {activeCols.map((col) => (
                <ColHeader key={col.key} col={col} sort={sort} onSort={handleSort} />
              ))}
            </tr>
          </thead>

          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={activeCols.length} className="px-4 py-12 text-center text-slate-400 text-sm animate-pulse">
                  Loading signals…
                </td>
              </tr>
            )}
            {!isLoading && error && (
              <tr>
                <td colSpan={activeCols.length} className="px-4 py-12 text-center text-sm">
                  <div className="flex flex-col items-center gap-2">
                    <span className="text-red-500 font-medium">API unavailable</span>
                    <span className="text-slate-400 text-xs max-w-sm">
                      {String(error?.message ?? error).slice(0, 120)}
                    </span>
                    <span className="text-slate-400 text-xs">
                      The database may be suspended — check the Neon console and resume the compute endpoint.
                    </span>
                  </div>
                </td>
              </tr>
            )}
            {!isLoading && visible.length === 0 && (
              <tr>
                <td colSpan={activeCols.length} className="px-4 py-12 text-center text-slate-400 text-sm">
                  No events match the current filters.
                </td>
              </tr>
            )}
            {visible.map((signal: any, idx: number) => {
              const isExpanded = expandedRows.has(signal.id);
              const isSelected = selectedEvents.has(signal._eventId);
              const multi = (signal._sourceCount ?? 1) > 1;
              const railColor = TIER_RAIL[signal.impact_tier as number] ?? "border-l-transparent";
              return (
              <Fragment key={signal._eventId}>
              <tr
                onClick={() => toggleRow(signal.id)}
                className={`group border-b border-slate-100 cursor-pointer transition-colors
                  ${isSelected ? "bg-blue-50/60" : isExpanded ? "bg-slate-50" : "hover:bg-slate-50/70"}`}>
                {activeCols.map((col, ci) => (
                  <td
                    key={col.key}
                    className={`px-2.5 py-3.5 align-top ${col.width}
                      ${col.key === "priority" ? `pl-4 border-l-[3px] ${railColor}` : ""}
                      ${col.key === "assess"  ? "pr-4 opacity-0 group-hover:opacity-100 transition-opacity" : ""}
                      ${col.section === "scorer" && isFull ? "bg-violet-50/20 border-l border-l-violet-100" : ""}
                      ${col.section === "triage"  && isFull ? "bg-teal-50/20  border-l border-l-teal-100" : ""}`}
                  >
                    {col.key === "priority" ? (
                      <div className="flex items-start gap-2">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onClick={(e) => e.stopPropagation()}
                          onChange={() => toggleSelect(signal._eventId)}
                          className="mt-0.5 accent-blue-600 cursor-pointer shrink-0"
                          title="Select event for merge"
                        />
                        <CellContent colKey={col.key} signal={signal} onScoreSaved={handleScoreSaved} expanded={isExpanded} rank={idx + 1} rankByPriority={rankByPriority} />
                      </div>
                    ) : (
                      <CellContent colKey={col.key} signal={signal} onScoreSaved={handleScoreSaved} expanded={isExpanded} rank={idx + 1} rankByPriority={rankByPriority} />
                    )}
                  </td>
                ))}
              </tr>

              {/* Sources sub-panel — the individual articles behind this event */}
              {isExpanded && multi && (
                <tr className="bg-slate-50/80 border-b border-slate-100">
                  <td colSpan={activeCols.length} className="px-4 pb-3 pt-0">
                    <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2 pl-6">
                      {signal._sourceCount} sources covering this event
                    </div>
                    <div className="flex flex-col gap-1.5 pl-6">
                      {signal._members.map((m: any) => (
                        <div key={m.id}
                          className="flex items-center gap-2 text-xs bg-white border border-slate-200 rounded-lg px-2.5 py-1.5">
                          <SourceBadge source={m.source} />
                          <span className="flex-1 text-slate-700 truncate">{m.description}</span>
                          {m.occurred_at && (
                            <span className="text-[10px] text-slate-400 whitespace-nowrap">
                              {new Date(m.occurred_at).toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
                            </span>
                          )}
                          {m.url && (
                            <a href={m.url} target="_blank" rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="text-[10px] text-blue-500 hover:text-blue-700 whitespace-nowrap">↗ open</a>
                          )}
                          <button
                            onClick={(e) => { e.stopPropagation(); detachSignal(m.id); }}
                            className="text-[10px] text-slate-400 hover:text-red-600 whitespace-nowrap font-medium"
                            title="Remove this article from the event (make it its own event)"
                          >
                            detach
                          </button>
                        </div>
                      ))}
                    </div>
                  </td>
                </tr>
              )}
              </Fragment>
            )})}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="mt-3 flex items-center gap-3 text-xs text-slate-400 flex-wrap">
        <span className="tabular-nums">{visible.length} events shown</span>
        {events.length !== visible.length && (
          <span className="tabular-nums">· {events.length - visible.length} hidden by filters</span>
        )}
        {sort && (
          <span>· sorted by {COLUMNS.find((c) => c.key === sort.col)?.label} {sort.dir === "desc" ? "↓" : "↑"}</span>
        )}
        {hasActiveFilters && (
          <span className="ml-auto flex items-center gap-1.5">
            <span className="text-slate-300">|</span>
            {filterSource     && <span className="px-2 py-0.5 bg-slate-100 rounded-full">{filterSource}</span>}
            {[...filterTiers].map(t => <span key={t} className="px-2 py-0.5 bg-slate-100 rounded-full">T{t}</span>)}
            {filterClass      && <span className="px-2 py-0.5 bg-teal-50 text-teal-700 rounded-full">{filterClass}</span>}
            {filterImpactType && <span className="px-2 py-0.5 bg-violet-50 text-violet-700 rounded-full">{filterImpactType}</span>}
            {filterMultiSrc   && <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full">multi-source</span>}
            {searchText       && <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-full">"{searchText}"</span>}
            <button
              onClick={clearAllFilters}
              className="px-2 py-0.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-full transition-colors"
            >
              Clear all
            </button>
          </span>
        )}
      </div>

      {showAddModal && (
        <AddSignalModal
          onClose={() => setShowAddModal(false)}
          onAdded={() => { void mutate(); }}
        />
      )}
    </div>
    </div>
  );
}
