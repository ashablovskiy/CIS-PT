"use client";

import useSWR from "swr";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { formatDistanceToNow } from "date-fns";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const STATUS_STYLES: Record<string, string> = {
  complete: "bg-green-100 text-green-700",
  needs_review: "bg-amber-100 text-amber-700",
  error: "bg-red-100 text-red-700",
  pending: "bg-slate-100 text-slate-600",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 bg-slate-50">
        <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  );
}

function ImpactRow({ dimension, data }: { dimension: string; data: any }) {
  if (!data) return null;
  const { direction, magnitude_pct, confidence } = data;
  const isUp = direction === "increase";
  const isNeutral = direction === "neutral";
  return (
    <div className="flex items-center gap-3 py-2 border-b border-slate-100 last:border-0">
      <div className="w-24 text-xs font-medium text-slate-600 capitalize">{dimension}</div>
      <div className={`text-sm font-semibold w-24 ${isNeutral ? "text-slate-400" : isUp ? "text-red-600" : "text-green-600"}`}>
        {isNeutral ? "—" : isUp ? "▲" : "▼"} {isNeutral ? "neutral" : `${magnitude_pct ?? "?"}%`}
      </div>
      {confidence != null && (
        <div className="flex items-center gap-1">
          <div className="h-1.5 w-20 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-400 rounded-full"
              style={{ width: `${(confidence ?? 0) * 100}%` }}
            />
          </div>
          <span className="text-xs text-slate-400">{Math.round((confidence ?? 0) * 100)}%</span>
        </div>
      )}
    </div>
  );
}

export default function AssessmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: a, isLoading, error } = useSWR(`/api/assessments/${id}`, fetcher);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackAction, setFeedbackAction] = useState("");

  async function submitFeedback(action: string) {
    setFeedbackAction(action);
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assessment_id: id, user_action: action }),
    });
    setFeedbackSent(true);
  }

  if (isLoading) {
    return (
      <div className="p-8 text-slate-400 animate-pulse text-sm">Loading assessment…</div>
    );
  }
  if (error || !a) {
    return (
      <div className="p-8 text-slate-400 text-sm">
        Assessment not found.{" "}
        <Link href="/assessments" className="text-blue-500 hover:underline">
          ← Back
        </Link>
      </div>
    );
  }

  const entities = a.affected_entities || {};
  const impact = a.impact || {};
  const clauses: any[] = a.affected_clauses || [];
  const chain: any[] = a.reasoning_chain || [];

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-5">
      {/* Back + header */}
      <div>
        <Link href="/assessments" className="text-sm text-slate-400 hover:text-slate-600 mb-3 inline-block">
          ← Assessments
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">Assessment Detail</h1>
            <div className="flex items-center gap-3 mt-1">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[a.status] || STATUS_STYLES.pending}`}>
                {a.status?.replace(/_/g, " ")}
              </span>
              <span className="text-xs text-slate-400 font-mono">{a.id?.slice(0, 8)}…</span>
              {a.created_at && (
                <span className="text-xs text-slate-400">
                  {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                </span>
              )}
            </div>
          </div>
          {/* Confidence */}
          <div className="text-right">
            <div className="text-xs text-slate-400 mb-1">Confidence</div>
            <div className={`text-2xl font-bold ${
              (a.confidence ?? 0) >= 0.7 ? "text-green-600" :
              (a.confidence ?? 0) >= 0.45 ? "text-amber-600" : "text-red-500"
            }`}>
              {a.confidence != null ? `${Math.round(a.confidence * 100)}%` : "—"}
            </div>
          </div>
        </div>
      </div>

      {/* Signal context */}
      {a.signal && (
        <div className="bg-blue-50 border border-blue-100 rounded-xl px-5 py-3 flex items-start gap-3">
          <span className="text-blue-400 text-sm mt-0.5">📡</span>
          <div>
            <div className="text-sm font-medium text-blue-800">{a.signal.title || "Signal"}</div>
            <div className="text-xs text-blue-500 mt-0.5">
              {a.signal.source}
              {a.signal.occurred_at && ` · ${formatDistanceToNow(new Date(a.signal.occurred_at), { addSuffix: true })}`}
            </div>
            {a.signal.url && (
              <a href={a.signal.url} target="_blank" rel="noopener noreferrer"
                className="text-xs text-blue-500 hover:underline mt-1 inline-block">
                ↗ View source
              </a>
            )}
          </div>
        </div>
      )}

      {/* Summary */}
      <Section title="Executive Summary">
        <p className="text-sm text-slate-700 leading-relaxed">{a.summary}</p>
      </Section>

      {/* Affected entities */}
      {Object.keys(entities).some((k) => (entities[k] as string[]).length > 0) && (
        <Section title="Affected Entities">
          <div className="space-y-2">
            {Object.entries(entities).map(([type, items]) => {
              const arr = items as string[];
              if (!arr.length) return null;
              return (
                <div key={type} className="flex gap-2 items-start">
                  <div className="w-24 text-xs font-medium text-slate-500 capitalize shrink-0 pt-0.5">
                    {type}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {arr.map((item) => (
                      <span key={item} className="px-2 py-0.5 bg-slate-100 rounded text-xs text-slate-700">
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* Impact by dimension */}
      {Object.keys(impact).length > 0 && (
        <Section title="Impact by Dimension">
          {Object.entries(impact).map(([dim, data]) => (
            <ImpactRow key={dim} dimension={dim} data={data} />
          ))}
        </Section>
      )}

      {/* Contract clauses */}
      {clauses.length > 0 && (
        <Section title="Contract Clause Implications">
          <div className="space-y-2">
            {clauses.map((c, i) => (
              <div
                key={i}
                className={`rounded-lg border px-4 py-3 ${
                  c.triggered
                    ? "bg-red-50 border-red-200"
                    : "bg-slate-50 border-slate-200"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  {c.triggered && <span className="text-red-500 text-xs font-semibold">⚠ TRIGGERED</span>}
                  <span className="text-xs font-semibold text-slate-600">
                    {c.clause_type?.replace(/_/g, " ")}
                  </span>
                  {c.contract_id && (
                    <span className="text-xs text-slate-400 font-mono">{c.contract_id}</span>
                  )}
                </div>
                {c.detail && (
                  <p className="text-xs text-slate-600">{c.detail}</p>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Reasoning chain */}
      {chain.length > 0 && (
        <Section title="Reasoning Chain">
          <div className="space-y-3">
            {chain.map((step: any, i: number) => (
              <div key={i} className="flex gap-3">
                <div className="shrink-0 w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-500">
                  {step.step ?? i + 1}
                </div>
                <div>
                  <div className="text-sm font-medium text-slate-800">{step.claim}</div>
                  {step.inference && (
                    <div className="text-xs text-slate-500 mt-0.5">→ {step.inference}</div>
                  )}
                  {step.grounded_in && (
                    <div className="text-xs text-slate-400 mt-0.5 italic">
                      Source: {step.grounded_in}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Feedback widget */}
      <Section title="Analyst Feedback">
        {feedbackSent ? (
          <div className="text-sm text-green-600 font-medium">
            ✓ Feedback recorded ({feedbackAction}). Thank you.
          </div>
        ) : (
          <div>
            <p className="text-xs text-slate-500 mb-3">
              Your feedback trains the DSPy optimisation loop (Week 5).
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => submitFeedback("accept")}
                className="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 transition-colors"
              >
                ✓ Accept
              </button>
              <button
                onClick={() => submitFeedback("reject")}
                className="px-4 py-2 rounded-lg bg-red-100 text-red-700 text-sm font-medium hover:bg-red-200 transition-colors"
              >
                ✕ Reject
              </button>
              <button
                onClick={() => submitFeedback("edit")}
                className="px-4 py-2 rounded-lg bg-slate-100 text-slate-700 text-sm font-medium hover:bg-slate-200 transition-colors"
              >
                ✎ Needs Edit
              </button>
            </div>
          </div>
        )}
      </Section>
    </div>
  );
}
