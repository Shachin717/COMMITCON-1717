"use client";

import React, { createContext, useContext, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from "lucide-react";

export type ToastType = "success" | "error" | "info" | "warning";

export interface Toast {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
}

interface ToastContextType {
  toasts: Toast[];
  toast: (options: {
    message: string;
    type?: ToastType;
    title?: string;
    duration?: number;
  }) => string;
  success: (message: string, title?: string) => string;
  error: (message: string, title?: string) => string;
  info: (message: string, title?: string) => string;
  warning: (message: string, title?: string) => string;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

function formatToastMessage(val: any): string {
  if (typeof val === "string") return val;
  if (val === null || val === undefined) return "";
  if (typeof val === "object") {
    try {
      if (typeof val.message === "string") return val.message;
      if (typeof val.detail === "string") return val.detail;
      return JSON.stringify(val);
    } catch {
      return String(val);
    }
  }
  return String(val);
}

// Standalone global trigger so toast can be called from non-React API clients
type ToastSubscriber = (t: Omit<Toast, "id">) => void;
const subscribers = new Set<ToastSubscriber>();

export function showToast(options: {
  message: any;
  type?: ToastType;
  title?: string;
  duration?: number;
}) {
  const safeMessage = formatToastMessage(options.message);
  subscribers.forEach((cb) =>
    cb({
      message: safeMessage,
      type: options.type || "info",
      title: options.title,
      duration: options.duration,
    })
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback(
    ({
      message,
      type = "info",
      title,
      duration = 4500,
    }: {
      message: any;
      type?: ToastType;
      title?: string;
      duration?: number;
    }) => {
      const id = Math.random().toString(36).substring(2, 9);
      const safeMessage = formatToastMessage(message);
      const newToast: Toast = { id, type, title, message: safeMessage, duration };

      setToasts((prev) => [...prev, newToast]);

      if (duration > 0) {
        setTimeout(() => {
          dismiss(id);
        }, duration);
      }

      return id;
    },
    [dismiss]
  );

  const success = useCallback(
    (message: string, title?: string) => toast({ message, title, type: "success" }),
    [toast]
  );
  const error = useCallback(
    (message: string, title?: string) => toast({ message, title, type: "error" }),
    [toast]
  );
  const info = useCallback(
    (message: string, title?: string) => toast({ message, title, type: "info" }),
    [toast]
  );
  const warning = useCallback(
    (message: string, title?: string) => toast({ message, title, type: "warning" }),
    [toast]
  );

  React.useEffect(() => {
    const handler: ToastSubscriber = (toastData) => {
      toast(toastData);
    };
    subscribers.add(handler);
    return () => {
      subscribers.delete(handler);
    };
  }, [toast]);

  return (
    <ToastContext.Provider
      value={{ toasts, toast, success, error, info, warning, dismiss }}
    >
      {children}
      {/* Toast viewport */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-md w-full pointer-events-none px-4 sm:px-0">
        <AnimatePresence mode="popLayout">
          {toasts.map((t) => {
            const icons = {
              success: <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />,
              error: <AlertCircle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />,
              warning: <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />,
              info: <Info className="w-5 h-5 text-sky-500 shrink-0 mt-0.5" />,
            };

            const borders = {
              success: "border-emerald-500/20 dark:border-emerald-500/30",
              error: "border-rose-500/20 dark:border-rose-500/30",
              warning: "border-amber-500/20 dark:border-amber-500/30",
              info: "border-sky-500/20 dark:border-sky-500/30",
            };

            return (
              <motion.div
                key={t.id}
                layout
                initial={{ opacity: 0, y: 20, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 15, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                className={`pointer-events-auto flex items-start gap-3 p-4 rounded-2xl bg-[var(--card)] text-[var(--foreground)] border ${borders[t.type]} shadow-xl shadow-black/5 dark:shadow-black/30 backdrop-blur-md`}
              >
                {icons[t.type]}
                <div className="flex-1 min-w-0">
                  {t.title && (
                    <h4 className="text-sm font-semibold tracking-tight mb-0.5">
                      {t.title}
                    </h4>
                  )}
                  <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
                    {t.message}
                  </p>
                </div>
                <button
                  onClick={() => dismiss(t.id)}
                  className="text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                  aria-label="Close notification"
                >
                  <X className="w-4 h-4" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}

