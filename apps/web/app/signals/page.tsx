"use client";

import useSWR from "swr";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const DECISION_COLORS: Record<string, string> = {
  escalate: "bg-red-100 text-red-700 border-red-200",
  classify: "bg-blue-100 text-blue-700 border-blue-200",
  discard: "bg-slate-100 text-slate-500 border-slate-200",
};

const SOURCE_ICONS: Record<string, string> = {
  prices: "💹",
  gdelt: "🌍",
  logistics: "🚢",
  press: "📰",
  demand: "📈",
  sec: "📄",
};

export default function SignalsPage() {
  const [hours, setHours] = useState(48);
  const [filter, setFilter] = useState<string>("all");

  const url = `/api/signals?hours=${hours}&limit=100${filter !== "all" ? `&decision=${filter}` : ""}`;
  const { data: signals, isLoading } = useSWR(url, fetcher, { refreshInterval: 30_000 });

  const counts = (signals ?? []).reduce((acc: Record<string, number>, s: any) => {
    const d = s.decision || "none";
    acc[d] = (acc[d] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Signals Feed</h1>
        <p className="text-slate-500 text-sm mt-1">Real-time ingestion from 6 data sources</p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        <div className="flex gap-2">
          {["all", "escalate", "classify", "discard"].map((d) => (
            <button
              key={d}
              onClick={() => setFilter(d)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                filter === d
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
              }`}
            >
              {d === "all" ? "All" : d.charAt(0).toUpperCase() + d.slice(1)}
              {counts[d] !== undefined && (
                <span className="ml-1 text-xs opacity-60">{counts[d]}</span>
              )}
            </button>
          ))}
        </div>
        <select
          value={hours}
          onChange={(e) => setHours(Number(e.target.value))}
          className="ml-auto px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm text-slate-700"
        >
          <option value={24}>Last 24 hours</option>
          <option value={48}>Last 48 hours</option>
          <option value={168}>Last 7 days</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide w-8">
                Src
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Title / Summary
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide w-24">
                Score
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide w-28">
                Decision
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide w-28">
                Age
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400 text-sm animate-pulse">
                  Loading signals…
                </td>
              </tr>
            )}
            {!isLoading && (!signals || signals.length === 0) && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-400 text-sm">
                  No signals found for this filter.
                </td>
              </tr>
            )}
            {(signals ?? []).map((s: any) => (
              <tr key={s.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3 text-center">
                  <span title={s.source} className="text-base">
                    {SOURCE_ICONS[s.source] || "📌"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium text-slate-800 truncate max-w-xs">
                    {s.title || <span className="text-slate-400 italic">No title</span>}
                  </div>
                  {s.summary && (
                    <div className="text-xs text-slate-400 mt-0.5 truncate max-w-md">
                      {s.summary}
                    </div>
                  )}
                  {s.url && (
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-500 hover:underline"
                    >
                      ↗ source
                    </a>
                  )}
                </td>
                <td className="px-4 py-3">
                  {s.llm_score != null ? (
                    <div className="flex items-center gap-1">
                      <div
                        className="h-1.5 rounded-full bg-slate-200 w-16 overflow-hidden"
                        title={`LLM: ${s.llm_score.toFixed(2)}`}
                      >
                        <div
                          className="h-full rounded-full bg-blue-500"
                          style={{ width: `${s.llm_score * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-500">{s.llm_score.toFixed(2)}</span>
                    </div>
                  ) : (
                    <span className="text-slate-300 text-xs">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {s.decision ? (
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium border ${
                        DECISION_COLORS[s.decision] || "bg-gray-100 text-gray-600 border-gray-200"
                      }`}
                    >
                      {s.decision}
                    </span>
                  ) : (
                    <span className="text-slate-300 text-xs">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-slate-400">
                  {s.ingested_at
                    ? formatDistanceToNow(new Date(s.ingested_at), { addSuffix: true })
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 text-xs text-slate-400">
        {signals?.length ?? 0} signals shown · auto-refreshes every 30s
      </div>
    </div>
  );
}
