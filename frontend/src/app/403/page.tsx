"use client";

import React from "react";
import Link from "next/link";
import { ShieldAlert, ArrowLeft, Home, LogOut } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { apiClient } from "@/lib/api-client";

export default function Forbidden403Page() {
  const handleLogout = async () => {
    try {
      await apiClient("/api/auth/logout", { method: "POST" });
    } catch {
      // ignore
    }
    document.cookie = "access_token=; path=/; max-age=0";
    document.cookie = "refresh_token=; path=/; max-age=0";
    document.cookie = "user_role=; path=/; max-age=0";
    window.location.href = "/staff/login";
  };

  return (
    <div className="min-h-screen w-full flex flex-col justify-between bg-[var(--background)] p-6 sm:p-12 relative overflow-hidden">
      <header className="w-full max-w-3xl mx-auto flex items-center justify-between">
        <Link
          href="/"
          className="text-xs font-semibold text-[var(--muted-foreground)] hover:text-[var(--foreground)] inline-flex items-center gap-1.5 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Home
        </Link>
        <ThemeToggle />
      </header>

      <main className="w-full max-w-md mx-auto my-auto text-center py-12">
        <div className="w-16 h-16 rounded-3xl bg-rose-500/10 text-rose-600 dark:text-rose-400 flex items-center justify-center mx-auto mb-6 shadow-xl shadow-rose-500/10">
          <ShieldAlert className="w-8 h-8" />
        </div>

        <span className="text-xs font-bold uppercase tracking-widest text-rose-600 dark:text-rose-400">
          Error 403 • Forbidden
        </span>
        <h1 className="text-3xl font-extrabold tracking-tight text-[var(--foreground)] mt-2 mb-3">
          Access Restricted
        </h1>
        <p className="text-sm text-[var(--muted-foreground)] leading-relaxed mb-8">
          You don&apos;t have access to that area. Each portal is strictly isolated to its designated campus role.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            href="/"
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl font-semibold text-xs text-white bg-slate-900 dark:bg-slate-100 dark:text-slate-900 shadow-md transition-all hover:scale-[1.02] flex items-center justify-center gap-2"
          >
            <Home className="w-3.5 h-3.5" />
            <span>Return to Home</span>
          </Link>
          <button
            onClick={handleLogout}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl font-semibold text-xs border border-[var(--border)] text-[var(--foreground)] hover:bg-[var(--muted)] transition-all flex items-center justify-center gap-2"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Switch Account</span>
          </button>
        </div>
      </main>

      <footer className="w-full max-w-3xl mx-auto text-center text-xs text-[var(--muted-foreground)]">
        Smart Classroom Allocation System • Role Enforcement Security Boundary
      </footer>
    </div>
  );
}

