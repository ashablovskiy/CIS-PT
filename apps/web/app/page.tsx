"use client";

import useSWR from "swr";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const SOURCE_COLORS: Record<string, string> = {
  gdelt:     "#6366f1",
  prices:    "#f59e0b",
  logistics: "#3b82f6",
  press:     "#10b981",
  demand:    "#8b5cf6",
  sec:       "#ef4444",
  unknown:   "#94a3b8",
};

function StatCard({
  label, value, sub, href,
}: {
  label: string; value: string | number; sub?: string; href?: string;
}) {
  const inner = (
    <div className="bg-white rounded-xl border border-slate-200 p-5 hover:border-slate-300 transition-colors">
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">{label}</div>
      <div className="text-3xl font-bold text-slate-900">{value}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  );
  return href ? <Link href={href}>{inner}</Link> : inner;
}

function ThemePill({ label, count }: { label: string; count: number }) {
  const colors: Record<string, string> = {
    commodity_price_move:    "bg-amber-100 text-amber-800",
    logistics_disruption:    "bg-blue-100 text-blue-800",
    supplier_capacity:       "bg-purple-100 text-purple-800",
    geopolitical_disruption: "bg-red-100 text-red-800",
    natural_disaster:        "bg-orange-100 text-orange-800",
    demand_surge:            "bg-green-100 text-green-800",
    financial_disclosure:    "bg-slate-100 text-slate-700",
    regulatory_trade:        "bg-indigo-100 text-indigo-800",
    other:                   "bg-gray-100 text-gray-600",
    press:                   "bg-sky-100 text-sky-800",
  };
  const cls = colors[label] || "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${cls}`}>
      {label.replace(/_/g, " ")}
      <span className="font-bold">{count}</span>
    </span>
  );
}

/** Minimal SVG stacked bar chart — no external dependency. */
function SignalVolumeChart({ stats }: { stats: any }) {
  if (!stats?.time_series?.length) {
    return (
      <div className="h-28 flex items-center justify-center text-xs text-slate-300">
        No signal data in window
      </div>
    );
  }

  const series: any[] = stats.time_series;
  const sources: string[] = stats.sources || [];
  const W = 560, H = 100, BAR_GAP = 2;
  const barW = Math.max(4, Math.floor((W - BAR_GAP * series.length) / series.length));

  const maxVal = Math.max(1, ...series.map((d: any) =>
    sources.reduce((s: number, src: string) => s + (d[src] || 0), 0)
  ));

  return (
    <div className="overflow-x-auto">
      <svg width={W} height={H + 24} className="block">
        {series.map((d: any, i: number) => {
          let yOffset = 0;
          const x = i * (barW + BAR_GAP);
          return (
            <g key={i}>
              {sources.map((src: string) => {
                const val = d[src] || 0;
                const h = Math.round((val / maxVal) * H);
                const y = H - yOffset - h;
                yOffset += h;
                if (h === 0) return null;
                return (
                  <rect
                    key={src}
                    x={x} y={y} width={barW} height={h}
                    fill={SOURCE_COLORS[src] || SOURCE_COLORS.unknown}
                    opacity={0.85}
                  >
                    <title>{src}: {val}</title>
                  </rect>
                );
              })}
              {i % Math.max(1, Math.floor(series.length / 7)) === 0 && (
                <text
                  x={x + barW / 2} y={H + 16}
                  fontSize="8" fill="#94a3b8" textAnchor="middle"
                >
                  {String(d.time ?? "").slice(5)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="flex flex-wrap gap-3 mt-2">
        {sources.map((src: string) => (
          <div key={src} className="flex items-center gap-1">
            <span
              className="w-2.5 h-2.5 rounded-sm inline-block"
              style={{ background: SOURCE_COLORS[src] || SOURCE_COLORS.unknown }}
            />
            <span className="text-[11px] text-slate-500">{src}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data: brief, error: briefErr, isLoading: briefLoading } =
    useSWR("/api/briefs/latest", fetcher, { refreshInterval: 300_000 });

  const { data: signals } = useSWR("/api/signals?hours=24&limit=200", fetcher, {
    refreshInterval: 60_000,
  });

  const { data: assessments } = useSWR("/api/assessments?limit=100", fetcher, {
    refreshInterval: 60_000,
  });

  const { data: stats } = useSWR("/api/signals/stats?hours=168", fetcher, {
    refreshInterval: 300_000,
  });

  const { data: feedbackStats } = useSWR("/api/feedback/stats", fetcher, {
    refreshInterval: 300_000,
  });

  const totalSignals = signals?.length ?? "—";
  const escalated    = signals?.filter((s: any) => s.decision === "escalate").length ?? "—";
  const complete     = assessments?.filter((a: any) => a.status === "complete").length ?? "—";
  const needsReview  = assessments?.filter((a: any) => a.status === "needs_review").length ?? "—";

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Daily Brief</h1>
        <p className="text-slate-500 text-sm mt-1">
          Power transformer procurement intelligence — last 24 hours
        </p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard label="Signals (24h)" value={totalSignals} sub="ingested" href="/signals" />
        <StatCard label="Escalated"     value={escalated}    sub="sent to assessment" href="/signals" />
        <StatCard label="Complete"      value={complete}     sub="assessments done" href="/assessments" />
        <StatCard label="Needs Review"  value={needsReview}  sub="analyst action needed" href="/assessments" />
      </div>

      {/* Signal volume chart + optimizer health */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="col-span-2 bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm font-semibold text-slate-700">Signal Volume — 7 days</div>
            {stats && (
              <span className="text-xs text-slate-400">{stats.total} total</span>
            )}
          </div>
          <SignalVolumeChart stats={stats} />
        </div>

        <div className="bg-white rounded-xl border border-slate-200 p-5 flex flex-col">
          <div className="text-sm font-semibold text-slate-700 mb-4">Optimizer Health</div>
          {feedbackStats ? (
            <div className="space-y-3 flex-1">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Accepted</span>
                <span className="text-sm font-bold text-emerald-600">{feedbackStats.accepted}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Edited</span>
                <span className="text-sm font-bold text-amber-600">{feedbackStats.edited}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Rejected</span>
                <span className="text-sm font-bold text-red-500">{feedbackStats.rejected}</span>
              </div>
              <div className="border-t border-slate-100 pt-3 flex items-center justify-between">
                <span className="text-xs text-slate-500">Training examples</span>
                <span className="text-sm font-bold text-slate-800">{feedbackStats.training_examples}</span>
              </div>
              <div className="pt-2">
                {feedbackStats.optimizer_ready ? (
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold
                    text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-1 rounded-full">
                    ✓ Ready to optimize
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[11px] text-slate-500
                    bg-slate-50 border border-slate-200 px-2 py-1 rounded-full">
                    {feedbackStats.training_examples}/5 examples needed
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-300 animate-pulse">Loading…</div>
          )}
        </div>
      </div>

      {/* Brief content */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div className="font-semibold text-slate-900">Intelligence Brief</div>
          {brief && (
            <div className="flex items-center gap-4">
              {brief.themes && Object.keys(brief.themes).length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {Object.entries(brief.themes as Record<string, number>).map(([k, v]) => (
                    <ThemePill key={k} label={k} count={v as number} />
                  ))}
                </div>
              )}
              {brief.created_at && (
                <span className="text-xs text-slate-400 shrink-0">
                  {formatDistanceToNow(new Date(brief.created_at), { addSuffix: true })}
                </span>
              )}
            </div>
          )}
        </div>

        <div className="px-6 py-6">
          {briefLoading && (
            <div className="text-slate-400 text-sm animate-pulse">Loading brief…</div>
          )}
          {briefErr && (
            <div className="text-slate-400 text-sm">
              No brief available yet.{" "}
              <span className="text-slate-300">
                Run <code className="bg-slate-100 px-1 rounded">scripts/run_scout.py</code> to
                generate one.
              </span>
            </div>
          )}
          {brief && (
            <div className="prose prose-slate prose-sm max-w-none">
              <BriefMarkdown markdown={brief.body_markdown} />
            </div>
          )}
        </div>
      </div>

      {/* Flagged signals */}
      {brief?.flagged_for_assessment?.length > 0 && (
        <div className="mt-6 bg-amber-50 border border-amber-200 rounded-xl px-6 py-4">
          <div className="text-sm font-semibold text-amber-800 mb-2">
            ⚠ Flagged for Assessment ({brief.flagged_for_assessment.length})
          </div>
          <div className="flex flex-wrap gap-2">
            {brief.flagged_for_assessment.map((id: string) => (
              <a
                key={id}
                href={`/signals?id=${id}`}
                className="text-xs font-mono text-amber-700 hover:underline"
              >
                {id.slice(0, 8)}…
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/** Minimal markdown renderer — headings, bullets, bold, code */
function BriefMarkdown({ markdown }: { markdown: string }) {
  const lines = markdown.split("\n");
  const elements: React.ReactNode[] = [];

  lines.forEach((line, i) => {
    if (line.startsWith("# ")) {
      elements.push(
        <h1 key={i} className="text-xl font-bold text-slate-900 mt-0 mb-3">
          {line.slice(2)}
        </h1>
      );
    } else if (line.startsWith("## ")) {
      elements.push(
        <h2 key={i} className="text-base font-semibold text-slate-800 mt-5 mb-2 border-b border-slate-100 pb-1">
          {line.slice(3)}
        </h2>
      );
    } else if (line.startsWith("### ")) {
      elements.push(
        <h3 key={i} className="text-sm font-semibold text-slate-700 mt-4 mb-1">
          {line.slice(4)}
        </h3>
      );
    } else if (line.startsWith("- ")) {
      elements.push(
        <li key={i} className="text-sm text-slate-700 ml-4 list-disc">
          <InlineMarkdown text={line.slice(2)} />
        </li>
      );
    } else if (line.startsWith("---")) {
      elements.push(<hr key={i} className="my-4 border-slate-100" />);
    } else if (line.trim()) {
      elements.push(
        <p key={i} className="text-sm text-slate-700 mb-2">
          <InlineMarkdown text={line} />
        </p>
      );
    }
  });

  return <>{elements}</>;
}

function InlineMarkdown({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={i}>{part.slice(2, -2)}</strong>;
        }
        if (part.startsWith("*") && part.endsWith("*")) {
          return <em key={i}>{part.slice(1, -1)}</em>;
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code key={i} className="bg-slate-100 px-1 rounded text-xs font-mono">
              {part.slice(1, -1)}
            </code>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}
