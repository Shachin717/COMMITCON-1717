"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface PasswordStrengthMeterProps {
  password: string;
  className?: string;
}

export function evaluatePasswordStrength(password: string): {
  score: number;
  label: string;
  color: string;
  requirements: { label: string; met: boolean }[];
} {
  const reqs = [
    { label: "At least 8 characters", met: password.length >= 8 },
    { label: "Contains uppercase letter", met: /[A-Z]/.test(password) },
    { label: "Contains lowercase letter", met: /[a-z]/.test(password) },
    { label: "Contains number", met: /[0-9]/.test(password) },
    { label: "Contains special character", met: /[^A-Za-z0-9]/.test(password) },
  ];

  const metCount = reqs.filter((r) => r.met).length;
  let score = 0;
  let label = "Very Weak";
  let color = "bg-rose-500";

  if (password.length === 0) {
    score = 0;
    label = "Enter a password";
    color = "bg-slate-300 dark:bg-slate-700";
  } else if (metCount <= 2 || password.length < 6) {
    score = 1;
    label = "Weak";
    color = "bg-rose-500";
  } else if (metCount === 3) {
    score = 2;
    label = "Fair";
    color = "bg-amber-500";
  } else if (metCount === 4) {
    score = 3;
    label = "Good";
    color = "bg-sky-500";
  } else {
    score = 4;
    label = "Strong";
    color = "bg-emerald-500";
  }

  return { score, label, color, requirements: reqs };
}

export const PasswordStrengthMeter: React.FC<PasswordStrengthMeterProps> = ({
  password,
  className,
}) => {
  const { score, label, color, requirements } = evaluatePasswordStrength(password);

  return (
    <div className={cn("space-y-2.5", className)}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-[var(--muted-foreground)]">Password strength</span>
        <span
          className={cn(
            "font-semibold",
            score <= 1
              ? "text-rose-500"
              : score === 2
              ? "text-amber-500"
              : score === 3
              ? "text-sky-500"
              : "text-emerald-500"
          )}
        >
          {label}
        </span>
      </div>

      <div className="grid grid-cols-4 gap-1.5 h-1.5 w-full">
        {[1, 2, 3, 4].map((step) => (
          <div
            key={step}
            className={cn(
              "h-full rounded-full transition-all duration-300",
              score >= step ? color : "bg-slate-200 dark:bg-slate-800"
            )}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 pt-1 text-[11px]">
        {requirements.map((req, i) => (
          <div
            key={i}
            className={cn(
              "flex items-center gap-1.5 transition-colors",
              req.met
                ? "text-emerald-600 dark:text-emerald-400 font-medium"
                : "text-[var(--muted-foreground)]"
            )}
          >
            <span
              className={cn(
                "w-1.5 h-1.5 rounded-full",
                req.met ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-700"
              )}
            />
            {req.label}
          </div>
        ))}
      </div>
    </div>
  );
};

