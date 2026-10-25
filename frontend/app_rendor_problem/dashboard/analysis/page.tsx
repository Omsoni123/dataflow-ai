"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

type AskResult = {
  success?: boolean;
  question?: string;
  answer?: string;
  data?: Array<Record<string, unknown>>;
  sql?: string;
  detail?: string;
  message?: string;
};

const ANALYSIS_CONFIG: Record<string, { title: string; description: string; question: (metric?: string) => string }> = {
  "numeric-summary": {
    title: "Numeric summary",
    description: "Decision-ready statistics with exact values, context, and next actions.",
    question: (metric) => metric
      ? `Perform a decision-focused analysis of the numeric column "${metric}". Use SQL to return a compact result containing non-null count, null count if available, total, average, minimum, maximum, and median only if supported. Then explain what the actual returned values mean, identify the most important finding, state one limitation, and recommend one concrete next action. Use only existing columns and calculated results. Do not invent period changes, causes, or values.`
      : "Analyze the most useful numeric columns in my dataset. Return a compact SQL result with valid totals, averages, minimums, maximums, and counts for a few meaningful measures. Explain the 2-3 most decision-relevant findings using exact returned values, note any data-quality caveat, and recommend concrete next actions. Do not invent values or trends.",
  },
  "dimension-breakdown": {
    title: "Dimension breakdown",
    description: "Find which categories contribute most and where performance differs.",
    question: (metric) => `Create a decision-focused dimension breakdown${metric ? ` with special attention to "${metric}"` : ""}. Identify an existing categorical column and a relevant numeric measure. Return the top categories ranked by that measure, with counts and totals/averages where appropriate. Explain the biggest difference using exact query results, identify a category worth investigating, and suggest one actionable next step. Do not claim a category caused an outcome. If no suitable category/measure exists, say so clearly.`,
  },
  "time-trend": {
    title: "Time trend",
    description: "Understand direction and variability using a real date column where available.",
    question: (metric) => `Analyze a time trend${metric ? ` for "${metric}"` : ""} using an actual date/time column and a numeric measure from my dataset. Return a time-bucketed series with the measure and record count, ordered by time. Describe the direction and any notable peaks/dips only when supported by returned rows. Compare periods only if both periods exist. If there is no suitable date column or insufficient time coverage, explain that instead of fabricating a trend. Recommend one next action based on the evidence.`,
  },
  "numeric-relationships": {
    title: "Numeric relationships",
    description: "Explore useful associations and exceptions without confusing correlation with causation.",
    question: (metric) => `Investigate relationships between numeric fields${metric ? ` with special attention to "${metric}"` : ""}. Use existing columns only. Return a compact comparison or grouped result that can support the interpretation. State the exact evidence, explain a possible association cautiously, mention that association does not prove causation, and recommend one follow-up check. Do not claim a statistical correlation unless it was actually calculated.`,
  },
  "category-distribution": {
    title: "Category distribution",
    description: "See which groups dominate and how the dataset is distributed.",
    question: (metric) => `Analyze category distribution${metric ? ` with "${metric}" included where useful` : ""}. Identify a suitable categorical column and return the top categories by row count, plus a relevant numeric total or average if available. Include percentages only if they can be calculated from returned values. Explain the dominant category and any meaningful concentration or imbalance using exact values, then suggest one practical next step. If no suitable category exists, state that clearly.`,
  },
};

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return value.toLocaleString("en-IN", { maximumFractionDigits: 3 });
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function AnalysisPage() {
  const router = useRouter();
  const [type, setType] = useState("numeric-summary");
  const [metric, setMetric] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [result, setResult] = useState<AskResult | null>(null);
  const [question, setQuestion] = useState("");

  const config = useMemo(() => ANALYSIS_CONFIG[type] ?? ANALYSIS_CONFIG["numeric-summary"], [type]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedType = (params.get("type") ?? "numeric-summary").toLowerCase();
    const requestedMetric = params.get("metric") ?? "";
    const safeType = ANALYSIS_CONFIG[requestedType] ? requestedType : normalizeType(requestedType);
    const selectedType = ANALYSIS_CONFIG[safeType] ? safeType : "numeric-summary";
    setType(selectedType);
    setMetric(requestedMetric);
    const prompt = ANALYSIS_CONFIG[selectedType].question(requestedMetric || undefined);
    setQuestion(prompt);

    async function runAnalysis() {
      setLoading(true);
      setError("");
      setResult(null);
      const token = localStorage.getItem("access_token");
      if (!token) {
        router.push("/login");
        return;
      }

      const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "");
      if (!apiUrl) {
        setError("API URL is not configured. Set NEXT_PUBLIC_API_URL and restart the frontend.");
        setLoading(false);
        return;
      }

      try {
        const response = await fetch(`${apiUrl}/datasets/ask`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ question: prompt }),
        });
        const payload = await response.json().catch(() => ({}));
        if (response.status === 401) {
          localStorage.removeItem("access_token");
          router.push("/login");
          return;
        }
        if (!response.ok) {
          throw new Error(payload.detail ?? payload.message ?? `Analysis failed (${response.status}).`);
        }
        setResult(payload as AskResult);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to run this analysis.");
      } finally {
        setLoading(false);
      }
    }

    void runAnalysis();
  }, [router]);

  async function rerun() {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.push("/login");
      return;
    }
    const apiUrl = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/+$/, "");
    if (!apiUrl) {
      setError("API URL is not configured. Set NEXT_PUBLIC_API_URL and restart the frontend.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${apiUrl}/datasets/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ question }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail ?? `Analysis failed (${response.status}).`);
      setResult(payload as AskResult);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run this analysis.");
    } finally {
      setLoading(false);
    }
  }

  const rows = Array.isArray(result?.data) ? result.data : [];
  const columns = rows.length ? Object.keys(rows[0]) : [];

  return (
    <main className="min-h-screen bg-[#07050d] px-4 py-6 text-white sm:px-8 lg:px-10">
      <div className="mx-auto max-w-[1500px]">
        <header className="flex flex-col justify-between gap-4 border-b border-white/[0.08] pb-6 sm:flex-row sm:items-center">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-violet-300/70">DataFlow AI / Deep analysis</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">{config.title}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-white/50">{config.description}</p>
            {metric && <p className="mt-2 text-xs text-violet-200/80">Selected metric: {metric}</p>}
          </div>
          <button
            type="button"
            onClick={() => router.push("/dashboard")}
            className="self-start rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2.5 text-sm text-white/75 transition hover:border-violet-300/30 hover:bg-violet-500/10"
          >
            ← Back to dashboard
          </button>
        </header>

        <section className="mt-6 rounded-3xl border border-violet-300/15 bg-gradient-to-br from-[#17102b] via-[#100d1d] to-[#0b1020] p-5 sm:p-7">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-violet-300/20 bg-violet-400/10 px-3 py-1.5 text-[11px] font-medium text-violet-100">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                DATA-DRIVEN ANALYSIS
              </div>
              <h2 className="mt-4 text-lg font-semibold">Analysis result</h2>
              <p className="mt-1 text-sm text-white/45">Powered by your authenticated DataFlow AI analytics endpoint.</p>
            </div>
            <button
              type="button"
              onClick={rerun}
              disabled={loading}
              className="rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 px-4 py-2.5 text-sm font-semibold transition hover:brightness-110 disabled:opacity-50"
            >
              {loading ? "Analyzing…" : "Run again ↻"}
            </button>
          </div>

          <div className="mt-5 rounded-2xl border border-white/[0.08] bg-black/20 p-4 sm:p-5">
            <p className="text-xs font-semibold uppercase tracking-wider text-white/40">Analysis request</p>
            <p className="mt-2 text-sm leading-6 text-white/75">{question || "Preparing analysis…"}</p>
          </div>

          {loading && (
            <div className="mt-5 flex items-center gap-3 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-5 text-sm text-white/55">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-violet-300/30 border-t-violet-200" />
              Running the analysis against your dataset…
            </div>
          )}

          {error && (
            <div role="alert" className="mt-5 rounded-2xl border border-rose-300/20 bg-rose-400/[0.07] p-4 text-sm leading-6 text-rose-100">
              {error}
            </div>
          )}

          {!loading && !error && result && (
            <div className="mt-5 space-y-4">
              <div className="rounded-2xl border border-emerald-300/15 bg-emerald-400/[0.05] p-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-emerald-200/70">Findings from your data</p>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-white/80">{result.answer ?? "The query completed, but no explanation was returned."}</p>
              </div>

              {rows.length > 0 && (
                <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-black/20">
                  <div className="border-b border-white/[0.08] px-4 py-3">
                    <p className="text-sm font-semibold">Query results</p>
                    <p className="mt-1 text-xs text-white/40">{rows.length.toLocaleString("en-IN")} returned rows</p>
                  </div>
                  <div className="max-h-[520px] overflow-auto">
                    <table className="w-full min-w-[520px] border-collapse text-left text-sm">
                      <thead className="sticky top-0 bg-[#171225] text-xs uppercase tracking-wider text-white/45">
                        <tr>{columns.map((column) => <th key={column} className="border-b border-white/[0.08] px-4 py-3 font-medium">{column}</th>)}</tr>
                      </thead>
                      <tbody>
                        {rows.slice(0, 100).map((row, index) => (
                          <tr key={index} className="border-b border-white/[0.05] last:border-0 hover:bg-white/[0.025]">
                            {columns.map((column) => <td key={column} className="max-w-[360px] px-4 py-3 text-white/70">{formatValue(row[column])}</td>)}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {result.sql && (
                <details className="rounded-2xl border border-white/[0.08] bg-black/20 p-4">
                  <summary className="cursor-pointer text-xs font-medium text-white/50">Show generated SQL</summary>
                  <pre className="mt-3 overflow-auto whitespace-pre-wrap text-xs leading-6 text-violet-100/80">{result.sql}</pre>
                </details>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function normalizeType(value: string): string {
  const normalized = value.replaceAll("_", "-").replaceAll(" ", "-");
  const aliases: Record<string, string> = {
    "numeric-summary": "numeric-summary",
    "numeric-summary-analysis": "numeric-summary",
    "dimension-breakdown": "dimension-breakdown",
    "time-trend": "time-trend",
    "numeric-relationships": "numeric-relationships",
    "category-distribution": "category-distribution",
    "numeric-relationship": "numeric-relationships",
    "category-breakdown": "category-distribution",
    "dimension-breakdown-analysis": "dimension-breakdown",
  };
  return aliases[normalized] ?? normalized;
}
