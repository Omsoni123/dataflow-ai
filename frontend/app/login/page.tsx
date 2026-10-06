"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type AuthMode = "login" | "signup";

export default function LoginPage() {
  const router = useRouter();

  const [mode, setMode] = useState<AuthMode>("login");

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  function switchMode(newMode: AuthMode) {
    setMode(newMode);
    setError("");
    setSuccess("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL;

      if (!API_URL) {
        throw new Error("API URL is not configured.");
      }

      const endpoint =
        mode === "login"
          ? `${API_URL}/auth/login`
          : `${API_URL}/auth/signup`;

      const body =
        mode === "login"
          ? {
              email,
              password,
            }
          : {
              name,
              email,
              password,
            };

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
            (mode === "login"
              ? "Login failed"
              : "Account creation failed")
        );
      }

      if (mode === "login") {
        localStorage.setItem("access_token", data.access_token);
        router.push("/dashboard");
      } else {
        setSuccess("Account created successfully. You can now sign in.");

        setName("");
        setPassword("");

        setMode("login");
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : mode === "login"
          ? "Login failed"
          : "Account creation failed"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#07050d] px-6 text-white">
      <div className="w-full max-w-md">

        {/* Logo / Header */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 via-purple-600 to-fuchsia-600 text-xl font-bold shadow-lg shadow-purple-900/30">
            D
          </div>

          <h1 className="text-3xl font-semibold">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h1>

          <p className="mt-2 text-sm text-white/40">
            {mode === "login"
              ? "Sign in to your DataFlow AI workspace"
              : "Start analyzing your data with DataFlow AI"}
          </p>
        </div>

        {/* Auth Card */}
        <div className="rounded-3xl border border-white/[0.08] bg-white/[0.03] p-7 shadow-2xl">

          {/* Tabs */}
          <div className="mb-7 grid grid-cols-2 rounded-xl bg-black/30 p-1">
            <button
              type="button"
              onClick={() => switchMode("login")}
              className={`rounded-lg px-4 py-2.5 text-sm font-medium transition ${
                mode === "login"
                  ? "bg-white text-black shadow"
                  : "text-white/40 hover:text-white"
              }`}
            >
              Sign In
            </button>

            <button
              type="button"
              onClick={() => switchMode("signup")}
              className={`rounded-lg px-4 py-2.5 text-sm font-medium transition ${
                mode === "signup"
                  ? "bg-white text-black shadow"
                  : "text-white/40 hover:text-white"
              }`}
            >
              Create Account
            </button>
          </div>

          <form onSubmit={handleSubmit}>

            {/* Name - Signup only */}
            {mode === "signup" && (
              <>
                <label className="text-sm text-white/70">
                  Name
                </label>

                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  required
                  className="mt-2 mb-5 w-full rounded-xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none placeholder:text-white/20 focus:border-purple-400/40"
                />
              </>
            )}

            {/* Email */}
            <label className="text-sm text-white/70">
              Email
            </label>

            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="mt-2 mb-5 w-full rounded-xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none placeholder:text-white/20 focus:border-purple-400/40"
            />

            {/* Password */}
            <label className="text-sm text-white/70">
              Password
            </label>

            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={8}
              className="mt-2 mb-5 w-full rounded-xl border border-white/[0.08] bg-black/30 px-4 py-3 text-sm text-white outline-none placeholder:text-white/20 focus:border-purple-400/40"
            />

            {/* Error */}
            {error && (
              <div className="mb-4 rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                {error}
              </div>
            )}

            {/* Success */}
            {success && (
              <div className="mb-4 rounded-xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
                {success}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 px-5 py-3 text-sm font-semibold transition hover:from-purple-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading
                ? mode === "login"
                  ? "Signing in..."
                  : "Creating account..."
                : mode === "login"
                ? "Sign in"
                : "Create account"}
            </button>
          </form>

          {/* Switch text */}
          <div className="mt-6 text-center text-sm text-white/40">
            {mode === "login" ? (
              <>
                Don't have an account?{" "}
                <button
                  type="button"
                  onClick={() => switchMode("signup")}
                  className="font-medium text-purple-400 hover:text-purple-300"
                >
                  Create one
                </button>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => switchMode("login")}
                  className="font-medium text-purple-400 hover:text-purple-300"
                >
                  Sign in
                </button>
              </>
            )}
          </div>

          {/* Back */}
          <button
            type="button"
            onClick={() => router.push("/")}
            className="mt-5 w-full text-sm text-white/30 transition hover:text-white"
          >
            ← Back to DataFlow AI
          </button>

        </div>
      </div>
    </main>
  );
}