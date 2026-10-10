"use client";

import * as React from "react";
import { Modal } from "./modal";
import { Button } from "./button";
import { AlertTriangle, AlertCircle, Info } from "lucide-react";

export interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: "danger" | "warning" | "info";
  isLoading?: boolean;
}

export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = "Confirm",
  cancelText = "Cancel",
  variant = "danger",
  isLoading = false,
}: ConfirmDialogProps) {
  const icons = {
    danger: (
      <div className="p-3 rounded-2xl bg-rose-500/10 text-rose-500 mb-3 w-fit">
        <AlertCircle className="w-6 h-6" />
      </div>
    ),
    warning: (
      <div className="p-3 rounded-2xl bg-amber-500/10 text-amber-500 mb-3 w-fit">
        <AlertTriangle className="w-6 h-6" />
      </div>
    ),
    info: (
      <div className="p-3 rounded-2xl bg-sky-500/10 text-sky-500 mb-3 w-fit">
        <Info className="w-6 h-6" />
      </div>
    ),
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} maxWidth="sm">
      <div className="flex flex-col items-center text-center">
        {icons[variant]}
        <h3 className="text-base font-bold text-[var(--foreground)] mb-1">
          {title}
        </h3>
        <p className="text-sm text-[var(--muted-foreground)] mb-6 leading-relaxed">
          {message}
        </p>
        <div className="flex w-full items-center gap-3">
          <Button
            variant="outline"
            className="flex-1"
            onClick={onClose}
            disabled={isLoading}
          >
            {cancelText}
          </Button>
          <Button
            variant={variant === "danger" ? "danger" : "primary"}
            className="flex-1"
            onClick={onConfirm}
            isLoading={isLoading}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

