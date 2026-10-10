"use client";

import React, { Suspense } from "react";
import Link from "next/link";
import { 
  Building2, 
  Shield, 
  GraduationCap, 
  Boxes, 
  ArrowRight, 
  ArrowLeft,
  Sparkles,
  ChevronRight
} from "lucide-react";
import { Aurora, Particles, BlurText } from "@/components/reactbits";
import { ThemeToggle } from "@/components/theme-toggle";

export default function StaffPortalChooserPage() {
  return (
    <div className="min-h-screen w-full flex flex-col justify-between bg-[var(--background)] relative overflow-hidden p-6 sm:p-12">
      <Aurora colorStops={["#0284c7", "#8b5cf6", "#f43f5e"]} className="opacity-30" />
      <Particles quantity={35} color="#94a3b8" className="opacity-40" />

      {/* TOP BAR */}
      <header className="relative z-10 w-full max-w-5xl mx-auto flex items-center justify-between">
        <Link
          href="/"
          className="text-xs font-semibold text-[var(--muted-foreground)] hover:text-[var(--foreground)] inline-flex items-center gap-1.5 transition-colors group"
        >
          <ArrowLeft className="w-3.5 h-3.5 transition-transform group-hover:-translate-x-1" />
          Back to Home
        </Link>
        <ThemeToggle />
      </header>

      {/* MAIN CONTENT */}
      <main className="relative z-10 w-full max-w-5xl mx-auto my-auto py-12">
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/20 text-xs font-semibold text-sky-600 dark:text-sky-400 mb-3">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Role-Isolated Portals</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[var(--foreground)]">
            <BlurText text="Choose Your Staff Portal" />
          </h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-2">
            Each role maintains dedicated access controls and isolated workflows. Select your portal below to sign in.
          </p>
        </div>

        {/* 3 STAFF CARDS */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* 1. ADMIN */}
          <Link
            href="/admin/login"
            className="group relative flex flex-col justify-between p-6 sm:p-8 rounded-3xl bg-[var(--card)] border border-[var(--border)] hover:border-rose-500/50 shadow-lg hover:shadow-xl hover:shadow-rose-500/10 transition-all hover:-translate-y-1"
          >
            <div>
              <div className="w-12 h-12 rounded-2xl bg-rose-500/10 text-rose-600 dark:text-rose-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Shield className="w-6 h-6" />
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-rose-600 dark:text-rose-400">
                Institutional Control
              </span>
              <h3 className="text-xl font-bold text-[var(--foreground)] mt-1 mb-2">
                System Admin
              </h3>
              <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                Room catalogs, department policies, user accounts, block assignments, and immutable audit logs.
              </p>
            </div>
            <div className="pt-6 flex items-center gap-2 text-xs font-semibold text-rose-600 dark:text-rose-400 group-hover:gap-3 transition-all">
              <span>Sign in as Admin</span>
              <ArrowRight className="w-4 h-4" />
            </div>
          </Link>

          {/* 2. COORDINATOR */}
          <Link
            href="/coordinator/login"
            className="group relative flex flex-col justify-between p-6 sm:p-8 rounded-3xl bg-[var(--card)] border border-[var(--border)] hover:border-sky-500/50 shadow-lg hover:shadow-xl hover:shadow-sky-500/10 transition-all hover:-translate-y-1"
          >
            <div>
              <div className="w-12 h-12 rounded-2xl bg-sky-500/10 text-sky-600 dark:text-sky-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <Building2 className="w-6 h-6" />
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-sky-600 dark:text-sky-400">
                Building Wings
              </span>
              <h3 className="text-xl font-bold text-[var(--foreground)] mt-1 mb-2">
                Block Coordinator
              </h3>
              <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                Review and approve student requests, block rooms for maintenance or exams, and manage wing logistics.
              </p>
            </div>
            <div className="pt-6 flex items-center gap-2 text-xs font-semibold text-sky-600 dark:text-sky-400 group-hover:gap-3 transition-all">
              <span>Sign in as Coordinator</span>
              <ArrowRight className="w-4 h-4" />
            </div>
          </Link>

          {/* 3. FACULTY */}
          <Link
            href="/faculty/login"
            className="group relative flex flex-col justify-between p-6 sm:p-8 rounded-3xl bg-[var(--card)] border border-[var(--border)] hover:border-emerald-500/50 shadow-lg hover:shadow-xl hover:shadow-emerald-500/10 transition-all hover:-translate-y-1"
          >
            <div>
              <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <GraduationCap className="w-6 h-6" />
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                Academics & Lectures
              </span>
              <h3 className="text-xl font-bold text-[var(--foreground)] mt-1 mb-2">
                Academic Faculty
              </h3>
              <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                Check real-time room availability, book halls for lectures and seminars, and track academic bookings.
              </p>
            </div>
            <div className="pt-6 flex items-center gap-2 text-xs font-semibold text-emerald-600 dark:text-emerald-400 group-hover:gap-3 transition-all">
              <span>Sign in as Faculty</span>
              <ArrowRight className="w-4 h-4" />
            </div>
          </Link>
        </div>

        {/* HOD SEPARATE CARD */}
        <div className="mt-8 p-6 rounded-3xl bg-[var(--card)] border border-[var(--border)] shadow-md flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-11 h-11 rounded-2xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center shrink-0">
              <Boxes className="w-6 h-6" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-[var(--foreground)]">
                Department Head (HOD) Portal
              </h4>
              <p className="text-xs text-[var(--muted-foreground)]">
                Dedicated authorization gateway for specialized departmental laboratories and exam hall approvals.
              </p>
            </div>
          </div>
          <Link
            href="/hod/login"
            className="shrink-0 px-4 py-2 rounded-xl text-xs font-semibold text-white bg-purple-600 hover:bg-purple-500 shadow-md shadow-purple-500/20 inline-flex items-center gap-2 transition-all hover:scale-[1.02]"
          >
            <span>Access HOD Portal</span>
            <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
      </main>

      {/* FOOTER */}
      <footer className="relative z-10 w-full max-w-5xl mx-auto text-center text-xs text-[var(--muted-foreground)] pt-6">
        Smart Classroom Allocation System • Strict Role Isolation Enforced
      </footer>
    </div>
  );
}
