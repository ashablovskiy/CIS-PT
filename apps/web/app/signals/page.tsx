"use client";

import { useState, useCallback, useMemo, useRef, useEffect } from "react";
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

const SOURCE_META: Record<string, { icon: string; label: string; color: string }> = {
  prices:    { icon: "💹", label: "Prices",    color: "bg-amber-50 text-amber-700 border-amber-200" },
  gdelt:     { icon: "🌍", label: "GDELT",     color: "bg-purple-50 text-purple-700 border-purple-200" },
  logistics: { icon: "🚢", label: "Logistics", color: "bg-blue-50 text-blue-700 border-blue-200" },
  press:     { icon: "📰", label: "Press",     color: "bg-slate-50 text-slate-600 border-slate-200" },
  demand:    { icon: "📈", label: "Demand",    color: "bg-teal-50 text-teal-700 border-teal-200" },
  sec:       { icon: "📄", label: "SEC",       color: "bg-gray-50 text-gray-600 border-gray-200" },
  ir:        { icon: "🏭", label: "IR / OEM",  color: "bg-orange-50 text-orange-700 border-orange-200" },
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

// ── Small reusable components ─────────────────────────────────────────────────

function Chip({ label, color }: { label: string; color: string }) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border whitespace-nowrap ${color}`}>
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
                   "bg-green-50 text-green-700 border-green-200";
  if (overridden) {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold border border-dashed border-violet-300 bg-violet-50 text-violet-700 whitespace-nowrap">
        {score.toFixed(2)} <span className="opacity-60 font-normal">·ed</span>
      </span>
    );
  }
  return <Chip label={score.toFixed(2)} color={color} />;
}

function DirectionBadge({ dir }: { dir: string | undefined }) {
  if (!dir) return <span className="text-slate-300 text-xs">—</span>;
  const map: Record<string, { icon: string; color: string }> = {
    negative: { icon: "▼", color: "bg-red-50 text-red-700 border-red-200" },
    positive: { icon: "▲", color: "bg-green-50 text-green-700 border-green-200" },
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
        className="text-xs text-slate-400 hover:text-slate-700 hover:underline transition-colors whitespace-nowrap"
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
  th?: string; // extra th className
};

const SECTION_COLORS = {
  general: "",
  scorer:  "text-violet-500",
  triage:  "text-teal-600",
};

const SECTION_BG = {
  general: "",
  scorer:  "bg-violet-50/40",
  triage:  "bg-teal-50/40",
};

const COLUMNS: ColDef[] = [
  // I. GENERAL
  { key: "source",      label: "Source",       section: "general", essential: true,  width: "w-[110px]",
    sortValue: (s) => s.source },
  { key: "description", label: "Signal",        section: "general", essential: true,  width: "min-w-[220px] max-w-[320px]" },
  { key: "occurred_at", label: "Time",           section: "general", essential: true,  width: "w-[90px]",
    sortValue: (s) => s.occurred_at },
  { key: "ingested_at", label: "Ingested",       section: "general", essential: true,  width: "w-[90px]",
    sortValue: (s) => s.ingested_at },

  // II. SCORER
  { key: "impact_tier",      label: "Tier",         section: "scorer", essential: true,  width: "w-[56px]",
    sortValue: (s) => s.impact_tier ?? 99 },
  { key: "what_changed",     label: "What Changed", section: "scorer", essential: true,  width: "min-w-[160px] max-w-[240px]" },
  { key: "mechanism",        label: "Mechanism",    section: "scorer", essential: true,  width: "min-w-[180px] max-w-[260px]" },
  { key: "llm_score",        label: "Relevance",    section: "scorer", essential: false, width: "w-[80px]",
    sortValue: (s) => s.llm_score ?? 0 },
  { key: "signal_kind",      label: "Kind",         section: "scorer", essential: false, width: "w-[110px]",
    sortValue: (s) => s.signal_kind ?? "" },
  { key: "impact_type",      label: "Impact Type",  section: "scorer", essential: false, width: "w-[150px]",
    sortValue: (s) => s.impact_type ?? "" },
  { key: "scorer_reasoning", label: "Reasoning",    section: "scorer", essential: false, width: "min-w-[180px] max-w-[260px]" },

  // III. TRIAGE
  { key: "graph_entities",          label: "Entities",      section: "triage", essential: true,  width: "min-w-[160px] max-w-[220px]" },
  { key: "geo_tags",                label: "Geo",           section: "triage", essential: true,  width: "min-w-[120px] max-w-[180px]" },
  { key: "triage_reasoning",        label: "Reasoning",     section: "triage", essential: true,  width: "min-w-[180px] max-w-[260px]" },
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
  { key: "assess", label: "Assess", section: "general", essential: true, width: "w-[130px]" },
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

// ── Cell renderer ─────────────────────────────────────────────────────────────

function CellContent({ colKey, signal, onScoreSaved, expanded }: {
  colKey: string;
  signal: any;
  onScoreSaved: (id: string, score: number) => void;
  expanded: boolean;
}) {
  const src = SOURCE_META[signal.source] ?? { icon: "📌", label: signal.source, color: "bg-slate-50 text-slate-500 border-slate-200" };

  switch (colKey) {
    case "source":
      return (
        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium border ${src.color}`}>
          {src.icon} {src.label}
        </span>
      );

    case "description":
      return (
        <div className="flex flex-col gap-1">
          <div className={`text-sm text-slate-800 leading-snug ${expanded ? "" : "line-clamp-2"}`}>
            {signal.description || <span className="text-slate-400 italic">No description</span>}
          </div>
          {signal.price_move && (
            <span className="text-xs text-slate-500 font-mono">{signal.price_move}</span>
          )}
          {signal.url && (
            <a href={signal.url} target="_blank" rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-[10px] text-slate-400 hover:text-blue-500 transition-colors">
              ↗ source
            </a>
          )}
        </div>
      );

    case "occurred_at":
      return signal.occurred_at ? (
        <span className="text-xs text-slate-600 whitespace-nowrap">
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
        <span className={`text-xs text-slate-600 leading-snug italic ${expanded ? "" : "line-clamp-3"}`}>{signal.mechanism}</span>
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
        <span className={`text-[10px] text-slate-500 leading-snug italic ${expanded ? "" : "line-clamp-3"}`}>{signal.scorer_reasoning}</span>
      ) : <span className="text-slate-300 text-xs">—</span>;

    case "graph_entities":
      return <EntityPills entities={signal.graph_entities} />;

    case "geo_tags":
      return <GeoTags tags={signal.geo_tags} />;

    case "triage_reasoning":
      return signal.triage_reasoning ? (
        <span className={`text-[10px] text-slate-500 leading-snug italic ${expanded ? "" : "line-clamp-3"}`}>{signal.triage_reasoning}</span>
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
        <span className={`text-xs font-mono font-semibold ${
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

function ColHeader({
  col, sort, onSort,
}: {
  col: ColDef;
  sort: SortState | null;
  onSort: (key: string) => void;
}) {
  const active = sort?.col === col.key;
  const canSort = !!col.sortValue;
  return (
    <th
      className={`px-2 py-2 text-left text-[10px] font-semibold uppercase tracking-wider select-none
        ${SECTION_COLORS[col.section]}
        ${canSort ? "cursor-pointer hover:bg-slate-50" : ""}
        ${col.key === "source" ? "pl-4" : ""}
        ${col.key === "assess" ? "pr-4" : ""}`}
      onClick={canSort ? () => onSort(col.key) : undefined}
    >
      <span className="flex items-center gap-1">
        {col.label}
        {canSort && (
          <span className={`text-[10px] ${active ? "opacity-100" : "opacity-25"}`}>
            {active && sort?.dir === "asc" ? "↑" : active && sort?.dir === "desc" ? "↓" : "↕"}
          </span>
        )}
      </span>
    </th>
  );
}

// ── Filter pill button ────────────────────────────────────────────────────────

function FilterPill({
  label, count, active, onClick,
}: {
  label: string; count?: number; active: boolean; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex items-center gap-1.5
        ${active ? "bg-slate-800 text-white" : "bg-white text-slate-600 border border-slate-200 hover:border-slate-300"}`}
    >
      {label}
      {count != null && (
        <span className={`text-[10px] ${active ? "text-slate-300" : "text-slate-400"}`}>{count}</span>
      )}
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

  // Close on Escape
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", h);
    return () => document.removeEventListener("keydown", h);
  }, [onClose]);

  // Focus URL input on open
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

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-900">Add Signal Manually</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 transition-colors">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22z"/>
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-100">
          {(["url", "file"] as const).map((t) => (
            <button key={t} onClick={() => { setTab(t); setStatus("idle"); setResult(null); }}
              className={`flex-1 py-2.5 text-sm font-medium transition-colors
                ${tab === t ? "text-blue-600 border-b-2 border-blue-600" : "text-slate-500 hover:text-slate-800"}`}>
              {t === "url" ? "🔗  Paste URL" : "📎  Upload File"}
            </button>
          ))}
        </div>

        {/* Body */}
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

          {/* Error */}
          {status === "error" && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
              {message}
            </div>
          )}

          {/* Result */}
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
  const [hours,          setHours]          = useState(48);
  const [isFull,         setIsFull]         = useState(false);
  const [sort,           setSort]           = useState<SortState | null>({ col: "occurred_at", dir: "desc" });
  const [filterSource,   setFilterSource]   = useState<string | null>(null);
  const [filterTiers,    setFilterTiers]    = useState<Set<number>>(new Set());
  const [filterClass,    setFilterClass]    = useState<string | null>(null);
  const [filterDecision, setFilterDecision] = useState<string | null>(null);
  const [overrides,      setOverrides]      = useState<Record<string, number>>({});
  const [expandedRows,   setExpandedRows]   = useState<Set<string>>(new Set());
  const [showAddModal,   setShowAddModal]   = useState(false);

  function toggleRow(id: string) {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
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

  // ── Filter ────────────────────────────────────────────────────────────────

  const filtered = useMemo(() => signals.filter((s) => {
    if (filterSource   && s.source !== filterSource)               return false;
    if (filterTiers.size > 0 && !filterTiers.has(s.impact_tier))  return false;
    if (filterClass    && s.event_class !== filterClass)           return false;
    if (filterDecision && s.decision !== filterDecision)           return false;
    return true;
  }), [signals, filterSource, filterTiers, filterClass, filterDecision]);

  // ── Sort ──────────────────────────────────────────────────────────────────

  const visible = useMemo(() => sortSignals(filtered, sort), [filtered, sort]);

  // ── Sort toggle ───────────────────────────────────────────────────────────

  function handleSort(key: string) {
    setSort((prev) =>
      prev?.col === key
        ? { col: key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { col: key, dir: "asc" }
    );
  }

  // ── Counts for filter pills ───────────────────────────────────────────────

  const sourceCounts = useMemo(() =>
    signals.reduce((a: Record<string, number>, s: any) => {
      a[s.source] = (a[s.source] || 0) + 1; return a;
    }, {}), [signals]);

  const classCounts = useMemo(() =>
    signals.reduce((a: Record<string, number>, s: any) => {
      if (s.event_class) a[s.event_class] = (a[s.event_class] || 0) + 1; return a;
    }, {}), [signals]);

  const tierCounts = useMemo(() =>
    signals.reduce((a: Record<number, number>, s: any) => {
      if (s.impact_tier) a[s.impact_tier] = (a[s.impact_tier] || 0) + 1; return a;
    }, {}), [signals]);

  const handleScoreSaved = useCallback(
    (id: string, score: number) => setOverrides((p) => ({ ...p, [id]: score })),
    []
  );

  // ── Active columns ────────────────────────────────────────────────────────

  const activeCols = COLUMNS.filter((c) => isFull || c.essential);

  // ── Section dividers for full view header ─────────────────────────────────

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
    <div className="p-6 max-w-full">

      {/* ── Header row ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Signals</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            {visible.length} signal{visible.length !== 1 ? "s" : ""} · auto-refreshes every 30 s
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold
              hover:bg-blue-700 transition-colors shadow-sm"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
              <path d="M6 1a.75.75 0 0 1 .75.75v3.5h3.5a.75.75 0 0 1 0 1.5h-3.5v3.5a.75.75 0 0 1-1.5 0v-3.5H1.75a.75.75 0 0 1 0-1.5h3.5v-3.5A.75.75 0 0 1 6 1z"/>
            </svg>
            Add Signal
          </button>

          {/* View toggle */}
          <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
          <button
            onClick={() => setIsFull(false)}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors
              ${!isFull ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
          >
            Essential
          </button>
          <button
            onClick={() => setIsFull(true)}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold transition-colors
              ${isFull ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
          >
            Full
          </button>
        </div>
        </div>{/* end actions */}
      </div>

      {/* ── Filter bar ─────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-2 mb-4">

        {/* Row 1: Source + time window */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider w-12">Source</span>
          <FilterPill label="All" count={signals.length} active={!filterSource} onClick={() => setFilterSource(null)} />
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

          {/* Time window — pushed right */}
          <div className="ml-auto flex items-center gap-1 bg-slate-100 rounded-lg p-1">
            {HOUR_OPTIONS.map((o) => (
              <button key={o.value} onClick={() => setHours(o.value)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors
                  ${hours === o.value ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}>
                {o.label}
              </button>
            ))}
          </div>
        </div>

        {/* Row 2: Tier */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider w-12">Tier</span>
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

        {/* Row 3: Event class (only show classes that have signals) */}
        {Object.keys(classCounts).length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider w-12">Class</span>
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
      </div>

      {/* ── Table ──────────────────────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-sm border-collapse">

          {/* Full view: section header row */}
          {isFull && sectionRow.length > 0 && (
            <thead>
              <tr className="border-b border-slate-100">
                {sectionRow.map((s, i) => (
                  <th key={i} colSpan={s.span}
                    className={`px-2 py-1 text-left text-[9px] font-bold uppercase tracking-widest
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

          {/* Column header row */}
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50/50">
              {activeCols.map((col) => (
                <ColHeader key={col.key} col={col} sort={sort} onSort={handleSort} />
              ))}
            </tr>
          </thead>

          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={activeCols.length} className="px-4 py-10 text-center text-slate-400 text-sm animate-pulse">
                  Loading signals…
                </td>
              </tr>
            )}
            {!isLoading && error && (
              <tr>
                <td colSpan={activeCols.length} className="px-4 py-10 text-center text-sm">
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
                <td colSpan={activeCols.length} className="px-4 py-10 text-center text-slate-400 text-sm">
                  No signals match the current filters.
                </td>
              </tr>
            )}
            {visible.map((signal: any) => {
              const isExpanded = expandedRows.has(signal.id);
              return (
              <tr key={signal.id}
                onClick={() => toggleRow(signal.id)}
                className={`group border-b border-slate-100 last:border-0 cursor-pointer transition-colors
                  ${isExpanded ? "bg-slate-50" : "hover:bg-slate-50/70"}`}>
                {activeCols.map((col) => (
                  <td
                    key={col.key}
                    className={`px-2 py-3 align-top ${col.width}
                      ${col.key === "source"  ? "pl-4" : ""}
                      ${col.key === "assess"  ? "pr-4 opacity-0 group-hover:opacity-100 transition-opacity" : ""}
                      ${col.section === "scorer" && isFull ? "bg-violet-50/20 border-l border-l-violet-100 first:border-l-0" : ""}
                      ${col.section === "triage"  && isFull ? "bg-teal-50/20  border-l border-l-teal-100  first:border-l-0" : ""}`}
                  >
                    <CellContent colKey={col.key} signal={signal} onScoreSaved={handleScoreSaved} expanded={isExpanded} />
                  </td>
                ))}
              </tr>
            )})}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="mt-2 flex items-center gap-4 text-xs text-slate-400">
        <span>{visible.length} signals shown</span>
        {signals.length !== visible.length && (
          <span>· {signals.length - visible.length} hidden by filters</span>
        )}
        {sort && (
          <span>· sorted by {COLUMNS.find((c) => c.key === sort.col)?.label} {sort.dir}</span>
        )}
      </div>

      {showAddModal && (
        <AddSignalModal
          onClose={() => setShowAddModal(false)}
          onAdded={() => { void mutate(); }}
        />
      )}
    </div>
  );
}
