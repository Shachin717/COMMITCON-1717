"use client";

import React, { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { 
  Shield, 
  Lock, 
  Mail, 
  Eye, 
  EyeOff, 
  ArrowRight, 
  ArrowLeft,
  AlertCircle, 
  ShieldAlert, 
  KeyRound,
  Server
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

function AdminLoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const isExpired = searchParams.get("expired") === "1";
  const redirectQuery = searchParams.get("redirect");

  const [email, setEmail] = useState("admin@git.edu");
  const [password, setPassword] = useState("Admin@123");
  const [showPassword, setShowPassword] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMsg(null);

    try {
      const response = await apiClient<LoginResponse>("/api/auth/admin/login", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          password,
        }),
      });

      // Synchronize role cookie for client-side routing & middleware fast-path
      document.cookie = `user_role=ADMIN; path=/; max-age=86400`;

      if (response.user.must_change_password) {
        router.push(`/change-password?forced=1&redirect=${encodeURIComponent("/admin")}`);
        return;
      }

      const finalDestination =
        redirectQuery && redirectQuery.startsWith("/admin") && !redirectQuery.startsWith("/admin/login")
          ? redirectQuery
          : "/admin";
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
      {/* LEFT BRAND PANEL (Desktop) with Distinct Rose/Red Admin Accent */}
      <div className="hidden lg:flex lg:w-5/12 relative flex-col justify-between p-12 overflow-hidden border-r border-[var(--border)] bg-gradient-to-br from-rose-950 via-slate-900 to-red-950 text-white">
        <Aurora colorStops={["#e11d48", "#f43f5e", "#991b1b"]} className="opacity-50" />
        <Particles quantity={40} color="#fb7185" className="opacity-65" />

        <div className="relative z-10 flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-rose-600 shadow-lg shadow-rose-500/30 flex items-center justify-center text-white">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight text-white block">
              Smart Classroom
            </span>
            <span className="text-xs text-rose-200 font-medium">
              System Administration
            </span>
          </div>
        </div>

        <div className="relative z-10 space-y-4 my-auto max-w-md">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-rose-500/20 backdrop-blur-md border border-rose-400/30 text-xs font-semibold text-rose-200">
            <Server className="w-3.5 h-3.5" />
            <span>Root Administrator Gateway</span>
          </div>
          <h2 className="text-3xl font-extrabold tracking-tight text-white leading-tight">
            Institutional Control & Infrastructure Governance.
          </h2>
          <p className="text-sm text-slate-300 leading-relaxed">
            Centralized administration for room catalogs, block coordinator assignments, department approval toggles, and institutional scheduling policies.
          </p>

          <div className="pt-4 space-y-3">
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <div className="w-5 h-5 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center font-bold">✓</div>
              <span>Full control over rooms, facilities, and physical blocks</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <div className="w-5 h-5 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center font-bold">✓</div>
              <span>User management, account activation, and role assignments</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <div className="w-5 h-5 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center font-bold">✓</div>
              <span>Immutable security audit logging & utilization metrics</span>
            </div>
          </div>
        </div>

        <div className="relative z-10 text-xs text-slate-400 flex items-center justify-between">
          <span>Smart Classroom System</span>
          <Link href="/staff/login" className="text-rose-400 hover:text-rose-300 underline font-medium">
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
              <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300">
                Administrator Gateway
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--foreground)]">
              <BlurText text="Administrator Sign In" />
            </h1>
            <p className="text-xs sm:text-sm text-[var(--muted-foreground)] mt-1.5">
              Sign in with your campus administrative credentials.
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
                  Administrator Email
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
                    placeholder="admin@college.edu"
                    className="w-full h-11 pl-10 pr-4 rounded-xl border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-rose-500/40 focus:border-rose-500"
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--foreground)]">
                    Password
                  </label>
                  <Link
                    href="/forgot-password?portal=admin"
                    className="text-xs font-semibold text-rose-600 dark:text-rose-400 hover:underline"
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
                    className="w-full h-11 pl-10 pr-11 rounded-xl border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-rose-500/40 focus:border-rose-500"
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
                  className="w-full h-11 px-6 rounded-xl font-semibold text-white bg-rose-600 hover:bg-rose-500 shadow-lg shadow-rose-500/25 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed hover:scale-[1.01] active:scale-[0.99]"
                >
                  {isLoading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Authenticating...</span>
                    </>
                  ) : (
                    <>
                      <span>Sign In to Admin Portal</span>
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
              <Link href="/staff/login" className="font-semibold text-rose-600 dark:text-rose-400 hover:underline">
                View all login portals →
              </Link>
            </div>
          </div>
        </div>

        <div className="w-full max-w-md mx-auto text-center text-xs text-[var(--muted-foreground)] pt-4">
          Strictly restricted to authorized administrative personnel.
        </div>
      </div>
    </div>
  );
}

export default function AdminLoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
          <div className="w-8 h-8 border-4 border-rose-500/30 border-t-rose-500 rounded-full animate-spin" />
        </div>
      }
    >
      <AdminLoginContent />
    </Suspense>
  );
}

