import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "./button";
import { FolderOpen } from "lucide-react";

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center p-8 sm:p-12 rounded-2xl border border-dashed border-[var(--border)] bg-[var(--card)]/50",
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 dark:bg-slate-800 text-[var(--muted-foreground)] mb-4">
        {icon || <FolderOpen className="w-6 h-6" />}
      </div>
      <h3 className="text-base font-semibold text-[var(--foreground)] tracking-tight">
        {title}
      </h3>
      {description && (
        <p className="mt-1 text-sm text-[var(--muted-foreground)] max-w-sm">
          {description}
        </p>
      )}
      {action && (
        <Button
          size="sm"
          className="mt-5"
          onClick={action.onClick}
        >
          {action.label}
        </Button>
      )}
    </div>
  );
}

