"use client";

import React, { Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { 
  Building2, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle, 
  ArrowLeft, 
  Loader2, 
  ShieldCheck, 
  CalendarX 
} from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { apiClient, ApiError } from "@/lib/api-client";
import { Button } from "@/components/ui/button";

function CancelContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") || "";

  const [inputToken, setInputToken] = useState(token);
  const [reason, setReason] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    reference?: string;
    message?: string;
  } | null>(null);

  const activeToken = token || inputToken;

  const handleCancel = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeToken.trim()) return;

    setIsLoading(true);
    setResult(null);

    try {
      const data = await apiClient<{
        message: string;
        reference: string;
        status: string;
      }>("/api/public/bookings/cancel", {
        method: "POST",
        body: JSON.stringify({
          cancel_token: activeToken.trim(),
          reason: reason.trim() || undefined,
        }),
      });

      setResult({
        success: true,
        reference: data.reference,
        message: data.message || "Booking has been successfully cancelled and the room slot is freed.",
      });
    } catch (err: any) {
      setResult({
        success: false,
        message: err.message || "Failed to cancel booking. The link may be invalid or expired.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto">
      {result?.success ? (
        <div className="glass-card p-8 text-center space-y-6 border-emerald-500/30 bg-emerald-50/20 dark:bg-emerald-950/20">
          <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/50 text-emerald-600 dark:text-emerald-400 mx-auto flex items-center justify-center">
            <CheckCircle2 className="w-9 h-9" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--foreground)]">
              Booking Cancelled
            </h2>
            <p className="text-sm text-[var(--muted-foreground)] mt-2">
              {result.message}
            </p>
          </div>

          {result.reference && (
            <div className="p-4 rounded-xl bg-slate-100 dark:bg-slate-800 border border-[var(--border)] inline-block">
              <span className="text-xs uppercase tracking-wider text-[var(--muted-foreground)] font-semibold block mb-1">
                Booking Reference
              </span>
              <span className="font-mono text-lg font-bold text-sky-600 dark:text-sky-400">
                {result.reference}
              </span>
            </div>
          )}

          <div className="pt-2 flex flex-col sm:flex-row gap-3 justify-center">
            <Link href="/">
              <Button variant="primary">
                Return to Campus Portal
              </Button>
            </Link>
            <Link href="/#manage-section">
              <Button variant="outline">
                Check Booking Status
              </Button>
            </Link>
          </div>
        </div>
      ) : result?.success === false ? (
        <div className="glass-card p-8 text-center space-y-6 border-rose-500/30 bg-rose-50/20 dark:bg-rose-950/20">
          <div className="w-16 h-16 rounded-full bg-rose-100 dark:bg-rose-900/50 text-rose-600 dark:text-rose-400 mx-auto flex items-center justify-center">
            <XCircle className="w-9 h-9" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--foreground)]">
              Cancellation Error
            </h2>
            <p className="text-sm text-rose-600 dark:text-rose-400 mt-2">
              {result.message}
            </p>
          </div>

          <div className="pt-2 flex flex-col sm:flex-row gap-3 justify-center">
            <Button
              variant="outline"
              onClick={() => setResult(null)}
            >
              Try Again
            </Button>
            <Link href="/#manage-section">
              <Button variant="primary">
                Manage by Reference & Email
              </Button>
            </Link>
          </div>
        </div>
      ) : (
        <div className="glass-card p-8 border-[var(--border)] shadow-xl">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-3 rounded-xl bg-rose-500/10 text-rose-600 dark:text-rose-400">
              <CalendarX className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-[var(--foreground)]">
                Cancel Your Booking
              </h2>
              <p className="text-xs text-[var(--muted-foreground)]">
                This will release the room slot immediately and notify coordinators.
              </p>
            </div>
          </div>

          <form onSubmit={handleCancel} className="space-y-5">
            {!token && (
              <div>
                <label className="block text-xs font-semibold mb-1.5 text-[var(--foreground)]">
                  Cancellation Token
                </label>
                <input
                  type="text"
                  required
                  value={inputToken}
                  onChange={(e) => setInputToken(e.target.value)}
                  placeholder="Paste secure cancellation token from email"
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-rose-500"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold mb-1.5 text-[var(--foreground)]">
                Reason for Cancellation <span className="text-[var(--muted-foreground)] font-normal">(Optional)</span>
              </label>
              <textarea
                rows={3}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="e.g., Session postponed, faculty unavailable, emergency"
                className="w-full px-3.5 py-2.5 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-rose-500 resize-none"
              />
            </div>

            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>
                Cancelling will permanently release this room slot. Any waitlisted students will be automatically notified to claim this slot.
              </span>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <Link href="/" className="flex-1">
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  disabled={isLoading}
                >
                  <ArrowLeft className="w-4 h-4 mr-1.5" /> Back to Home
                </Button>
              </Link>
              <Button
                type="submit"
                variant="danger"
                className="flex-1"
                isLoading={isLoading}
                disabled={!activeToken.trim()}
              >
                Confirm Cancellation
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

export default function CancelPage() {
  return (
    <div className="min-h-screen bg-[var(--background)] relative overflow-hidden flex flex-col">
      <div className="absolute inset-0 bg-grid-pattern opacity-60 pointer-events-none" />
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-rose-500/15 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <header className="relative z-10 border-b border-[var(--border)] backdrop-blur-md bg-[var(--background)]/75">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-sky-500/25">
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-sky-600 to-indigo-600 dark:from-sky-400 dark:to-indigo-300 bg-clip-text text-transparent">
                Smart Classroom
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs uppercase tracking-wider px-2 py-0.5 rounded-full bg-sky-100 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 font-medium">
                Cancellation Portal
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-sm font-medium px-3.5 py-1.5 rounded-lg border border-[var(--border)] hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Back to Home
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="relative z-10 flex-1 flex items-center justify-center px-4 py-16 sm:px-6 lg:px-8">
        <Suspense fallback={<div className="text-center p-8"><Loader2 className="w-8 h-8 animate-spin mx-auto text-sky-600" /></div>}>
          <CancelContent />
        </Suspense>
      </main>
    </div>
  );
}

