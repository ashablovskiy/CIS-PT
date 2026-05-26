"use client";

import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">{label}</div>
      <div className="text-3xl font-bold text-slate-900">{value}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  );
}

function ThemePill({ label, count }: { label: string; count: number }) {
  const colors: Record<string, string> = {
    commodity_price_move: "bg-amber-100 text-amber-800",
    logistics_disruption: "bg-blue-100 text-blue-800",
    supplier_capacity: "bg-purple-100 text-purple-800",
    geopolitical_disruption: "bg-red-100 text-red-800",
    natural_disaster: "bg-orange-100 text-orange-800",
    demand_surge: "bg-green-100 text-green-800",
    financial_disclosure: "bg-slate-100 text-slate-700",
    regulatory_trade: "bg-indigo-100 text-indigo-800",
    other: "bg-gray-100 text-gray-600",
    press: "bg-sky-100 text-sky-800",
  };
  const cls = colors[label] || "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${cls}`}>
      {label.replace(/_/g, " ")}
      <span className="font-bold">{count}</span>
    </span>
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

  const totalSignals = signals?.length ?? "—";
  const escalated = signals?.filter((s: any) => s.decision === "escalate").length ?? "—";
  const complete = assessments?.filter((a: any) => a.status === "complete").length ?? "—";
  const needsReview = assessments?.filter((a: any) => a.status === "needs_review").length ?? "—";

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
      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard label="Signals (24h)" value={totalSignals} sub="ingested" />
        <StatCard label="Escalated" value={escalated} sub="sent to assessment" />
        <StatCard label="Complete" value={complete} sub="assessments done" />
        <StatCard label="Needs Review" value={needsReview} sub="analyst action needed" />
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
                    <ThemePill key={k} label={k} count={v} />
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
  // Bold: **text** and *text*, inline code: `code`
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
