"use client";

import React, { useState } from "react";
import { z } from "zod";
import { Clock, UserCheck, Bell, ShieldCheck, CheckCircle2 } from "lucide-react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { showToast } from "@/components/ui/toast";

const waitlistSchema = z.object({
  name: z.string().trim().min(2, "Name must be at least 2 characters"),
  email: z.string().trim().email("Please enter a valid college email"),
  phone: z.string().trim().min(7, "Enter a valid phone number"),
  roll_no: z.string().trim().optional(),
  department_id: z.number().optional(),
  class_name: z.string().trim().optional(),
});

interface WaitlistModalProps {
  isOpen: boolean;
  onClose: () => void;
  room: any | null;
  date: string;
  slot: any | null;
  departments: Array<{ id: number; name: string; code: string }>;
}

export function WaitlistModal({
  isOpen,
  onClose,
  room,
  date,
  slot,
  departments,
}: WaitlistModalProps) {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    roll_no: "",
    department_id: departments[0]?.id || 1,
    class_name: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!room || !slot || !date) return;

    const parse = waitlistSchema.safeParse(formData);
    if (!parse.success) {
      const errMap: Record<string, string> = {};
      parse.error.issues.forEach((err: any) => {
        if (err.path[0]) errMap[err.path[0] as string] = err.message;
      });
      setErrors(errMap);
      return;
    }
    setErrors({});

    setIsLoading(true);
    try {
      await apiClient("/api/public/waitlist", {
        method: "POST",
        body: JSON.stringify({
          room_id: room.id,
          date,
          slot_id: slot.id,
          name: formData.name,
          email: formData.email,
          phone: formData.phone,
          roll_no: formData.roll_no || undefined,
          department_id: formData.department_id || undefined,
          class_name: formData.class_name || undefined,
        }),
      });

      setIsSuccess(true);
      showToast({
        title: "Added to Waitlist",
        message: "You will receive an automatic email if this slot is freed.",
        type: "success",
      });
    } catch (err: any) {
      showToast({
        title: "Waitlist Failed",
        message: err.message || "Failed to join waitlist.",
        type: "error",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    setIsSuccess(false);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={isSuccess ? "" : "Join Room Slot Waitlist"}
      description={isSuccess ? "" : "Get notified immediately if a booking is cancelled."}
      maxWidth="md"
    >
      {isSuccess ? (
        <div className="text-center py-6 space-y-4">
          <div className="w-14 h-14 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 mx-auto flex items-center justify-center">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-[var(--foreground)]">
              You're on the Waitlist!
            </h3>
            <p className="text-xs text-[var(--muted-foreground)] mt-1 max-w-sm mx-auto">
              If {room?.name || "this room"} becomes available on {date} during slot {slot?.label || ""}, you will receive an automatic notification email with booking priority.
            </p>
          </div>
          <div className="pt-2">
            <Button variant="primary" onClick={handleClose}>
              Close
            </Button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          {room && slot && (
            <div className="p-3 rounded-xl bg-slate-100 dark:bg-slate-800/60 border border-[var(--border)] text-xs">
              <span className="font-semibold text-[var(--foreground)]">
                {room.name} ({room.block_name})
              </span>
              <div className="text-[var(--muted-foreground)] mt-0.5">
                Date: {date} • Slot: {slot.label}
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
                Full Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Student Name"
                className="w-full px-3 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              {errors.name && <p className="text-[11px] text-rose-500 mt-1">{errors.name}</p>}
            </div>

            <div>
              <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
                College Email <span className="text-rose-500">*</span>
              </label>
              <input
                type="email"
                required
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="student@college.edu"
                className="w-full px-3 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              {errors.email && <p className="text-[11px] text-rose-500 mt-1">{errors.email}</p>}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
                Phone Number <span className="text-rose-500">*</span>
              </label>
              <input
                type="tel"
                required
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                placeholder="+91 98765 43210"
                className="w-full px-3 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              {errors.phone && <p className="text-[11px] text-rose-500 mt-1">{errors.phone}</p>}
            </div>

            <div>
              <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
                Roll Number
              </label>
              <input
                type="text"
                value={formData.roll_no}
                onChange={(e) => setFormData({ ...formData, roll_no: e.target.value })}
                placeholder="Optional, e.g. 21CS042"
                className="w-full px-3 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border)]">
            <Button type="button" variant="outline" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={isLoading}>
              Join Waitlist
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}
