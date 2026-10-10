import * as React from "react";
import { cn } from "@/lib/utils";

export type StatusType =
  | "success"
  | "warning"
  | "error"
  | "info"
  | "neutral"
  | "primary";

export interface StatusBadgeProps {
  status: StatusType | string;
  label?: string;
  size?: "sm" | "md";
  className?: string;
}

export function StatusBadge({
  status,
  label,
  size = "md",
  className,
}: StatusBadgeProps) {
  const normStatus = status.toLowerCase();

  let style = "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700";
  let dotColor = "bg-slate-400";

  if (
    normStatus === "success" ||
    normStatus === "active" ||
    normStatus === "approved" ||
    normStatus === "confirmed"
  ) {
    style =
      "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/60";
    dotColor = "bg-emerald-500";
  } else if (
    normStatus === "warning" ||
    normStatus === "pending" ||
    normStatus === "pending_hod" ||
    normStatus === "maintenance"
  ) {
    style =
      "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 border-amber-200 dark:border-amber-800/60";
    dotColor = "bg-amber-500 animate-pulse";
  } else if (
    normStatus === "error" ||
    normStatus === "rejected" ||
    normStatus === "cancelled" ||
    normStatus === "inactive"
  ) {
    style =
      "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400 border-rose-200 dark:border-rose-800/60";
    dotColor = "bg-rose-500";
  } else if (
    normStatus === "info" ||
    normStatus === "primary" ||
    normStatus === "coordinator_approved"
  ) {
    style =
      "bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-400 border-sky-200 dark:border-sky-800/60";
    dotColor = "bg-sky-500";
  }

  const sizes = {
    sm: "px-2 py-0.5 text-[11px] gap-1.5",
    md: "px-2.5 py-1 text-xs gap-2",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center font-medium rounded-full border transition-colors select-none",
        style,
        sizes[size],
        className
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full shrink-0", dotColor)} />
      {label || status}
    </span>
  );
}

