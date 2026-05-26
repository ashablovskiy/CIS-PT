"use client";

import { useState, useCallback } from "react";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

// ── Source metadata ───────────────────────────────────────────────────────────

const SOURCE_META: Record<string, { icon: string; label: string; color: string }> = {
  prices:    { icon: "💹", label: "Prices",    color: "bg-amber-50 text-amber-700 border-amber-200" },
  gdelt:     { icon: "🌍", label: "GDELT",     color: "bg-purple-50 text-purple-700 border-purple-200" },
  logistics: { icon: "🚢", label: "Logistics", color: "bg-blue-50 text-blue-700 border-blue-200" },
  press:     { icon: "📰", label: "Press",     color: "bg-slate-50 text-slate-600 border-slate-200" },
  demand:    { icon: "📈", label: "Demand",    color: "bg-teal-50 text-teal-700 border-teal-200" },
  sec:       { icon: "📄", label: "SEC",       color: "bg-gray-50 text-gray-600 border-gray-200" },
};

// ── Impact type chip colors (controlled vocabulary from scorer) ───────────────

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

// ── Score → color gradient ────────────────────────────────────────────────────

function scoreColor(score: number): { bg: string; text: string; dot: string } {
  if (score >= 0.8) return { bg: "bg-red-50",    text: "text-red-700",    dot: "bg-red-500" };
  if (score >= 0.6) return { bg: "bg-orange-50", text: "text-orange-700", dot: "bg-orange-500" };
  if (score >= 0.4) return { bg: "bg-amber-50",  text: "text-amber-700",  dot: "bg-amber-400" };
  return               { bg: "bg-green-50",  text: "text-green-700",  dot: "bg-green-500" };
}

function ScorePill({ score, overridden }: { score: number; overridden?: boolean }) {
  const c = scoreColor(score);
  if (overridden) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold border border-dashed border-violet-300 bg-violet-50 text-violet-700">
        <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
        {score.toFixed(2)}
        <span className="opacity-60 font-normal">·edited</span>
      </span>
    );
  }
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold ${c.bg} ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {score.toFixed(2)}
    </span>
  );
}

// ── Price move badge ──────────────────────────────────────────────────────────

function PriceMoveBadge({ move }: { move: string }) {
  const isUp = move.includes("+");
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded
      ${isUp ? "bg-red-50 text-red-600" : "bg-green-50 text-green-700"}`}>
      {isUp ? "▲" : "▼"} {move}
    </span>
  );
}

// ── Manual assess (always shows "Set score" entry; pill is only in Score col) ─

function AssessCell({ signal, onSaved }: {
  signal: any;
  onSaved: (id: string, score: number) => void;
}) {
  const seed = signal.analyst_score ?? signal.llm_score ?? 0.5;
  const [open, setOpen]     = useState(false);
  const [draft, setDraft]   = useState<number>(seed);
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
        onClick={() => { setDraft(seed); setOpen(true); }}
        className="text-xs text-slate-400 hover:text-slate-700 hover:underline transition-colors whitespace-nowrap"
      >
        {signal.analyst_score != null ? "Change score" : "Set score"}
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-1.5 min-w-[150px]">
      <div className="flex items-center gap-2">
        <input
          type="range"
          min={0} max={1} step={0.01}
          value={draft}
          onChange={(e) => setDraft(parseFloat(e.target.value))}
          className="w-24 accent-violet-500 cursor-pointer"
        />
        <span className="text-xs font-mono text-slate-700 w-9">{draft.toFixed(2)}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <button
          onClick={handleSave}
          disabled={saving}
          className="text-xs px-2 py-0.5 bg-violet-600 text-white rounded hover:bg-violet-700 disabled:opacity-50"
        >
          {saving ? "…" : "Save"}
        </button>
        <button
          onClick={() => setOpen(false)}
          className="text-xs text-slate-400 hover:text-slate-600"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ── Tier badge ────────────────────────────────────────────────────────────────

function TierBadge({ tier }: { tier: number | null | undefined }) {
  if (tier == null) {
    return <span className="text-xs text-slate-300">—</span>;
  }
  const map: Record<number, string> = {
    1: "bg-red-50 text-red-600 border-red-200",
    2: "bg-orange-50 text-orange-600 border-orange-200",
    3: "bg-amber-50 text-amber-600 border-amber-200",
    4: "bg-slate-50 text-slate-400 border-slate-200",
  };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold border ${map[tier] ?? IMPACT_FALLBACK}`}>
      T{tier}
    </span>
  );
}

// ── Signal row ────────────────────────────────────────────────────────────────

function SignalRow({ signal, onScoreSaved }: {
  signal: any;
  onScoreSaved: (id: string, score: number) => void;
}) {
  const src = SOURCE_META[signal.source] ?? { icon: "📌", label: signal.source, color: "bg-slate-50 text-slate-500 border-slate-200" };

  // Effective display score: analyst override beats LLM
  const isOverridden = signal.analyst_score != null;
  const displayScore: number | null = isOverridden
    ? signal.analyst_score
    : (typeof signal.llm_score === "number" ? signal.llm_score : null);

  const impactTypeLabel = signal.impact_type ?? "Unrated";
  const impactColor     = IMPACT_COLORS[impactTypeLabel] ?? IMPACT_FALLBACK;

  return (
    <tr className="group hover:bg-slate-50/70 transition-colors border-b border-slate-100 last:border-0">

      {/* Source */}
      <td className="pl-5 pr-2 py-3 w-[100px]">
        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium border ${src.color}`}>
          <span>{src.icon}</span>
          {src.label}
        </span>
      </td>

      {/* Description + price move */}
      <td className="px-2 py-3">
        <div className="flex flex-col gap-1">
          <div className="text-sm text-slate-800 leading-snug line-clamp-2">
            {signal.description || <span className="text-slate-400 italic">No description</span>}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {signal.price_move && <PriceMoveBadge move={signal.price_move} />}
            {signal.url && (
              <a
                href={signal.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-slate-400 hover:text-blue-500 transition-colors"
              >
                ↗ source
              </a>
            )}
          </div>
        </div>
      </td>

      {/* Impact type — domain-specific mechanism */}
      <td className="px-2 py-3 w-[160px]">
        <div className="flex items-center gap-1.5">
          <TierBadge tier={signal.impact_tier} />
          <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${impactColor}`}>
            {impactTypeLabel}
          </span>
        </div>
      </td>

      {/* Score */}
      <td className="px-2 py-3 w-[90px]">
        {displayScore != null
          ? <ScorePill score={displayScore} overridden={isOverridden} />
          : <span className="text-slate-300 text-xs">—</span>}
      </td>

      {/* Age */}
      <td className="px-2 py-3 w-[100px]">
        <span className="text-xs text-slate-400 whitespace-nowrap">
          {signal.ingested_at
            ? formatDistanceToNow(new Date(signal.ingested_at), { addSuffix: true })
            : "—"}
        </span>
      </td>

      {/* Manual assess */}
      <td className="px-2 pr-5 py-3 w-[160px]">
        <div className="opacity-0 group-hover:opacity-100 transition-opacity">
          <AssessCell signal={signal} onSaved={onScoreSaved} />
        </div>
      </td>
    </tr>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const HOUR_OPTIONS = [
  { label: "Last 24h", value: 24 },
  { label: "Last 48h", value: 48 },
  { label: "Last 7d",  value: 168 },
  { label: "Last 30d", value: 720 },
];

export default function SignalsPage() {
  const [hours,        setHours]        = useState(48);
  const [showAll,      setShowAll]      = useState(false);
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  // Local overrides (optimistic, layered on top of DB)
  const [overrides, setOverrides] = useState<Record<string, number>>({});

  const url = `${API}/api/signals?hours=${hours}&limit=200`;
  const { data: rawSignals, isLoading } = useSWR(url, fetcher, { refreshInterval: 30_000 });

  // Merge in local optimistic overrides
  const signals: any[] = (rawSignals ?? []).map((s: any) => ({
    ...s,
    analyst_score: overrides[s.id] ?? s.analyst_score,
  }));

  // Source filter
  const afterSource = sourceFilter === "all"
    ? signals
    : signals.filter((s) => s.source === sourceFilter);

  // Impactful = tier 1 or 2, OR (legacy untiered AND effective score ≥ 0.5)
  // Crude oil -4.2% scored as Tier 3 is correctly hidden
  function isImpactful(s: any): boolean {
    if (s.impact_tier != null) return s.impact_tier <= 2;
    const eff = s.analyst_score ?? s.llm_score ?? 0;
    return eff >= 0.5;  // legacy fallback for untiered signals
  }

  const highImpact = afterSource.filter(isImpactful);
  const lowImpact  = afterSource.filter((s: any) => !isImpactful(s));
  const visible    = showAll ? afterSource : highImpact;
  const hiddenCount = lowImpact.length;

  const handleScoreSaved = useCallback((id: string, score: number) => {
    setOverrides((prev) => ({ ...prev, [id]: score }));
  }, []);

  const sourceCounts = signals.reduce((acc: Record<string, number>, s: any) => {
    acc[s.source] = (acc[s.source] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="p-8 max-w-7xl mx-auto">

      {/* Header */}
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-slate-900">Signals</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Tier 1–2 supply-chain impact shown by default · Tier 3–4 hidden as noise
        </p>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">

        <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1">
          <button
            onClick={() => setSourceFilter("all")}
            className={`px-3 py-1 rounded-md text-sm font-medium transition-colors
              ${sourceFilter === "all" ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
          >
            All
            <span className="ml-1.5 text-xs text-slate-400">{signals.length}</span>
          </button>
          {Object.keys(SOURCE_META).map((src) => {
            const m = SOURCE_META[src];
            const count = sourceCounts[src] ?? 0;
            if (!count) return null;
            return (
              <button
                key={src}
                onClick={() => setSourceFilter(src)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors flex items-center gap-1
                  ${sourceFilter === src ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"}`}
              >
                {m.icon} {m.label}
                <span className="text-slate-400">{count}</span>
              </button>
            );
          })}
        </div>

        <button
          onClick={() => setShowAll((v) => !v)}
          className={`ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors
            ${showAll
              ? "bg-slate-800 text-white border-slate-800"
              : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"}`}
        >
          {showAll ? "Showing all tiers" : `+${hiddenCount} low-impact hidden`}
        </button>

        <select
          value={hours}
          onChange={(e) => setHours(Number(e.target.value))}
          className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs text-slate-700 focus:outline-none"
        >
          {HOUR_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Notion-style table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100">
              <th className="pl-5 pr-2 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-[100px]">Source</th>
              <th className="px-2 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Signal</th>
              <th className="px-2 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-[160px]">Impact on TP chain</th>
              <th className="px-2 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-[90px]">Score</th>
              <th className="px-2 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-[100px]">Age</th>
              <th className="px-2 pr-5 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-[160px]">Assess</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={6} className="px-5 py-10 text-center text-slate-400 text-sm animate-pulse">Loading signals…</td></tr>
            )}
            {!isLoading && visible.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-slate-400 text-sm">
                  {showAll ? "No signals for this filter." : "No Tier 1–2 signals in this window."}
                  {!showAll && hiddenCount > 0 && (
                    <button onClick={() => setShowAll(true)} className="text-slate-600 underline ml-1">
                      Show {hiddenCount} lower-tier signals
                    </button>
                  )}
                </td>
              </tr>
            )}
            {visible.map((signal: any) => (
              <SignalRow key={signal.id} signal={signal} onScoreSaved={handleScoreSaved} />
            ))}

            {showAll && highImpact.length > 0 && lowImpact.length > 0 && (
              <tr className="bg-slate-50">
                <td colSpan={6} className="px-5 py-2 text-xs text-slate-400 font-medium">
                  ↓ {lowImpact.length} lower-tier signals (Tier 3–4 noise / proxy)
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-2.5 flex items-center gap-4 text-xs text-slate-400">
        <span>{visible.length} signals shown</span>
        {!showAll && hiddenCount > 0 && <span>· {hiddenCount} low-impact hidden</span>}
        <span className="ml-auto">auto-refreshes every 30s</span>
      </div>
    </div>
  );
}
