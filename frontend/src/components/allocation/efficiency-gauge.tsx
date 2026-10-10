"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { TrendingUp, ArrowUpRight } from "lucide-react";

interface EfficiencyGaugeProps {
  baselineScore: number;
  optimizedScore: number;
  delta: number;
  className?: string;
}

export function EfficiencyGauge({
  baselineScore,
  optimizedScore,
  delta,
  className = "",
}: EfficiencyGaugeProps) {
  // Clamped 0 - 100
  const safeBase = Math.min(100, Math.max(0, baselineScore));
  const safeOpt = Math.min(100, Math.max(0, optimizedScore));

  // Circular gauge geometry
  const radius = 64;
  const strokeWidth = 10;
  const circumference = 2 * Math.PI * radius;
  // Semi-circle arc: half circumference
  const arcLength = Math.PI * radius;

  const baseOffset = arcLength - (safeBase / 100) * arcLength;
  const optOffset = arcLength - (safeOpt / 100) * arcLength;

  // Color selection
  const getScoreColor = (val: number) => {
    if (val >= 75) return "#10b981"; // emerald-500
    if (val >= 50) return "#0284c7"; // sky-600
    if (val >= 35) return "#f59e0b"; // amber-500
    return "#ef4444"; // red-500
  };

  const optColor = getScoreColor(safeOpt);
  const baseColor = "#94a3b8"; // slate-400

  return (
    <div className={`flex flex-col items-center ${className}`}>
      {/* SVG Arc Gauge */}
      <div className="relative w-48 h-28 flex items-center justify-center">
        <svg viewBox="0 0 160 95" className="w-full h-full overflow-visible">
          <defs>
            <linearGradient id="optGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#0ea5e9" />
              <stop offset="100%" stopColor="#10b981" />
            </linearGradient>
            <linearGradient id="bgGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.08" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0.12" />
            </linearGradient>
          </defs>

          {/* Background Track Arc */}
          <path
            d="M 16 80 A 64 64 0 0 1 144 80"
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            className="text-slate-200 dark:text-slate-800"
          />

          {/* Baseline Score Arc (dashed or muted) */}
          <motion.path
            d="M 16 80 A 64 64 0 0 1 144 80"
            fill="none"
            stroke={baseColor}
            strokeWidth={strokeWidth - 4}
            strokeDasharray={arcLength}
            strokeLinecap="round"
            initial={{ strokeDashoffset: arcLength }}
            animate={{ strokeDashoffset: baseOffset }}
            transition={{ duration: 1, ease: "easeOut" }}
            strokeOpacity="0.6"
          />

          {/* Optimized Score Arc (vibrant gradient) */}
          <motion.path
            d="M 16 80 A 64 64 0 0 1 144 80"
            fill="none"
            stroke="url(#optGradient)"
            strokeWidth={strokeWidth}
            strokeDasharray={arcLength}
            strokeLinecap="round"
            initial={{ strokeDashoffset: arcLength }}
            animate={{ strokeDashoffset: optOffset }}
            transition={{ duration: 1.4, ease: "easeOut" }}
          />
        </svg>

        {/* Center Value */}
        <div className="absolute bottom-1 flex flex-col items-center">
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="text-3xl font-extrabold tracking-tight text-[var(--foreground)]"
          >
            {safeOpt.toFixed(1)}
            <span className="text-xs font-semibold text-[var(--muted-foreground)] ml-0.5">/100</span>
          </motion.div>
          <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 -mt-0.5">
            Optimized Score
          </span>
        </div>
      </div>

      {/* Side-by-side pill comparison */}
      <div className="w-full mt-2 grid grid-cols-2 gap-2 text-center">
        <div className="p-2 rounded-xl bg-slate-500/5 border border-[var(--border)]">
          <span className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)] font-semibold block">
            Baseline
          </span>
          <span className="text-sm font-bold text-slate-600 dark:text-slate-400">
            {safeBase.toFixed(1)}
          </span>
        </div>
        <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
          <span className="text-[10px] uppercase tracking-wider text-emerald-600 dark:text-emerald-400 font-semibold block">
            Optimized
          </span>
          <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
            {safeOpt.toFixed(1)}
          </span>
        </div>
      </div>

      {/* Delta Badge */}
      <div className="mt-2 inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
        <ArrowUpRight className="w-3.5 h-3.5" />
        <span>+{delta > 0 ? delta.toFixed(1) : "0.0"} pts Improvement</span>
      </div>
    </div>
  );
}

