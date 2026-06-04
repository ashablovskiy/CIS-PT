"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const STATUS_STYLES: Record<string, string> = {
  complete: "bg-green-100 text-green-700 border-green-200",
  needs_review: "bg-amber-100 text-amber-700 border-amber-200",
  error: "bg-red-100 text-red-700 border-red-200",
  pending: "bg-slate-100 text-slate-600 border-slate-200",
};

const EVENT_CLASS_COLORS: Record<string, string> = {
  commodity_price_move: "text-amber-600",
  logistics_disruption: "text-blue-600",
  supplier_capacity: "text-purple-600",
  geopolitical_disruption: "text-red-600",
  natural_disaster: "text-orange-600",
  demand_surge: "text-green-600",
  financial_disclosure: "text-slate-600",
  regulatory_trade: "text-indigo-600",
  other: "text-gray-500",
};

function ConfidenceBadge({ value }: { value: number | null }) {
  if (value == null) return <span className="text-slate-300 text-xs">—</span>;
  const pct = Math.round(value * 100);
  const color = value >= 0.7 ? "text-green-600" : value >= 0.45 ? "text-amber-600" : "text-red-500";
  return <span className={`text-sm font-semibold ${color}`}>{pct}%</span>;
}

/**
 * Magnitudes can arrive as either a scalar number or a
 * {low, mid, high} confidence interval (from the XGBoost price model).
 * Returns a tuple: [headline text, optional range hint].
 */
function formatMagnitude(mag: unknown): [string, string | null] {
  if (mag == null) return ["?", null];
  if (typeof mag === "number") return [mag.toFixed(1), null];
  if (typeof mag === "object") {
    const m = mag as { low?: number; mid?: number; high?: number };
    if (typeof m.mid === "number") {
      const headline = m.mid.toFixed(1);
      const range = (typeof m.low === "number" && typeof m.high === "number")
        ? `${m.low.toFixed(1)}–${m.high.toFixed(1)}`
        : null;
      return [headline, range];
    }
  }
  return [String(mag), null];
}

export default function AssessmentsPage() {
  const [filter, setFilter] = useState("all");
  const url = `${API}/api/assessments?limit=50${filter !== "all" ? `&status=${filter}` : ""}`;
  const { data: assessments, isLoading } = useSWR(url, fetcher, { refreshInterval: 30_000 });

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Assessments</h1>
        <p className="text-slate-500 text-sm mt-1">7-node LangGraph pipeline outputs</p>
      </div>

      {/* Status filter */}
      <div className="flex gap-2 mb-6">
        {["all", "complete", "needs_review", "error"].map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              filter === s
                ? "bg-slate-900 text-white border-slate-900"
                : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
            }`}
          >
            {s === "all" ? "All" : s.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Cards */}
      <div className="space-y-4">
        {isLoading && (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-400 text-sm animate-pulse">
            Loading assessments…
          </div>
        )}
        {!isLoading && (!assessments || assessments.length === 0) && (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-400 text-sm">
            No assessments found.
          </div>
        )}
        {(assessments ?? []).map((a: any) => (
          <AssessmentCard key={a.id} assessment={a} />
        ))}
      </div>
    </div>
  );
}

function AssessmentCard({ assessment: a }: { assessment: any }) {
  const entities = a.affected_entities || {};
  const suppliers: string[] = entities.suppliers || [];
  const commodities: string[] = entities.commodities || [];
  const impact = a.impact || {};

  const priceDir = impact.price?.direction;
  const [priceMagText, priceMagRange] = formatMagnitude(impact.price?.magnitude_pct);

  return (
    <Link href={`/assessments/detail?id=${a.id}`}>
      <div className="bg-white rounded-xl border border-slate-200 p-5 hover:border-slate-300 hover:shadow-sm transition-all cursor-pointer">
        <div className="flex items-start justify-between gap-4">
          {/* Left: summary */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span
                className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium border ${
                  STATUS_STYLES[a.status] || STATUS_STYLES.pending
                }`}
              >
                {a.status?.replace(/_/g, " ")}
              </span>
              {a.signal?.source && (
                <span className="text-xs text-slate-400">{a.signal.source}</span>
              )}
              {a.created_at && (
                <span className="text-xs text-slate-400">
                  {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                </span>
              )}
            </div>
            <p className="text-sm text-slate-700 line-clamp-2">{a.summary}</p>
            <div className="flex flex-wrap gap-1 mt-2">
              {suppliers.slice(0, 3).map((s: string) => (
                <span key={s} className="px-1.5 py-0.5 bg-purple-50 text-purple-700 rounded text-xs">
                  {s}
                </span>
              ))}
              {commodities.slice(0, 3).map((c: string) => (
                <span key={c} className="px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded text-xs">
                  {c}
                </span>
              ))}
            </div>
          </div>

          {/* Right: metrics */}
          <div className="shrink-0 text-right space-y-2">
            <div>
              <div className="text-xs text-slate-400 mb-0.5">Confidence</div>
              <ConfidenceBadge value={a.confidence} />
            </div>
            {priceDir && (
              <div>
                <div className="text-xs text-slate-400 mb-0.5">Price</div>
                <span className={`text-sm font-medium ${priceDir === "increase" ? "text-red-600" : "text-green-600"}`}>
                  {priceDir === "increase" ? "▲" : "▼"} {priceMagText}%
                </span>
                {priceMagRange && (
                  <div className="text-[10px] text-slate-400 mt-0.5">range {priceMagRange}%</div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Clauses row */}
        {a.affected_clauses?.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap gap-2">
            {a.affected_clauses.slice(0, 4).map((c: any, i: number) => (
              <span
                key={i}
                className={`text-xs px-2 py-0.5 rounded border ${
                  c.triggered
                    ? "bg-red-50 border-red-200 text-red-700"
                    : "bg-slate-50 border-slate-200 text-slate-600"
                }`}
              >
                {c.triggered ? "⚠ " : ""}
                {c.clause_type?.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
      </div>
    </Link>
  );
}
