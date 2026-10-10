"use client";

import * as React from "react";
import { Info } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface InfoTooltipProps {
  content: React.ReactNode;
  title?: string;
  className?: string;
}

export function InfoTooltip({ content, title, className = "" }: InfoTooltipProps) {
  const [open, setOpen] = React.useState(false);

  return (
    <div
      className={`relative inline-flex items-center ${className}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <button
        type="button"
        className="text-[var(--muted-foreground)] hover:text-sky-500 transition-colors p-0.5 rounded-full focus:outline-none focus:ring-1 focus:ring-sky-500"
        aria-label="Information"
      >
        <Info className="w-3.5 h-3.5" />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 z-50 w-64 max-w-xs p-3 rounded-xl bg-slate-900/95 dark:bg-slate-800/95 text-white text-xs shadow-xl backdrop-blur-md border border-slate-700 pointer-events-none"
          >
            {title && (
              <div className="font-semibold text-sky-400 mb-1 flex items-center gap-1.5">
                <Info className="w-3 h-3 shrink-0" />
                <span>{title}</span>
              </div>
            )}
            <div className="text-slate-300 leading-relaxed text-[11px] font-normal">
              {content}
            </div>
            {/* Arrow pointer */}
            <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-slate-900 dark:border-t-slate-800" />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

