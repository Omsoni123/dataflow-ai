"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

type Kpis = {
  total_sales: number;
  total_profit: number;
  profit_margin: number;
  total_units: number;
  total_orders: number;
  total_customers: number;
};

type ChatMessage = {
  question: string;
  answer: string;
};

// Production-ready API configuration
const API_URL = process.env.NEXT_PUBLIC_API_URL;

export default function Dashboard() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploading, setUploading] = useState(false);
  const [asking, setAsking] = useState(false);

  const [error, setError] = useState("");
  const [aiError, setAiError] = useState("");

  const [fileName, setFileName] = useState("");
  const [kpis, setKpis] = useState<Kpis | null>(null);

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);

  // ==========================================================
  // API CONFIGURATION
  // ==========================================================

  function getApiUrl() {
    if (!API_URL) {
      throw new Error(
        "API URL is not configured. Please set NEXT_PUBLIC_API_URL."
      );
    }

    return API_URL.replace(/\/+$/, "");
  }

  // ==========================================================
  // AUTH
  // ==========================================================

  function getToken() {
    if (typeof window === "undefined") {
      return null;
    }

    return localStorage.getItem("access_token");
  }

  function logout() {
    localStorage.removeItem("access_token");
    router.push("/");
  }

  // ==========================================================
  // FILE PICKER
  // ==========================================================

  function openFilePicker() {
    setError("");
    fileInputRef.current?.click();
  }

  // ==========================================================
  // UPLOAD DATASET
  // ==========================================================

  async function handleFileUpload(
    event: React.ChangeEvent<HTMLInputElement>
  ) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Please upload a CSV file.");
      event.target.value = "";
      return;
    }

    const token = getToken();

    if (!token) {
      setError("Your session has expired. Please log in again.");
      return;
    }

    setUploading(true);
    setError("");

    try {
      const apiUrl = getApiUrl();

      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${apiUrl}/datasets/upload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      const data = await response.json().catch(() => ({}));

      if (response.status === 401) {
        localStorage.removeItem("access_token");
        router.push("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(
          data.detail || "Dataset upload failed."
        );
      }

      setFileName(file.name);
      setKpis(data.kpis);

      // Reset AI workspace for the new dataset
      setAnswer("");
      setChatHistory([]);
      setAiError("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while uploading the dataset."
      );
    } finally {
      setUploading(false);

      // Allow same file to be selected again
      event.target.value = "";
    }
  }

  // ==========================================================
  // ASK AI
  // ==========================================================

  async function askAI(customQuestion?: string) {
    const finalQuestion = (
      customQuestion ?? question
    ).trim();

    if (!finalQuestion) {
      return;
    }

    const token = getToken();

    if (!token) {
      setAiError("Your session has expired. Please log in again.");
      return;
    }

    if (!kpis) {
      setAiError("Please upload a dataset first.");
      return;
    }

    setAsking(true);
    setAiError("");
    setAnswer("");

    try {
      const apiUrl = getApiUrl();

      const response = await fetch(`${apiUrl}/datasets/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          question: finalQuestion,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (response.status === 401) {
        localStorage.removeItem("access_token");
        router.push("/login");
        return;
      }

      if (!response.ok) {
        throw new Error(
          data.detail || "AI analysis failed."
        );
      }

      const newAnswer = data.answer;

      setAnswer(newAnswer);

      setChatHistory((previous) => [
        ...previous,
        {
          question: finalQuestion,
          answer: newAnswer,
        },
      ]);

      setQuestion("");
    } catch (err) {
      setAiError(
        err instanceof Error
          ? err.message
          : "Something went wrong while asking AI."
      );
    } finally {
      setAsking(false);
    }
  }

  function handleQuestionSubmit(
    event: React.FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();
    askAI();
  }

  // ==========================================================
  // UI
  // ==========================================================

  return (
    <main className="min-h-screen bg-[#07050d] text-white">

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv"
        onChange={handleFileUpload}
        className="hidden"
      />

      {/* =====================================================
          NAVIGATION
      ===================================================== */}

      <nav className="border-b border-white/[0.07] bg-[#07050d]/90 backdrop-blur-xl">
        <div className="mx-auto flex h-[72px] max-w-[1500px] items-center justify-between px-6 lg:px-10">

          <div className="flex items-center gap-3">

            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 via-purple-600 to-fuchsia-600">
              <span className="font-bold">D</span>
            </div>

            <div>
              <div className="text-[17px] font-semibold">
                DataFlow{" "}
                <span className="text-purple-400">
                  AI
                </span>
              </div>

              <div className="text-[9px] uppercase tracking-[0.25em] text-white/30">
                Intelligent Analytics
              </div>
            </div>

          </div>

          <button
            onClick={logout}
            className="rounded-lg px-4 py-2 text-sm text-white/50 transition hover:bg-white/[0.05] hover:text-white"
          >
            Logout
          </button>

        </div>
      </nav>

      {/* =====================================================
          DASHBOARD
      ===================================================== */}

      <div className="mx-auto max-w-[1500px] px-6 py-8 lg:px-10">

        {/* Header */}
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">

          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-purple-300/60">
              Workspace
            </p>

            <h1 className="mt-2 text-3xl font-semibold tracking-tight">
              Analytics Dashboard
            </h1>

            <p className="mt-2 text-sm text-white/40">
              Upload your data and turn it into actionable insights.
            </p>
          </div>

          <button
            onClick={openFilePicker}
            disabled={uploading}
            className="rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 px-5 py-3 text-sm font-semibold shadow-lg shadow-purple-900/20 transition hover:from-purple-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uploading ? "Uploading..." : "+ Add Data"}
          </button>

        </div>

        {/* =================================================
            DATASET SECTION
        ================================================= */}

        <section className="mt-8 rounded-3xl border border-purple-400/10 bg-gradient-to-b from-purple-500/[0.06] to-white/[0.015] p-8">

          {!fileName ? (

            <div className="mx-auto max-w-2xl py-16 text-center">

              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-purple-400/20 bg-purple-500/10 text-2xl text-purple-300">
                ↑
              </div>

              <h2 className="mt-6 text-2xl font-semibold">
                Your analytics workspace is ready
              </h2>

              <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-white/40">
                Upload a CSV dataset to automatically clean your
                data, calculate business metrics, and start asking
                questions with AI.
              </p>

              <button
                onClick={openFilePicker}
                disabled={uploading}
                className="mt-7 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-black transition hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {uploading ? "Uploading..." : "Upload CSV"}
              </button>

              {uploading && (
                <p className="mt-4 text-xs text-purple-300">
                  Understanding your dataset...
                </p>
              )}

              {error && (
                <div className="mx-auto mt-5 max-w-lg rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                  {error}
                </div>
              )}

            </div>

          ) : (

            <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">

              <div>

                <div className="flex items-center gap-2">

                  <span className="h-2 w-2 rounded-full bg-emerald-400" />

                  <span className="text-sm font-medium text-emerald-300">
                    Dataset connected
                  </span>

                </div>

                <h2 className="mt-3 text-xl font-semibold">
                  {fileName}
                </h2>

                <p className="mt-1 text-xs text-white/30">
                  Dataset processed successfully
                </p>

              </div>

              <button
                onClick={openFilePicker}
                disabled={uploading}
                className="rounded-xl border border-white/10 bg-white/[0.04] px-5 py-3 text-sm font-medium text-white/70 transition hover:border-purple-400/20 hover:text-white disabled:opacity-50"
              >
                {uploading
                  ? "Uploading..."
                  : "Upload New Dataset"}
              </button>

            </div>

          )}

          {error && fileName && (
            <div className="mt-5 rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </div>
          )}

        </section>

        {/* =================================================
            KPI CARDS
        ================================================= */}

        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

          <KpiCard
            label="Revenue"
            value={
              kpis
                ? formatCrore(kpis.total_sales)
                : "—"
            }
          />

          <KpiCard
            label="Profit"
            value={
              kpis
                ? formatCrore(kpis.total_profit)
                : "—"
            }
          />

          <KpiCard
            label="Profit Margin"
            value={
              kpis
                ? `${(kpis.profit_margin * 100).toFixed(2)}%`
                : "—"
            }
          />

          <KpiCard
            label="Units Sold"
            value={
              kpis
                ? kpis.total_units.toLocaleString("en-IN")
                : "—"
            }
          />

        </section>

        {/* =================================================
            ADDITIONAL METRICS
        ================================================= */}

        {kpis && (
          <section className="mt-4 grid gap-4 sm:grid-cols-2">

            <KpiCard
              label="Orders"
              value={kpis.total_orders.toLocaleString("en-IN")}
            />

            <KpiCard
              label="Customers"
              value={kpis.total_customers.toLocaleString("en-IN")}
            />

          </section>
        )}

        {/* =================================================
            AI ANALYST
        ================================================= */}

        <section className="mt-6 rounded-3xl border border-purple-400/10 bg-gradient-to-b from-purple-500/[0.05] to-white/[0.02] p-6">

          {/* AI Header */}

          <div className="flex items-center gap-3">

            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-lg text-purple-300">
              ✦
            </div>

            <div>
              <h2 className="font-semibold">
                AI Analyst
              </h2>

              <p className="text-xs text-white/30">
                Ask questions about your data in plain English
              </p>
            </div>

          </div>

          {!kpis ? (

            <div className="mt-5 flex min-h-[150px] items-center justify-center rounded-2xl border border-dashed border-white/10 bg-black/20">

              <div className="text-center">

                <p className="text-sm text-white/30">
                  Upload a dataset to activate AI Analyst
                </p>

                <p className="mt-2 text-xs text-white/20">
                  Ask questions about sales, profit, products,
                  customers and more.
                </p>

              </div>

            </div>

          ) : (

            <>

              {/* Suggested questions */}

              <div className="mt-5 flex flex-wrap gap-2">

                {[
                  "What are the top 5 products by sales?",
                  "Which category has the highest profit?",
                  "What is my total profit?",
                  "Which region generated the most sales?",
                ].map((item) => (

                  <button
                    key={item}
                    onClick={() => askAI(item)}
                    disabled={asking}
                    className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-xs text-white/50 transition hover:border-purple-400/30 hover:bg-purple-500/10 hover:text-purple-200 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {item}
                  </button>

                ))}

              </div>

              {/* Question input */}

              <form
                onSubmit={handleQuestionSubmit}
                className="mt-5"
              >

                <div className="flex flex-col gap-3 sm:flex-row">

                  <input
                    value={question}
                    onChange={(event) =>
                      setQuestion(event.target.value)
                    }
                    placeholder="Ask anything about your dataset..."
                    disabled={asking}
                    className="flex-1 rounded-xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none placeholder:text-white/20 focus:border-purple-400/40"
                  />

                  <button
                    type="submit"
                    disabled={
                      asking ||
                      !question.trim()
                    }
                    className="rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 px-6 py-3 text-sm font-semibold transition hover:from-purple-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {asking ? "Thinking..." : "Ask AI"}
                  </button>

                </div>

              </form>

              {/* Loading */}

              {asking && (
                <div className="mt-5 rounded-2xl border border-purple-400/10 bg-purple-500/[0.04] p-5">

                  <div className="flex items-center gap-3">

                    <div className="h-2 w-2 animate-pulse rounded-full bg-purple-400" />

                    <p className="text-sm text-purple-200">
                      Analyzing your data...
                    </p>

                  </div>

                  <p className="mt-2 text-xs text-white/25">
                    Groq is generating and validating the analysis.
                  </p>

                </div>
              )}

              {/* Error */}

              {aiError && (
                <div className="mt-5 rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                  {aiError}
                </div>
              )}

              {/* Latest answer */}

              {answer && !asking && (
                <div className="mt-5 rounded-2xl border border-purple-400/20 bg-purple-500/[0.06] p-6">

                  <div className="flex items-center gap-2">

                    <span className="text-purple-300">
                      ✦
                    </span>

                    <span className="text-xs font-medium uppercase tracking-wider text-purple-300/70">
                      AI Insight
                    </span>

                  </div>

                  <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-white/80">
                    {answer}
                  </p>

                </div>
              )}

              {/* Conversation history */}

              {chatHistory.length > 1 && (
                <div className="mt-6">

                  <p className="mb-3 text-xs uppercase tracking-wider text-white/20">
                    Recent Questions
                  </p>

                  <div className="space-y-3">

                    {chatHistory
                      .slice(0, -1)
                      .slice(-3)
                      .reverse()
                      .map((chat, index) => (

                        <div
                          key={`${chat.question}-${index}`}
                          className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4"
                        >

                          <p className="text-xs text-purple-300/70">
                            {chat.question}
                          </p>

                          <p className="mt-2 text-sm leading-6 text-white/50">
                            {chat.answer}
                          </p>

                        </div>

                      ))}

                  </div>

                </div>
              )}

            </>

          )}

        </section>

      </div>

    </main>
  );
}

// ============================================================
// HELPERS
// ============================================================

function formatCrore(value: number) {
  return `₹${(value / 10000000).toFixed(2)} Cr`;
}

// ============================================================
// KPI CARD
// ============================================================

function KpiCard({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">

      <p className="text-xs uppercase tracking-wider text-white/25">
        {label}
      </p>

      <p className="mt-3 text-2xl font-semibold">
        {value}
      </p>

      <p className="mt-2 text-[11px] text-white/20">
        {value === "—"
          ? "Waiting for dataset"
          : "From uploaded dataset"}
      </p>

    </div>
  );
}