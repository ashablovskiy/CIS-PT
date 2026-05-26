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

// ── Impact type chip colors ───────────────────────────────────────────────────

const IMPACT_COLORS: Record<string, string> = {
  "Price movement":   "bg-orange-50 text-orange-700 border-orange-200",
  "Supply disruption":"bg-red-50 text-red-700 border-red-200",
  "Geopolitical":     "bg-violet-50 text-violet-700 border-violet-200",
  "Market news":      "bg-sky-50 text-sky-700 border-sky-200",
  "Demand shift":     "bg-emerald-50 text-emerald-700 border-emerald-200",
  "Regulatory":       "bg-gray-50 text-gray-600 border-gray-200",
};

// ── Score → color gradient ────────────────────────────────────────────────────

function scoreColor(score: number): { bg: string; text: string; dot: string } {
  if (score >= 0.8) return { bg: "bg-red-50",    text: "text-red-700",    dot: "bg-red-500" };
  if (score >= 0.6) return { bg: "bg-orange-50", text: "text-orange-700", dot: "bg-orange-500" };
  if (score >= 0.4) return { bg: "bg-amber-50",  text: "text-amber-700",  dot: "bg-amber-400" };
  return               { bg: "bg-green-50",  text: "text-green-700",  dot: "bg-green-500" };
}

function ScorePill({ score, isOverridden }: { score: number; isOverridden?: boolean }) {
  const c = scoreColor(score);
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold border
      ${c.bg} ${c.text}
      ${isOverridden ? "border-dashed border-violet-300 bg-violet-50 text-violet-700" : "border-transparent"}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${isOverridden ? "bg-violet-400" : c.dot}`} />
      {score.toFixed(2)}
      {isOverridden && <span className="opacity-60 font-normal">·edited</span>}
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

// ── Manual score cell ─────────────────────────────────────────────────────────

function AssessCell({ signal, onSaved }: {
  signal: any;
  onSaved: (id: string, score: number) => void;
}) {
  const existing = signal._analystScore ?? signal.analyst_score;
  const [open, setOpen]       = useState(false);
  const [draft, setDraft]     = useState<number>(existing ?? signal.llm_score ?? 0.5);
  const [saving, setSaving]   = useState(false);

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
        onClick={() => setOpen(true)}
        className="text-xs text-slate-300 hover:text-slate-500 transition-colors whitespace-nowrap"
      >
        {existing != null
          ? <ScorePill score={existing} isOverridden />
          : <span className="hover:underline">Set score</span>}
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-1.5 min-w-[140px]">
      <div className="flex items-center gap-2">
        <input
          type="range"
          min={0} max={1} step={0.01}
          value={draft}
          onChange={(e) => setDraft(parseFloat(e.target.value))}
          className="w-20 accent-violet-500 cursor-pointer"
        />
        <span className="text-xs font-mono text-slate-700 w-8">{draft.toFixed(2)}</span>
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

// ── Signal row ────────────────────────────────────────────────────────────────

function SignalRow({ signal, onScoreSaved }: {
  signal: any;
  onScoreSaved: (id: string, score: number) => void;
}) {
  const src    = SOURCE_META[signal.source] ?? { icon: "📌", label: signal.source, color: "bg-slate-50 text-slate-500 border-slate-200" };
  const score  = signal._analystScore ?? signal.analyst_score ?? signal.llm_score;
  const isOverridden = signal._analystScore != null || signal.analyst_score != null;
  const impactColor = IMPACT_COLORS[signal.impact_type] ?? "bg-slate-50 text-slate-500 border-slate-200";

  return (
    <tr className="group hover:bg-slate-50/70 transition-colors border-b border-slate-100 last:border-0">

      {/* Source */}
      <td className="pl-5 pr-3 py-3 w-[100px]">
        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-medium border ${src.color}`}>
          <span>{src.icon}</span>
          {src.label}
        </span>
      </td>

      {/* Description + price move */}
      <td className="px-3 py-3">
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

      {/* Impact type */}
      <td className="px-3 py-3 w-[140px]">
        <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border ${impactColor}`}>
          {signal.impact_type}
        </span>
      </td>

      {/* Score */}
      <td className="px-3 py-3 w-[80px]">
        {score != null
          ? <ScorePill score={score} isOverridden={isOverridden} />
          : <span className="text-slate-300 text-xs">—</span>}
      </td>

      {/* Age */}
      <td className="px-3 py-3 w-[100px]">
        <span className="text-xs text-slate-400 whitespace-nowrap">
          {signal.ingested_at
            ? formatDistanceToNow(new Date(signal.ingested_at), { addSuffix: true })
            : "—"}
        </span>
      </td>

      {/* Manual assess */}
      <td className="px-3 pr-5 py-3 w-[160px]">
        <div className="opacity-0 group-hover:opacity-100 transition-opacity">
          <AssessCell signal={signal} onSaved={onScoreSaved} />
        </div>
      </td>
    </tr>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const HOUR_OPTIONS = [
  { label: "Last 24h",  value: 24 },
  { label: "Last 48h",  value: 48 },
  { label: "Last 7d",   value: 168 },
  { label: "Last 30d",  value: 720 },
];

export default function SignalsPage() {
  const [hours,      setHours]      = useState(48);
  const [showAll,    setShowAll]    = useState(false);
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  // Local analyst score overrides (session-only layer on top of DB values)
  const [overrides,  setOverrides]  = useState<Record<string, number>>({});

  const url = `${API}/api/signals?hours=${hours}&limit=200`;
  const { data: rawSignals, isLoading } = useSWR(url, fetcher, { refreshInterval: 30_000 });

  // Merge in local overrides
  const signals: any[] = (rawSignals ?? []).map((s: any) => ({
    ...s,
    _analystScore: overrides[s.id] ?? null,
  }));

  // Filter pipeline
  const afterSource = sourceFilter === "all"
    ? signals
    : signals.filter((s) => s.source === sourceFilter);

  const highImpact  = afterSource.filter((s) => {
    const score = s._analystScore ?? s.analyst_score ?? s.llm_score ?? 0;
    return score >= 0.5;
  });
  const lowImpact   = afterSource.filter((s) => {
    const score = s._analystScore ?? s.analyst_score ?? s.llm_score ?? 0;
    return score < 0.5;
  });

  const visible = showAll ? afterSource : highImpact;
  const hiddenCount = lowImpact.length;

  const handleScoreSaved = useCallback((id: string, score: number) => {
    setOverrides((prev) => ({ ...prev, [id]: score }));
  }, []);

  // Source counts for filter tabs
  const sourceCounts = (signals).reduce((acc: Record<string, number>, s: any) => {
    acc[s.source] = (acc[s.source] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="p-8 max-w-7xl mx-auto">

      {/* Header */}
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-slate-900">Signals</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Real-time ingestion from 6 data sources
        </p>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">

        {/* Source filter tabs */}
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

        {/* Low-impact toggle */}
        <button
          onClick={() => setShowAll((v) => !v)}
          className={`ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors
            ${showAll
              ? "bg-slate-800 text-white border-slate-800"
              : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"}`}
        >
          {showAll ? "Showing all" : `+${hiddenCount} low-impact hidden`}
        </button>

        {/* Time window */}
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
              <th className="pl-5 pr-3 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-[100px]">
                Source
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Signal
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-[140px]">
                Impact type
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-[80px]">
                Score
              </th>
              <th className="px-3 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-[100px]">
                Age
              </th>
              <th className="px-3 pr-5 py-2.5 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider w-[160px]">
                Assess
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-slate-400 text-sm animate-pulse">
                  Loading signals…
                </td>
              </tr>
            )}
            {!isLoading && visible.length === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-slate-400 text-sm">
                  {showAll ? "No signals for this filter." : "No impactful signals (score ≥ 0.5). "}
                  {!showAll && hiddenCount > 0 && (
                    <button onClick={() => setShowAll(true)} className="text-slate-600 underline ml-1">
                      Show {hiddenCount} lower-score signals
                    </button>
                  )}
                </td>
              </tr>
            )}
            {visible.map((signal: any) => (
              <SignalRow
                key={signal.id}
                signal={signal}
                onScoreSaved={handleScoreSaved}
              />
            ))}

            {/* Low-impact divider row when showing all */}
            {showAll && highImpact.length > 0 && lowImpact.length > 0 && (
              <tr className="bg-slate-50">
                <td colSpan={6} className="px-5 py-2 text-xs text-slate-400 font-medium">
                  ↓ {lowImpact.length} lower-impact signals (score &lt; 0.5)
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="mt-2.5 flex items-center gap-4 text-xs text-slate-400">
        <span>{visible.length} signals shown</span>
        {!showAll && hiddenCount > 0 && (
          <span>· {hiddenCount} low-impact hidden</span>
        )}
        <span className="ml-auto">auto-refreshes every 30s</span>
      </div>
    </div>
  );
}
