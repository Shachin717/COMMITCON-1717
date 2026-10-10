"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { 
  Building2, 
  Lock, 
  Mail, 
  Eye, 
  EyeOff, 
  ArrowRight, 
  ArrowLeft,
  AlertCircle, 
  ShieldAlert, 
  Boxes
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { Aurora, Particles, BlurText } from "@/components/reactbits";
import { ThemeToggle } from "@/components/theme-toggle";

interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: number;
    name: string;
    email: string;
    role: "ADMIN" | "COORDINATOR" | "FACULTY" | "HOD";
    is_active: boolean;
    must_change_password: boolean;
    department_id?: number | null;
  };
}

function CoordinatorLoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const isExpired = searchParams.get("expired") === "1";
  const redirectQuery = searchParams.get("redirect");

  const [email, setEmail] = useState("coordinator.block_a@git.edu");
  const [password, setPassword] = useState("Coord@123");
  const [showPassword, setShowPassword] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);

    try {
      const response = await apiClient<LoginResponse>("/api/auth/coordinator/login", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          password,
        }),
      });

      // Synchronize role cookie for client-side routing & middleware fast-path
      document.cookie = `user_role=COORDINATOR; path=/; max-age=86400`;

      if (response.user.must_change_password) {
        router.push(`/change-password?forced=1&redirect=${encodeURIComponent("/coordinator")}`);
        return;
      }

      const finalDestination =
        redirectQuery && redirectQuery.startsWith("/coordinator") && !redirectQuery.startsWith("/coordinator/login")
          ? redirectQuery
          : "/coordinator";
      router.push(finalDestination);
    } catch (err: any) {
      if (err.status === 401) {
        setErrorMsg("Invalid credentials. Please verify your email and password.");
      } else if (err.status === 429) {
        setErrorMsg("Too many login attempts. Please wait a minute and try again.");
      } else {
        setErrorMsg(err.message || "Failed to sign in. Please verify your connection.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex bg-[var(--background)] relative overflow-hidden">
      {/* LEFT BRAND PANEL (Desktop) with Sky/Blue Coordinator Accent */}
      <div className="hidden lg:flex lg:w-5/12 relative flex-col justify-between p-12 overflow-hidden border-r border-[var(--border)] bg-gradient-to-br from-slate-950 via-sky-950 to-slate-900 text-white">
        <Aurora colorStops={["#0284c7", "#38bdf8", "#0369a1"]} className="opacity-50" />
        <Particles quantity={40} color="#7dd3fc" className="opacity-65" />

        <div className="relative z-10 flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-sky-600 shadow-lg shadow-sky-500/30 flex items-center justify-center text-white">
            <Building2 className="w-6 h-6" />
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight text-white block">
              Smart Classroom
            </span>
            <span className="text-xs text-sky-200 font-medium">
              Block Coordinator Portal
            </span>
          </div>
        </div>

        <div className="relative z-10 space-y-4 my-auto max-w-md">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-500/20 backdrop-blur-md border border-sky-400/30 text-xs font-semibold text-sky-200">
            <Boxes className="w-3.5 h-3.5" />
            <span>Block Management Gateway</span>
          </div>
          <h2 className="text-3xl font-extrabold tracking-tight text-white leading-tight">
            Classroom Approvals & Building Resource Logistics.
          </h2>
          <p className="text-sm text-slate-300 leading-relaxed">
            Authorized portal for physical block coordinators to review student booking requests, block rooms for maintenance or exams, and manage wing schedules.
          </p>

          <div className="pt-4 space-y-3">
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <div className="w-5 h-5 rounded-full bg-sky-500/20 text-sky-400 flex items-center justify-center font-bold">✓</div>
              <span>One-click batch approvals and intelligent re-allocations</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <div className="w-5 h-5 rounded-full bg-sky-500/20 text-sky-400 flex items-center justify-center font-bold">✓</div>
              <span>Block rooms with instant relocation suggestions</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <div className="w-5 h-5 rounded-full bg-sky-500/20 text-sky-400 flex items-center justify-center font-bold">✓</div>
              <span>Assigned physical block boundaries strictly enforced</span>
            </div>
          </div>
        </div>

        <div className="relative z-10 text-xs text-slate-400 flex items-center justify-between">
          <span>Smart Classroom System</span>
          <Link href="/staff/login" className="text-sky-400 hover:text-sky-300 underline font-medium">
            Staff Portal Chooser →
          </Link>
        </div>
      </div>

      {/* RIGHT WORKSPACE FORM */}
      <div className="flex-1 flex flex-col justify-between p-6 sm:p-10 lg:p-12 relative overflow-y-auto">
        <div className="flex items-center justify-between w-full max-w-md mx-auto">
          <Link
            href="/"
            className="text-xs font-semibold text-[var(--muted-foreground)] hover:text-[var(--foreground)] inline-flex items-center gap-1.5 transition-colors group"
          >
            <ArrowLeft className="w-3.5 h-3.5 transition-transform group-hover:-translate-x-1" />
            Back to Home
          </Link>
          <ThemeToggle />
        </div>

        <div className="w-full max-w-md mx-auto my-auto py-8">
          {/* Header */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-sky-100 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300">
                Coordinator Gateway
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--foreground)]">
              <BlurText text="Block Coordinator Sign In" />
            </h1>
            <p className="text-xs sm:text-sm text-[var(--muted-foreground)] mt-1.5">
              Sign in to manage room allocations for your assigned physical block.
            </p>
          </div>

          {/* Session Expired Banner */}
          {isExpired && (
            <div className="mb-6 p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-400 text-xs sm:text-sm flex items-start gap-3 animate-in fade-in slide-in-from-top-1">
              <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Session Expired</p>
                <p className="mt-0.5">Your session has expired, please log in again.</p>
              </div>
            </div>
          )}

          {/* Error Message */}
          {errorMsg && (
            <div className="mb-6 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs sm:text-sm flex items-start gap-3 animate-in fade-in slide-in-from-top-1">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Sign in failed</p>
                <p className="mt-0.5">{errorMsg}</p>
              </div>
            </div>
          )}

          {/* Form Card */}
          <div className="p-6 sm:p-8 rounded-3xl bg-[var(--card)] border border-[var(--border)] shadow-xl">
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--foreground)]">
                  Coordinator Email
                </label>
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] pointer-events-none">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      setErrorMsg(null);
                    }}
                    placeholder="coordinator@college.edu"
                    className="w-full h-11 pl-10 pr-4 rounded-xl border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-sky-500/40 focus:border-sky-500"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--foreground)]">
                    Password
                  </label>
                  <Link
                    href="/forgot-password?portal=coordinator"
                    className="text-xs font-semibold text-sky-600 dark:text-sky-400 hover:underline"
                  >
                    Forgot password?
                  </Link>
                </div>
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] pointer-events-none">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      setErrorMsg(null);
                    }}
                    placeholder="••••••••••••"
                    className="w-full h-11 pl-10 pr-11 rounded-xl border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-sky-500/40 focus:border-sky-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full h-11 px-6 rounded-xl font-semibold text-white bg-sky-600 hover:bg-sky-500 shadow-lg shadow-sky-500/25 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-[1.01] active:scale-[0.99]"
                >
                  {isLoading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Authenticating...</span>
                    </>
                  ) : (
                    <>
                      <span>Sign In to Coordinator Portal</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>

          <div className="mt-6 text-center text-xs text-[var(--muted-foreground)] space-y-1.5">
            <div>
              Looking for other portals?{" "}
              <Link href="/staff/login" className="font-semibold text-sky-600 dark:text-sky-400 hover:underline">
                View all login portals →
              </Link>
            </div>
          </div>
        </div>

        <div className="w-full max-w-md mx-auto text-center text-xs text-[var(--muted-foreground)] pt-4">
          Strictly restricted to designated block coordinators.
        </div>
      </div>
    </div>
  );
}

export default function CoordinatorLoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
          <div className="w-8 h-8 border-4 border-sky-500/30 border-t-sky-500 rounded-full animate-spin" />
        </div>
      }
    >
      <CoordinatorLoginContent />
    </Suspense>
  );
}

