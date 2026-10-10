"use client";

import React, { Suspense, useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { 
  Building2, 
  Mail, 
  Lock, 
  Eye, 
  EyeOff, 
  ArrowRight, 
  ArrowLeft,
  AlertCircle, 
  CheckCircle2, 
  Clock, 
  KeyRound,
  ShieldCheck,
  Check
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { Stepper, StepItem, OtpInput, PasswordStrengthMeter, evaluatePasswordStrength } from "@/components/ui";
import { Particles, Aurora, BlurText } from "@/components/reactbits";
import { ThemeToggle } from "@/components/theme-toggle";

const STEPS: StepItem[] = [
  { id: "email", title: "Email", description: "Account identity" },
  { id: "otp", title: "Verification", description: "6-digit code" },
  { id: "password", title: "New Password", description: "Secure access" },
];

function ForgotPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Get portal query param to redirect back cleanly (admin, coordinator, faculty, hod)
  const portalParam = searchParams.get("portal")?.toLowerCase();
  const portal =
    portalParam === "admin" || portalParam === "coordinator" || portalParam === "faculty" || portalParam === "hod"
      ? portalParam
      : undefined;
  const loginUrl = portal ? `/${portal}/login` : "/staff/login";
  const isHod = portal === "hod";

  // Step state (0: email, 1: otp, 2: new password)
  const [currentStep, setCurrentStep] = useState(0);

  // Form data
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  // Status & loading states
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [resendSeconds, setResendSeconds] = useState(60);
  const [isResending, setIsResending] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);

  // Cooldown countdown timer for step 1 (OTP)
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (currentStep === 1 && resendSeconds > 0) {
      timer = setInterval(() => {
        setResendSeconds((prev) => (prev > 0 ? prev - 1 : 0));
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [currentStep, resendSeconds]);

  // Step 1: Submit Email
  const handleRequestOtp = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!email || !email.includes("@")) {
      setErrorMsg("Please enter a valid email address.");
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      await apiClient("/api/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email: email.trim().toLowerCase(), portal }),
      });

      setSuccessMsg(`A 6-digit verification code has been dispatched to ${email}.`);
      setResendSeconds(60);
      setCurrentStep(1);
    } catch (err: any) {
      if (err.status === 429) {
        setErrorMsg("Please wait 60 seconds before requesting another code.");
      } else {
        setErrorMsg(err.message || "Failed to send reset code. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Resend OTP
  const handleResendOtp = async () => {
    if (resendSeconds > 0 || isResending) return;
    setIsResending(true);
    setErrorMsg(null);

    try {
      await apiClient("/api/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email: email.trim().toLowerCase(), portal }),
      });
      setSuccessMsg("A fresh 6-digit code has been sent to your email.");
      setResendSeconds(60);
    } catch (err: any) {
      setErrorMsg(err.message || "Could not resend code. Please try again shortly.");
    } finally {
      setIsResending(false);
    }
  };

  // Step 2: Verify OTP
  const handleVerifyOtp = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (otp.length !== 6) {
      setErrorMsg("Please enter the complete 6-digit verification code.");
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await apiClient<{ valid: boolean; message: string; reset_token: string }>(
        "/api/auth/verify-otp",
        {
          method: "POST",
          body: JSON.stringify({
            email: email.trim().toLowerCase(),
            otp: otp.trim(),
            portal,
          }),
        }
      );

      if (res.valid && res.reset_token) {
        setResetToken(res.reset_token);
        setSuccessMsg("Code verified! You can now choose a new secure password.");
        setCurrentStep(2);
      } else {
        setErrorMsg("Invalid verification code. Please check and try again.");
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Invalid or expired verification code.");
    } finally {
      setIsLoading(false);
    }
  };

  // Step 3: Set New Password
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (newPassword.length < 6) {
      setErrorMsg("Password must be at least 6 characters long.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setErrorMsg("Passwords do not match. Please verify both fields.");
      return;
    }

    const { score } = evaluatePasswordStrength(newPassword);
    if (score < 2) {
      setErrorMsg("Please choose a stronger password matching the security criteria.");
      return;
    }

    setIsLoading(true);

    try {
      await apiClient("/api/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          reset_token: resetToken,
          new_password: newPassword,
          portal,
        }),
      });

      setIsCompleted(true);
      setSuccessMsg("Your password has been successfully reset!");
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to reset password. The link or code may have expired.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex bg-[var(--background)] relative overflow-hidden">
      {/* LEFT BRAND PANEL (Desktop) */}
      <div className={`hidden lg:flex lg:w-5/12 relative flex-col justify-between p-12 overflow-hidden border-r border-[var(--border)] ${
        isHod
          ? "bg-gradient-to-br from-purple-950 via-slate-900 to-indigo-950 text-white"
          : "bg-gradient-to-br from-slate-950 via-sky-950 to-slate-900 text-white"
      }`}>
        <Aurora 
          colorStops={isHod ? ["#a855f7", "#ec4899", "#6366f1"] : ["#0284c7", "#38bdf8", "#818cf8"]} 
          className="opacity-45"
        />
        <Particles 
          quantity={35} 
          color={isHod ? "#c084fc" : "#7dd3fc"} 
          className="opacity-60"
        />

        <div className="relative z-10 flex items-center gap-3">
          <div className={`w-11 h-11 rounded-2xl flex items-center justify-center shadow-lg ${
            isHod ? "bg-purple-600 shadow-purple-500/30" : "bg-sky-600 shadow-sky-500/30"
          }`}>
            <Building2 className="w-6 h-6 text-white" />
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
            <span>Secure Password Recovery</span>
          </div>
          <h2 className="text-3xl font-extrabold tracking-tight text-white leading-tight">
            Regain Access in Three Simple Steps.
          </h2>
          <p className="text-sm text-slate-300 leading-relaxed">
            Verify your official campus email address via a one-time 6-digit security code and choose a new password.
          </p>

          <div className="pt-4 space-y-3">
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <div className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold">✓</div>
              <span>Immediate email delivery with 15-minute OTP lifespan</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <div className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold">✓</div>
              <span>Anti-enumeration generic validation protection</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <div className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold">✓</div>
              <span>Cryptographic reset tokens with single-use guarantee</span>
            </div>
          </div>
        </div>

        <div className="relative z-10 text-xs text-slate-400 flex items-center justify-between">
          <span>Smart Classroom System</span>
          <span>College IT Security</span>
        </div>
      </div>

      {/* RIGHT WORKSPACE FORM */}
      <div className="flex-1 flex flex-col justify-between p-6 sm:p-10 lg:p-12 relative overflow-y-auto">
        <div className="flex items-center justify-between w-full max-w-xl mx-auto">
          <Link
            href={loginUrl}
            className="text-xs font-semibold text-[var(--muted-foreground)] hover:text-[var(--foreground)] inline-flex items-center gap-1.5 transition-colors group"
          >
            <ArrowLeft className="w-3.5 h-3.5 transition-transform group-hover:-translate-x-1" />
            Back to {isHod ? "HOD Login" : "Staff Login"}
          </Link>
          <ThemeToggle />
        </div>

        <div className="w-full max-w-xl mx-auto my-auto py-8">
          {/* Header */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full ${
                isHod 
                  ? "bg-purple-100 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300" 
                  : "bg-sky-100 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300"
              }`}>
                {isHod ? "HOD Portal Recovery" : "Staff Portal Recovery"}
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--foreground)]">
              <BlurText text="Reset Your Password" />
            </h1>
            <p className="text-xs sm:text-sm text-[var(--muted-foreground)] mt-1.5">
              Follow the instructions below to verify your account and restore access.
            </p>
          </div>

          {/* 3-Step Stepper */}
          <div className="mb-8 p-4 rounded-2xl bg-[var(--card)] border border-[var(--border)] shadow-sm">
            <Stepper steps={STEPS} currentStep={isCompleted ? 3 : currentStep} />
          </div>

          {/* Feedback messages */}
          {errorMsg && (
            <div className="mb-6 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs sm:text-sm flex items-start gap-3 animate-in fade-in slide-in-from-top-1">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Notice</p>
                <p className="mt-0.5">{errorMsg}</p>
              </div>
            </div>
          )}

          {successMsg && !isCompleted && (
            <div className="mb-6 p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs sm:text-sm flex items-start gap-3 animate-in fade-in slide-in-from-top-1">
              <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Sent</p>
                <p className="mt-0.5">{successMsg}</p>
              </div>
            </div>
          )}

          {/* COMPLETED SUCCESS STATE */}
          {isCompleted ? (
            <div className="p-8 rounded-3xl bg-[var(--card)] border border-[var(--border)] shadow-xl text-center space-y-5 animate-in zoom-in-95">
              <div className="w-16 h-16 rounded-full bg-emerald-500/15 text-emerald-500 mx-auto flex items-center justify-center ring-8 ring-emerald-500/10">
                <Check className="w-8 h-8 stroke-[3]" />
              </div>
              <div className="space-y-2">
                <h2 className="text-xl font-bold text-[var(--foreground)]">
                  Password Reset Successfully!
                </h2>
                <p className="text-xs sm:text-sm text-[var(--muted-foreground)] max-w-sm mx-auto">
                  Your new credentials are now active. You can log in immediately to access your portal.
                </p>
              </div>

              <div className="pt-3">
                <button
                  type="button"
                  onClick={() => router.push(loginUrl)}
                  className={`w-full h-11 px-6 rounded-xl font-semibold text-white shadow-lg transition-all flex items-center justify-center gap-2 ${
                    isHod 
                      ? "bg-purple-600 hover:bg-purple-500 shadow-purple-500/25" 
                      : "bg-sky-600 hover:bg-sky-500 shadow-sky-500/25"
                  }`}
                >
                  Proceed to {isHod ? "HOD Login" : "Staff Login"}
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          ) : (
            <div className="p-6 sm:p-8 rounded-3xl bg-[var(--card)] border border-[var(--border)] shadow-xl">
              {/* STEP 0: EMAIL */}
              {currentStep === 0 && (
                <form onSubmit={handleRequestOtp} className="space-y-5">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--foreground)]">
                      Registered Email Address
                    </label>
                    <div className="relative">
                      <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] pointer-events-none">
                        <Mail className="w-4 h-4" />
                      </div>
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="e.g. name@college.edu"
                        className="w-full h-11 pl-10 pr-4 rounded-xl border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] text-sm shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-sky-500/40 focus:border-sky-500"
                        autoFocus
                      />
                    </div>
                    <p className="text-[11px] text-[var(--muted-foreground)]">
                      We will dispatch a 6-digit one-time code to verify your identity.
                    </p>
                  </div>

                  <button
                    type="submit"
                    disabled={isLoading}
                    className={`w-full h-11 px-6 rounded-xl font-semibold text-white shadow-lg transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                      isHod 
                        ? "bg-purple-600 hover:bg-purple-500 shadow-purple-500/25" 
                        : "bg-sky-600 hover:bg-sky-500 shadow-sky-500/25"
                    }`}
                  >
                    {isLoading ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        <span>Sending verification code...</span>
                      </>
                    ) : (
                      <>
                        <span>Continue</span>
                        <ArrowRight className="w-4 h-4" />
                      </>
                    )}
                  </button>
                </form>
              )}

              {/* STEP 1: OTP INPUT */}
              {currentStep === 1 && (
                <form onSubmit={handleVerifyOtp} className="space-y-6">
                  <div className="text-center space-y-1">
                    <span className="text-xs text-[var(--muted-foreground)]">
                      Enter the 6 digits sent to
                    </span>
                    <p className="text-sm font-bold text-[var(--foreground)] break-all">
                      {email}
                    </p>
                  </div>

                  {/* 6-digit OTP Box */}
                  <div className="py-2">
                    <OtpInput
                      value={otp}
                      onChange={(val) => {
                        setOtp(val);
                        setErrorMsg(null);
                      }}
                      error={!!errorMsg}
                      autoFocus
                    />
                  </div>

                  {/* Timer & Resend */}
                  <div className="flex items-center justify-between text-xs pt-1 px-1">
                    <div className="flex items-center gap-1.5 text-[var(--muted-foreground)]">
                      <Clock className="w-3.5 h-3.5" />
                      {resendSeconds > 0 ? (
                        <span>Resend in <strong className="text-[var(--foreground)]">{resendSeconds}s</strong></span>
                      ) : (
                        <span className="text-emerald-500 font-medium">Ready to resend</span>
                      )}
                    </div>

                    <button
                      type="button"
                      disabled={resendSeconds > 0 || isResending}
                      onClick={handleResendOtp}
                      className="text-xs font-semibold text-sky-600 dark:text-sky-400 hover:underline disabled:opacity-40 disabled:no-underline disabled:cursor-not-allowed transition-opacity"
                    >
                      {isResending ? "Sending..." : "Resend Code"}
                    </button>
                  </div>

                  <div className="flex flex-col sm:flex-row gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => {
                        setCurrentStep(0);
                        setErrorMsg(null);
                      }}
                      className="h-11 px-5 rounded-xl border border-[var(--border)] font-semibold text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)] transition-colors"
                    >
                      Change Email
                    </button>

                    <button
                      type="submit"
                      disabled={isLoading || otp.length !== 6}
                      className={`flex-1 h-11 px-6 rounded-xl font-semibold text-white shadow-lg transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                        isHod 
                          ? "bg-purple-600 hover:bg-purple-500 shadow-purple-500/25" 
                          : "bg-sky-600 hover:bg-sky-500 shadow-sky-500/25"
                      }`}
                    >
                      {isLoading ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          <span>Verifying code...</span>
                        </>
                      ) : (
                        <>
                          <span>Verify & Proceed</span>
                          <ArrowRight className="w-4 h-4" />
                        </>
                      )}
                    </button>
                  </div>
                </form>
              )}

              {/* STEP 2: NEW PASSWORD */}
              {currentStep === 2 && (
                <form onSubmit={handleResetPassword} className="space-y-5">
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

                  {/* Password Strength Meter */}
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
                    className={`w-full h-11 px-6 rounded-xl font-semibold text-white shadow-lg transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                      isHod 
                        ? "bg-purple-600 hover:bg-purple-500 shadow-purple-500/25" 
                        : "bg-sky-600 hover:bg-sky-500 shadow-sky-500/25"
                    }`}
                  >
                    {isLoading ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        <span>Updating password...</span>
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="w-4 h-4" />
                        <span>Save New Password</span>
                      </>
                    )}
                  </button>
                </form>
              )}
            </div>
          )}
        </div>

        <div className="w-full max-w-xl mx-auto text-center text-xs text-[var(--muted-foreground)] pt-4">
          Need administrator assistance? Contact{" "}
          <span className="font-semibold text-[var(--foreground)]">admin@college.edu</span>
        </div>
      </div>
    </div>
  );
}

export default function ForgotPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
          <div className="w-8 h-8 border-4 border-sky-500/30 border-t-sky-500 rounded-full animate-spin" />
        </div>
      }
    >
      <ForgotPasswordContent />
    </Suspense>
  );
}

