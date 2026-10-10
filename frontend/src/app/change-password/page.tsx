"use client";

import React, { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { 
  Building2, 
  Lock, 
  Eye, 
  EyeOff, 
  ShieldCheck, 
  AlertCircle,
  KeyRound
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { PasswordStrengthMeter, evaluatePasswordStrength } from "@/components/ui";
import { Aurora, Particles, BlurText } from "@/components/reactbits";
import { ThemeToggle } from "@/components/theme-toggle";

function ChangePasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const isTemporary = searchParams.get("forced") === "1";
  const redirectTarget = searchParams.get("redirect") || "/";

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!isTemporary && !currentPassword) {
      setErrorMsg("Please enter your current password.");
      return;
    }

    if (newPassword.length < 6) {
      setErrorMsg("New password must be at least 6 characters long.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMsg("New passwords do not match.");
      return;
    }

    const { score } = evaluatePasswordStrength(newPassword);
    if (score < 2) {
      setErrorMsg("Please choose a stronger password matching the security criteria.");
      return;
    }

    setIsLoading(true);

    try {
      await apiClient("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          old_password: currentPassword || undefined,
          new_password: newPassword,
        }),
      });

      // Clear user_role cookie and force re-login or route to target
      router.push(redirectTarget);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to update password. Please check your credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex bg-[var(--background)] relative overflow-hidden">
      {/* LEFT BRAND PANEL */}
      <div className="hidden lg:flex lg:w-5/12 relative flex-col justify-between p-12 overflow-hidden border-r border-[var(--border)] bg-gradient-to-br from-slate-950 via-sky-950 to-slate-900 text-white">
        <Aurora colorStops={["#0284c7", "#38bdf8", "#818cf8"]} className="opacity-45" />
        <Particles quantity={35} color="#7dd3fc" className="opacity-60" />

        <div className="relative z-10 flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-sky-600 shadow-lg shadow-sky-500/30 flex items-center justify-center text-white">
            <Building2 className="w-6 h-6" />
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight text-white block">
              Smart Classroom
            </span>
            <span className="text-xs text-slate-300 font-medium">
              Campus Allocation System
            </span>
          </div>
        </div>

        <div className="relative z-10 space-y-4 my-auto max-w-md">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md border border-white/10 text-xs font-medium text-slate-200">
            <KeyRound className="w-3.5 h-3.5" />
            <span>Mandatory Security Update</span>
          </div>
          <h2 className="text-3xl font-extrabold tracking-tight text-white leading-tight">
            Protect Your Account With a New Password.
          </h2>
          <p className="text-sm text-slate-300 leading-relaxed">
            {isTemporary
              ? "Your account was provisioned with a temporary password. For campus security compliance, please set a new personal password before proceeding."
              : "Update your existing account password with our enhanced password security requirements."}
          </p>
        </div>

        <div className="relative z-10 text-xs text-slate-400 flex items-center justify-between">
          <span>Smart Classroom System</span>
          <span>College IT Security</span>
        </div>
      </div>

      {/* RIGHT WORKSPACE FORM */}
      <div className="flex-1 flex flex-col justify-between p-6 sm:p-10 lg:p-12 relative overflow-y-auto">
        <div className="flex items-center justify-end w-full max-w-xl mx-auto">
          <ThemeToggle />
        </div>

        <div className="w-full max-w-xl mx-auto my-auto py-8">
          <div className="mb-6">
            <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300">
              {isTemporary ? "Action Required" : "Account Security"}
            </span>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--foreground)] mt-2">
              <BlurText text={isTemporary ? "Set Permanent Password" : "Change Password"} />
            </h1>
            <p className="text-xs sm:text-sm text-[var(--muted-foreground)] mt-1.5">
              {isTemporary
                ? "Enter your temporary password followed by your chosen permanent password."
                : "Choose a strong, unique password to secure your institutional portal."}
            </p>
          </div>

          {errorMsg && (
            <div className="mb-6 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs sm:text-sm flex items-start gap-3">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Notice</p>
                <p className="mt-0.5">{errorMsg}</p>
              </div>
            </div>
          )}

          <div className="p-6 sm:p-8 rounded-3xl bg-[var(--card)] border border-[var(--border)] shadow-xl">
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--foreground)]">
                  {isTemporary ? "Temporary Password" : "Current Password"}
                </label>
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] pointer-events-none">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full h-11 pl-10 pr-11 rounded-xl border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-sky-500/40 focus:border-sky-500"
                    autoFocus
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

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--foreground)]">
                  New Password
                </label>
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] pointer-events-none">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full h-11 pl-10 pr-4 rounded-xl border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-sky-500/40 focus:border-sky-500"
                  />
                </div>
              </div>

              {/* Strength Meter */}
              <PasswordStrengthMeter password={newPassword} />

              <div className="space-y-1.5 pt-1">
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--foreground)]">
                  Confirm New Password
                </label>
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] pointer-events-none">
                    <Lock className="w-4 h-4" />
                  </div>
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full h-11 pl-10 pr-4 rounded-xl border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-sky-500/40 focus:border-sky-500"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isLoading || !newPassword || !confirmPassword}
                className="w-full h-11 px-6 rounded-xl font-semibold text-white bg-sky-600 hover:bg-sky-500 shadow-lg shadow-sky-500/25 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Updating password...</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-4 h-4" />
                    <span>Save Password & Continue</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        <div className="w-full max-w-xl mx-auto text-center text-xs text-[var(--muted-foreground)] pt-4">
          Need administrator assistance? Contact{" "}
          <span className="font-semibold text-[var(--foreground)]">admin@college.edu</span>
        </div>
      </div>
    </div>
  );
}

export default function ChangePasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
          <div className="w-8 h-8 border-4 border-sky-500/30 border-t-sky-500 rounded-full animate-spin" />
        </div>
      }
    >
      <ChangePasswordContent />
    </Suspense>
  );
}

