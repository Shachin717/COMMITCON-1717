import * as React from "react";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

export interface StepItem {
  id: string | number;
  title: string;
  description?: string;
}

export interface StepperProps {
  steps: StepItem[];
  currentStep: number;
  onStepClick?: (stepIndex: number) => void;
  className?: string;
}

export function Stepper({
  steps,
  currentStep,
  onStepClick,
  className,
}: StepperProps) {
  return (
    <div className={cn("w-full py-4", className)}>
      <div className="flex items-center justify-between relative">
        {/* Background track line */}
        <div className="absolute left-6 right-6 top-1/2 -translate-y-1/2 h-0.5 bg-[var(--border)] -z-0" />

        {steps.map((step, idx) => {
          const isCompleted = idx < currentStep;
          const isCurrent = idx === currentStep;
          const isClickable = !!onStepClick;

          return (
            <div
              key={step.id}
              onClick={() => isClickable && onStepClick(idx)}
              className={cn(
                "flex flex-col items-center relative z-10 select-none",
                isClickable && "cursor-pointer"
              )}
            >
              <div
                className={cn(
                  "w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all duration-200 bg-[var(--card)]",
                  isCompleted
                    ? "bg-sky-600 border-sky-600 text-white shadow-md shadow-sky-500/20"
                    : isCurrent
                    ? "border-sky-500 text-sky-600 dark:text-sky-400 ring-4 ring-sky-500/20"
                    : "border-[var(--border)] text-[var(--muted-foreground)]"
                )}
              >
                {isCompleted ? <Check className="w-4 h-4 stroke-[3]" /> : idx + 1}
              </div>
              <div className="mt-2 text-center">
                <span
                  className={cn(
                    "text-xs font-semibold block",
                    isCurrent
                      ? "text-sky-600 dark:text-sky-400"
                      : isCompleted
                      ? "text-[var(--foreground)]"
                      : "text-[var(--muted-foreground)]"
                  )}
                >
                  {step.title}
                </span>
                {step.description && (
                  <span className="text-[10px] text-[var(--muted-foreground)] hidden sm:block">
                    {step.description}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

