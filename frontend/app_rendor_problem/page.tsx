"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const suggestions = [
  "What are my top products?",
  "Show revenue by region",
  "Which category is most profitable?",
];

export default function Home() {
  const router = useRouter();
  const [question, setQuestion] = useState("");

  return (
    <main className="min-h-screen overflow-hidden bg-[#07050d] text-white">
      {/* Ambient background */}
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute left-[15%] top-[-250px] h-[600px] w-[600px] rounded-full bg-purple-700/20 blur-[160px]" />
        <div className="absolute right-[-180px] top-[30%] h-[500px] w-[500px] rounded-full bg-fuchsia-600/10 blur-[150px]" />
        <div className="absolute bottom-[-250px] left-[35%] h-[500px] w-[500px] rounded-full bg-violet-700/10 blur-[150px]" />
      </div>

      {/* Navigation */}
      <nav className="relative z-20 border-b border-white/[0.07] bg-[#07050d]/70 backdrop-blur-xl">
        <div className="mx-auto flex h-[76px] max-w-[1400px] items-center justify-between px-6 lg:px-10">
          <div className="flex items-center gap-3">
            <div className="relative flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl bg-gradient-to-br from-violet-500 via-purple-600 to-fuchsia-600 shadow-lg shadow-purple-900/30">
              <span className="text-lg font-bold">D</span>
              <div className="absolute inset-x-0 bottom-0 h-px bg-white/40" />
            </div>

            <div>
              <div className="text-[17px] font-semibold tracking-tight">
                DataFlow <span className="text-purple-400">AI</span>
              </div>

              <div className="text-[9px] font-medium uppercase tracking-[0.28em] text-white/35">
                Intelligent Analytics By Om Soni
              </div>
            </div>
          </div>

          <div className="hidden items-center gap-8 md:flex">
            <a
              href="#features"
              className="text-sm text-white/45 transition hover:text-white"
            >
              Features
            </a>

            <a
              href="#analyst"
              className="text-sm text-white/45 transition hover:text-white"
            >
              AI Analyst
            </a>

            <a
              href="#about"
              className="text-sm text-white/45 transition hover:text-white"
            >
              About
            </a>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/login")}
              className="hidden rounded-lg px-3 py-2 text-sm text-white/55 transition hover:text-white sm:block"
            >
              Sign in
            </button>

            <button
              onClick={() => router.push("/login")}
              className="rounded-lg border border-purple-400/20 bg-purple-600/90 px-4 py-2 text-sm font-medium shadow-lg shadow-purple-900/20 transition hover:bg-purple-500"
            >
              Get started
            </button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-10 mx-auto max-w-[1400px] px-6 pb-16 pt-20 lg:px-10 lg:pt-28">
        <div className="max-w-4xl">
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-purple-400/20 bg-purple-500/[0.08] px-3.5 py-1.5">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-purple-400 opacity-50" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-purple-400" />
            </span>

            <span className="text-xs font-medium text-purple-200">
              AI-powered analytics workspace
            </span>
          </div>

          <h1 className="text-[52px] font-semibold leading-[1.02] tracking-[-0.045em] sm:text-6xl lg:text-[76px]">
            Ask your data.
            <br />

            <span className="bg-gradient-to-r from-violet-300 via-purple-400 to-fuchsia-400 bg-clip-text text-transparent">
              Understand your business.
            </span>
          </h1>

          <p className="mt-7 max-w-2xl text-base leading-7 text-white/45 sm:text-lg">
            Upload your data, ask questions in natural language, and get
            accurate business insights without writing SQL.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            {/* Main CTA */}
            <button
              onClick={() => router.push("/login")}
              className="rounded-xl bg-white px-5 py-3 text-sm font-semibold text-black transition hover:bg-white/90"
            >
              Ask your data →
            </button>

            <button
              onClick={() =>
                document
                  .getElementById("features")
                  ?.scrollIntoView({ behavior: "smooth" })
              }
              className="rounded-xl border border-white/10 bg-white/[0.03] px-5 py-3 text-sm font-medium text-white/65 transition hover:border-purple-400/20 hover:text-white"
            >
              View capabilities
            </button>
          </div>
        </div>

        {/* Product preview */}
        <div className="relative mt-16">
          <div className="absolute -inset-10 rounded-[40px] bg-purple-600/10 blur-[80px]" />

          <div className="relative overflow-hidden rounded-3xl border border-white/[0.09] bg-[#0d0a15]/90 shadow-2xl shadow-black/40">
            {/* Preview top bar */}
            <div className="flex h-14 items-center justify-between border-b border-white/[0.07] px-5">
              <div className="flex items-center gap-3">
                <div className="flex gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-white/10" />
                  <span className="h-2.5 w-2.5 rounded-full bg-white/10" />
                  <span className="h-2.5 w-2.5 rounded-full bg-white/10" />
                </div>

                <span className="text-xs text-white/35">
                  DataFlow AI / Analytics
                </span>
              </div>

              <div className="flex items-center gap-2 text-[11px] text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                System operational
              </div>
            </div>

            <div className="grid lg:grid-cols-[220px_1fr]">
              {/* Sidebar */}
              <aside className="hidden border-r border-white/[0.07] p-5 lg:block">
                <p className="mb-4 text-[10px] font-semibold uppercase tracking-[0.2em] text-white/25">
                  Workspace
                </p>

                <div className="rounded-xl bg-purple-500/10 px-3 py-2.5 text-sm text-purple-200">
                  Overview
                </div>

                <div className="mt-1 px-3 py-2.5 text-sm text-white/35">
                  Analytics
                </div>

                <div className="px-3 py-2.5 text-sm text-white/35">
                  Datasets
                </div>

                <div className="px-3 py-2.5 text-sm text-white/35">
                  AI conversations
                </div>

                <div className="mt-8 border-t border-white/[0.06] pt-5">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-white/25">
                    Connected
                  </p>

                  <div className="mt-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-2 rounded-full bg-emerald-400" />
                      <span className="text-xs text-white/60">
                        sales.csv
                      </span>
                    </div>

                    <p className="mt-1 text-[10px] text-white/25">
                      5,000 rows · 13 columns
                    </p>
                  </div>
                </div>
              </aside>

              {/* Dashboard preview */}
              <div className="p-5 sm:p-7">
                <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
                  <div>
                    <p className="text-xs text-white/30">Overview</p>
                    <h3 className="mt-1 text-xl font-semibold">
                      Business performance
                    </h3>
                  </div>

                  <div className="rounded-lg border border-white/[0.07] bg-white/[0.02] px-3 py-2 text-xs text-white/40">
                    Last 30 days ▾
                  </div>
                </div>

                <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <PreviewKpi
                    label="Revenue"
                    value="₹16.72 Cr"
                    change="+12.4%"
                  />

                  <PreviewKpi
                    label="Profit"
                    value="₹4.53 Cr"
                    change="+8.7%"
                  />

                  <PreviewKpi
                    label="Margin"
                    value="27.08%"
                    change="+2.1%"
                  />

                  <PreviewKpi
                    label="Units"
                    value="15,894"
                    change="+6.3%"
                  />
                </div>

                <div className="mt-4 grid gap-4 lg:grid-cols-[1.4fr_0.8fr]">
                  <div className="rounded-2xl border border-white/[0.07] bg-white/[0.02] p-5">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-white/30">
                          Revenue trend
                        </p>

                        <p className="mt-1 text-sm font-medium text-white/80">
                          Monthly performance
                        </p>
                      </div>

                      <span className="text-xs text-purple-300">
                        +12.4%
                      </span>
                    </div>

                    <div className="mt-8 flex h-28 items-end gap-2">
                      {[35, 48, 42, 63, 57, 76, 68, 88, 73, 95, 82, 100].map(
                        (height, index) => (
                          <div
                            key={index}
                            className="group relative flex h-full flex-1 items-end"
                          >
                            <div
                              style={{ height: `${height}%` }}
                              className="w-full rounded-t-md bg-gradient-to-t from-purple-700/50 to-purple-400/80 transition group-hover:from-purple-600 group-hover:to-fuchsia-400"
                            />
                          </div>
                        ),
                      )}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-purple-400/10 bg-purple-500/[0.04] p-5">
                    <div className="flex items-center gap-2">
                      <span className="text-purple-300">✦</span>
                      <span className="text-xs font-medium text-white/70">
                        AI insight
                      </span>
                    </div>

                    <p className="mt-5 text-sm leading-6 text-white/55">
                      Revenue is growing steadily, while profit margin remains
                      above 27%. The strongest contribution is coming from the
                      top-performing product categories.
                    </p>

                    <button className="mt-5 text-xs font-medium text-purple-300 hover:text-purple-200">
                      Explore insight →
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Capability strip */}
      <section
        id="features"
        className="relative z-10 border-y border-white/[0.06] bg-white/[0.015]"
      >
        <div className="mx-auto grid max-w-[1400px] divide-y divide-white/[0.06] px-6 sm:grid-cols-3 sm:divide-x sm:divide-y-0 lg:px-10">
          <Capability
            number="01"
            title="Connect your data"
            description="Upload CSV datasets and build a secure analytics workspace."
          />

          <Capability
            number="02"
            title="Ask naturally"
            description="Turn business questions into data queries with AI."
          />

          <Capability
            number="03"
            title="Act on insights"
            description="Understand trends, performance and opportunities faster."
          />
        </div>
      </section>

      {/* AI Analyst */}
      <section
        id="analyst"
        className="relative z-10 mx-auto max-w-[1100px] px-6 py-24 lg:px-10"
      >
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-xl border border-purple-400/20 bg-purple-500/10 text-purple-300">
            ✦
          </div>

          <p className="text-xs font-medium uppercase tracking-[0.25em] text-purple-300/70">
            AI Analyst
          </p>

          <h2 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
            Talk to your data.
          </h2>

          <p className="mx-auto mt-4 max-w-xl text-sm leading-6 text-white/40">
            Ask a question in plain English. DataFlow AI will understand your
            dataset and return an actionable answer.
          </p>
        </div>

        <div className="mt-10 rounded-3xl border border-purple-400/15 bg-gradient-to-b from-purple-500/[0.07] to-white/[0.015] p-5 shadow-2xl shadow-purple-950/20 sm:p-7">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Ask DataFlow</p>
              <p className="mt-1 text-xs text-white/30">
                Demo preview
              </p>
            </div>

            <span className="flex items-center gap-2 text-xs text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              Ready
            </span>
          </div>

          <div className="rounded-2xl border border-white/[0.08] bg-black/20 p-4">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. What were my total sales last month?"
              className="min-h-[120px] w-full resize-none bg-transparent text-sm leading-6 text-white outline-none placeholder:text-white/20"
            />

            <div className="flex flex-col justify-between gap-4 border-t border-white/[0.07] pt-4 sm:flex-row sm:items-center">
              <span className="text-[11px] text-white/25">
                Natural language → SQL → validated result → AI explanation
              </span>

              <button
                onClick={() => router.push("/login")}
                disabled={!question.trim()}
                className="rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 px-5 py-2.5 text-sm font-semibold shadow-lg shadow-purple-900/20 transition hover:from-purple-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-30"
              >
                Analyze →
              </button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {suggestions.map((item) => (
              <button
                key={item}
                onClick={() => setQuestion(item)}
                className="rounded-full border border-white/[0.08] bg-white/[0.025] px-3.5 py-2 text-xs text-white/40 transition hover:border-purple-400/20 hover:bg-purple-500/[0.08] hover:text-purple-200"
              >
                {item}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer
        id="about"
        className="relative z-10 border-t border-white/[0.06]"
      >
        <div className="mx-auto flex max-w-[1400px] flex-col justify-between gap-4 px-6 py-8 text-xs text-white/25 sm:flex-row lg:px-10">
          <span>© 2026 DataFlow AI</span>
          <span>Intelligent analytics for modern teams.</span>
        </div>
      </footer>
    </main>
  );
}

function PreviewKpi({
  label,
  value,
  change,
}: {
  label: string;
  value: string;
  change: string;
}) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
      <p className="text-[10px] uppercase tracking-wider text-white/25">
        {label}
      </p>

      <div className="mt-2 flex items-end justify-between gap-2">
        <p className="text-lg font-semibold">{value}</p>
        <span className="text-[10px] text-emerald-400">{change}</span>
      </div>
    </div>
  );
}

function Capability({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description: string;
}) {
  return (
    <div className="px-6 py-8 sm:py-10 lg:px-10">
      <p className="text-[10px] font-semibold tracking-[0.2em] text-purple-400/70">
        {number}
      </p>

      <h3 className="mt-3 text-sm font-semibold">{title}</h3>

      <p className="mt-2 max-w-sm text-xs leading-5 text-white/35">
        {description}
      </p>
    </div>
  );
}