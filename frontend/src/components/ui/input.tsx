import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  label?: string;
  helperText?: string;
  icon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = "text", error, label, helperText, icon, id, ...props }, ref) => {
    const generatedId = React.useId();
    const inputId = id || generatedId;

    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-xs font-semibold text-[var(--foreground)] uppercase tracking-wider"
          >
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {icon && (
            <div className="absolute left-3 text-[var(--muted-foreground)] pointer-events-none">
              {icon}
            </div>
          )}
          <input
            id={inputId}
            type={type}
            ref={ref}
            className={cn(
              "w-full h-10 px-3.5 rounded-xl border border-[var(--border)] bg-[var(--card)] text-[var(--foreground)] text-sm shadow-sm transition-all placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-sky-500/50 focus:border-sky-500 disabled:cursor-not-allowed disabled:opacity-50",
              icon ? "pl-9" : "",
              error
                ? "border-rose-500 focus:border-rose-500 focus:ring-rose-500/30"
                : "",
              className
            )}
            {...props}
          />
        </div>
        {error ? (
          <p className="text-xs text-rose-500 font-medium">{error}</p>
        ) : helperText ? (
          <p className="text-xs text-[var(--muted-foreground)]">{helperText}</p>
        ) : null}
      </div>
    );
  }
);
Input.displayName = "Input";

