"use client";

import useSWR from "swr";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const STATUS_STYLES: Record<string, string> = {
  complete: "bg-emerald-100 text-emerald-700 border-emerald-200",
  needs_review: "bg-amber-100 text-amber-700 border-amber-200",
  error: "bg-red-100 text-red-700 border-red-200",
  pending: "bg-slate-100 text-slate-600 border-slate-200",
};

const DIM_COLORS: Record<string, string> = {
  increase: "text-red-600",
  decrease: "text-emerald-600",
  neutral: "text-slate-400",
  disrupted: "text-orange-600",
  restricted: "text-purple-600",
};

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
      <div className="px-5 py-3 border-b border-slate-100 bg-slate-50">
        <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  );
}

function ConfidenceRing({ value }: { value: number | null }) {
  if (value == null) return <span className="text-slate-300">—</span>;
  const pct = Math.round(value * 100);
  const color = value >= 0.7 ? "#10b981" : value >= 0.45 ? "#f59e0b" : "#ef4444";
  const r = 22, circ = 2 * Math.PI * r;
  const dash = (value * circ).toFixed(1);
  return (
    <div className="flex flex-col items-center">
      <svg width="60" height="60" className="-rotate-90">
        <circle cx="30" cy="30" r={r} fill="none" stroke="#e2e8f0" strokeWidth="5" />
        <circle cx="30" cy="30" r={r} fill="none" stroke={color} strokeWidth="5"
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round" />
      </svg>
      <span className="text-lg font-bold -mt-10" style={{ color }}>{pct}%</span>
      <span className="text-xs text-slate-400 mt-6">confidence</span>
    </div>
  );
}

/**
 * Magnitudes can arrive as either a scalar number or a
 * {low, mid, high} confidence interval (from the XGBoost price model).
 */
function magnitudeText(mag: unknown): { headline: string; range: string | null } {
  if (mag == null) return { headline: "—", range: null };
  if (typeof mag === "number") return { headline: `${mag.toFixed(1)}%`, range: null };
  if (typeof mag === "object") {
    const m = mag as { low?: number; mid?: number; high?: number };
    if (typeof m.mid === "number") {
      const range = (typeof m.low === "number" && typeof m.high === "number")
        ? `${m.low.toFixed(1)}–${m.high.toFixed(1)}%`
        : null;
      return { headline: `${m.mid.toFixed(1)}%`, range };
    }
  }
  return { headline: String(mag), range: null };
}

function ImpactRow({ dimension, data }: { dimension: string; data: any }) {
  if (!data || dimension.startsWith("_")) return null;
  const { direction, magnitude_pct, confidence, detail,
          ml_magnitude_pct, ml_direction, ml_confidence, ml_used } = data;
  const arrow = direction === "increase" ? "▲" : direction === "decrease" ? "▼" : "—";
  const colClass = DIM_COLORS[direction] || "text-slate-500";
  const mag   = magnitudeText(magnitude_pct);
  const mlMag = magnitudeText(ml_magnitude_pct);
  return (
    <div className="py-3 border-b border-slate-100 last:border-0">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="w-28 text-xs font-semibold text-slate-500 uppercase tracking-wide">
          {dimension.replace(/_/g, " ")}
        </div>
        <span className={`text-sm font-bold w-24 ${colClass}`}>
          {arrow} {direction === "neutral" ? "neutral" : mag.headline}
        </span>
        {confidence != null && (
          <div className="flex items-center gap-1.5">
            <div className="h-1.5 w-16 bg-slate-100 rounded-full overflow-hidden">
              <div className="h-full bg-blue-400 rounded-full"
                style={{ width: `${Math.round(confidence * 100)}%` }} />
            </div>
            <span className="text-xs text-slate-400">{Math.round(confidence * 100)}%</span>
          </div>
        )}
        {/* ML enrichment badge */}
        {ml_used && ml_magnitude_pct != null && (
          <span className="ml-auto text-[11px] bg-violet-50 border border-violet-200 text-violet-700
            px-2 py-0.5 rounded-full font-medium">
            ML: {ml_direction === "increase" ? "▲" : ml_direction === "decrease" ? "▼" : "—"}{" "}
            {mlMag.headline} · {Math.round((ml_confidence ?? 0) * 100)}% conf
          </span>
        )}
      </div>
      {(mag.range || mlMag.range) && (
        <div className="text-[10px] text-slate-400 mt-1 pl-[7.5rem]">
          {mag.range && <>range {mag.range}</>}
          {mag.range && mlMag.range && " · "}
          {mlMag.range && <>ML range {mlMag.range}</>}
        </div>
      )}
      {detail && (
        <p className="text-xs text-slate-500 mt-1 leading-relaxed pl-[7.5rem]">{detail}</p>
      )}
    </div>
  );
}

function ReasoningStep({ step, index }: { step: any; index: number }) {
  const source = typeof step.grounded_in === "object"
    ? step.grounded_in?.source ?? JSON.stringify(step.grounded_in)
    : String(step.grounded_in ?? "");

  return (
    <div className="flex gap-4 group">
      {/* Step number + connector */}
      <div className="flex flex-col items-center">
        <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center
          text-white text-xs font-bold shrink-0 shadow-sm">
          {step.step ?? index + 1}
        </div>
        <div className="w-px flex-1 bg-slate-200 mt-1 mb-1 group-last:hidden" />
      </div>
      {/* Content */}
      <div className="pb-5 flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-800 leading-snug">{step.claim}</p>
        {step.inference && (
          <p className="text-sm text-slate-500 mt-1">
            <span className="text-blue-400 font-medium">∴ </span>{step.inference}
          </p>
        )}
        {source && (
          <div className="mt-2 flex items-start gap-1.5">
            <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mt-0.5">
              Source
            </span>
            <span className="text-xs text-slate-500 bg-slate-50 border border-slate-200
              rounded px-2 py-0.5 font-mono leading-relaxed">
              {source}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// Static export requires this; assessment IDs are only known at runtime so we
// return [] and rely on client-side navigation (direct URL access will 404 on GH Pages).
export function generateStaticParams() {
  return [];
}

export default function AssessmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: a, isLoading, error } = useSWR(`/api/assessments/${id}`, fetcher);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackAction, setFeedbackAction] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submitFeedback(action: string) {
    setSubmitting(true);
    setFeedbackAction(action);
    try {
      await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assessment_id: id, user_action: action }),
      });
      setFeedbackSent(true);
    } finally {
      setSubmitting(false);
    }
  }

  if (isLoading) {
    return <div className="p-10 text-slate-400 text-sm animate-pulse">Loading assessment…</div>;
  }
  if (error || !a) {
    return (
      <div className="p-10 text-slate-500 text-sm">
        Assessment not found.{" "}
        <Link href="/assessments" className="text-blue-500 hover:underline">← Back</Link>
      </div>
    );
  }

  const entities = a.affected_entities || {};
  const impact   = a.impact || {};
  const clauses: any[] = Array.isArray(a.affected_clauses) ? a.affected_clauses : [];
  const chain:   any[] = Array.isArray(a.reasoning_chain)  ? a.reasoning_chain  : [];
  const hasEntities = Object.values(entities).some((v: any) => Array.isArray(v) && v.length > 0);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-5">

        {/* Header */}
        <div>
          <Link href="/assessments" className="text-sm text-slate-400 hover:text-slate-600 mb-4 inline-block">
            ← Assessments
          </Link>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap mb-2">
                <span className={`text-xs px-2 py-0.5 rounded-full font-semibold border ${STATUS_STYLES[a.status] || STATUS_STYLES.pending}`}>
                  {a.status?.replace(/_/g, " ")}
                </span>
                <span className="text-xs text-slate-400 font-mono">{a.id?.slice(0, 8)}…</span>
                {a.created_at && (
                  <span className="text-xs text-slate-400">
                    {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                  </span>
                )}
                {a.agent_version && (
                  <span className="text-xs text-slate-300">· {a.agent_version}</span>
                )}
              </div>
              <h1 className="text-xl font-bold text-slate-900 leading-tight">
                {a.signal?.title || "Impact Assessment"}
              </h1>
            </div>
            <ConfidenceRing value={a.confidence} />
          </div>
        </div>

        {/* Signal source banner */}
        {a.signal && (
          <div className="bg-blue-50 border border-blue-100 rounded-xl px-5 py-3 flex items-start gap-3">
            <span className="text-blue-400 mt-0.5">📡</span>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-blue-800 truncate">
                {a.signal.title || a.signal.source}
              </div>
              <div className="text-xs text-blue-500 mt-0.5 flex gap-2 flex-wrap">
                <span className="uppercase font-semibold">{a.signal.source}</span>
                {a.signal.occurred_at && (
                  <span>· {formatDistanceToNow(new Date(a.signal.occurred_at), { addSuffix: true })}</span>
                )}
              </div>
            </div>
            {a.signal.url && (
              <a href={a.signal.url} target="_blank" rel="noopener noreferrer"
                className="text-xs text-blue-400 hover:text-blue-600 shrink-0">↗ Source</a>
            )}
          </div>
        )}

        {/* Summary */}
        <Card title="Executive Summary">
          <p className="text-sm text-slate-700 leading-relaxed">{a.summary}</p>
        </Card>

        {/* Entities */}
        {hasEntities && (
          <Card title="Affected Entities">
            <div className="space-y-3">
              {Object.entries(entities).map(([type, items]) => {
                const arr = items as string[];
                if (!arr.length) return null;
                const iconMap: Record<string, string> = {
                  suppliers: "🏭", plants: "⚙️", ports: "🚢", commodities: "📦",
                };
                return (
                  <div key={type} className="flex gap-3 items-start">
                    <div className="w-24 text-xs font-semibold text-slate-500 capitalize
                      flex items-center gap-1 shrink-0 pt-0.5">
                      <span>{iconMap[type] ?? "•"}</span> {type}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {arr.map((item) => (
                        <span key={item}
                          className="px-2.5 py-0.5 bg-slate-100 hover:bg-slate-200
                            rounded-full text-xs text-slate-700 transition-colors">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        {/* Impact by dimension */}
        {Object.keys(impact).length > 0 && (
          <Card title="Impact by Dimension">
            {Object.entries(impact).map(([dim, data]) => (
              <ImpactRow key={dim} dimension={dim} data={data} />
            ))}
          </Card>
        )}

        {/* Contract clauses */}
        {clauses.length > 0 && (
          <Card title="Contract Clause Analysis">
            <div className="space-y-2.5">
              {clauses.map((c, i) => (
                <div key={i}
                  className={`rounded-xl border px-4 py-3 ${
                    c.triggered
                      ? "bg-red-50 border-red-200"
                      : "bg-slate-50 border-slate-200"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    {c.triggered ? (
                      <span className="text-[11px] font-bold text-red-600 bg-red-100
                        px-2 py-0.5 rounded-full uppercase tracking-wide">⚠ Triggered</span>
                    ) : (
                      <span className="text-[11px] font-semibold text-slate-400
                        bg-slate-100 px-2 py-0.5 rounded-full uppercase tracking-wide">
                        Not triggered
                      </span>
                    )}
                    <span className="text-xs font-semibold text-slate-700 capitalize">
                      {c.clause_type?.replace(/_/g, " ")}
                    </span>
                    {c.contract_id && (
                      <span className="text-xs text-slate-400 font-mono ml-auto">{c.contract_id}</span>
                    )}
                  </div>
                  {c.detail && (
                    <p className="text-xs text-slate-600 leading-relaxed">{c.detail}</p>
                  )}
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Reasoning chain */}
        {chain.length > 0 && (
          <Card title={`Reasoning Chain (${chain.length} steps)`}>
            <div className="pt-1">
              {chain.map((step: any, i: number) => (
                <ReasoningStep key={i} step={step} index={i} />
              ))}
            </div>
          </Card>
        )}

        {/* Feedback */}
        <Card title="Analyst Feedback">
          {feedbackSent ? (
            <div className="flex items-center gap-2 text-sm text-emerald-700 font-medium">
              <span>✓</span>
              <span>
                Feedback recorded as <strong>{feedbackAction}</strong>.
                {feedbackAction !== "reject" && " A training example has been queued for the optimizer."}
              </span>
            </div>
          ) : (
            <div>
              <p className="text-xs text-slate-500 mb-4">
                Your decision trains the DSPy optimization loop. Accept/Edit responses
                are stored as training examples for the weekly MIPROv2 run.
              </p>
              <div className="flex gap-2 flex-wrap">
                <button onClick={() => submitFeedback("accept")} disabled={submitting}
                  className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold
                    hover:bg-emerald-700 transition-colors disabled:opacity-50">
                  ✓ Accept
                </button>
                <button onClick={() => submitFeedback("edit")} disabled={submitting}
                  className="px-4 py-2 rounded-lg bg-slate-700 text-white text-sm font-semibold
                    hover:bg-slate-800 transition-colors disabled:opacity-50">
                  ✎ Needs Edit
                </button>
                <button onClick={() => submitFeedback("reject")} disabled={submitting}
                  className="px-4 py-2 rounded-lg bg-red-100 text-red-700 text-sm font-semibold
                    hover:bg-red-200 transition-colors disabled:opacity-50">
                  ✕ Reject
                </button>
              </div>
            </div>
          )}
        </Card>

      </div>
    </div>
  );
}
