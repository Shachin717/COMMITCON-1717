"use client";

import React, { useState } from "react";
import { 
  Search, 
  Calendar, 
  Clock, 
  MapPin, 
  User, 
  AlertCircle, 
  CheckCircle2, 
  XCircle, 
  Clock3, 
  X, 
  AlertTriangle, 
  FileText,
  Mail
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { Modal } from "@/components/ui/modal";
import { apiClient } from "@/lib/api-client";
import { showToast } from "@/components/ui/toast";

interface BookingStatusData {
  reference: string;
  status: string;
  room_id: number;
  room_name: string;
  block_name?: string;
  floor?: number;
  date: string;
  slot_id: number;
  slot_label: string;
  roll_no?: string;
  name: string;
  email: string;
  phone?: string;
  department_name?: string;
  class_name?: string;
  purpose: string;
  expected_strength: number;
  required_facilities: string[];
  requires_hod_approval: boolean;
  decision_note?: string;
  checked_in?: boolean;
  created_at: string;
}

export function ManageBookingSection() {
  const [reference, setReference] = useState("");
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [booking, setBooking] = useState<BookingStatusData | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isCheckingIn, setIsCheckingIn] = useState(false);

  // Cancellation state
  const [isCancelModalOpen, setIsCancelModalOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [isCancelling, setIsCancelling] = useState(false);

  const handleLookup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reference.trim() || !email.trim()) return;

    setIsLoading(true);
    setErrorMessage(null);
    setBooking(null);

    try {
      const data = await apiClient<BookingStatusData>(
        `/api/public/bookings/${encodeURIComponent(reference.trim())}`,
        {
          params: { email: email.trim().toLowerCase() },
        }
      );
      setBooking(data);
    } catch (err: any) {
      setErrorMessage(
        err.message || "Booking not found. Please check your Reference code and Email."
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmCancel = async () => {
    if (!booking) return;

    setIsCancelling(true);
    try {
      await apiClient("/api/public/bookings/cancel", {
        method: "POST",
        body: JSON.stringify({
          reference: booking.reference,
          email: booking.email,
          reason: cancelReason.trim() || "Requester initiated cancellation",
        }),
      });

      showToast({
        title: "Booking Cancelled",
        message: "Your reservation has been cancelled and the slot freed.",
        type: "success",
      });

      setBooking((prev) =>
        prev
          ? {
              ...prev,
              status: "CANCELLED",
              decision_note: cancelReason ? `Cancellation Reason: ${cancelReason}` : "Cancelled by requester",
            }
          : null
      );
      setIsCancelModalOpen(false);
      setCancelReason("");
    } catch (err: any) {
      showToast({
        title: "Cancellation Failed",
        message: err.message || "Could not cancel booking.",
        type: "error",
      });
    } finally {
      setIsCancelling(false);
    }
  };

  const handleCheckIn = async () => {
    if (!booking) return;
    setIsCheckingIn(true);
    try {
      await apiClient(`/api/public/bookings/${booking.reference}/check-in`, {
        method: "POST",
      });
      setBooking((prev) => (prev ? { ...prev, checked_in: true } : null));
      showToast({
        title: "Checked In Successfully",
        message: "Your attendance has been confirmed.",
        type: "success",
      });
    } catch (err: any) {
      showToast({
        title: "Check-In Failed",
        message: err.message || "Failed to confirm check-in.",
        type: "error",
      });
    } finally {
      setIsCheckingIn(false);
    }
  };

  // Timeline computation
  const getTimelineSteps = () => {
    if (!booking) return [];

    const isRejected = booking.status === "REJECTED";
    const isCancelled = booking.status === "CANCELLED";
    const reqHod = booking.requires_hod_approval;

    const baseSteps = [
      {
        id: "requested",
        title: "Requested",
        desc: "Student submission received",
        state: "completed", // always completed once booked
      },
      {
        id: "coordinator",
        title: "Coordinator Review",
        desc: "Block coordinator evaluation",
        state:
          isCancelled || isRejected
            ? "neutral"
            : booking.status === "PENDING"
            ? "current"
            : "completed",
      },
    ];

    if (reqHod) {
      baseSteps.push({
        id: "hod",
        title: "HOD Approval",
        desc: "Department head sign-off",
        state:
          isCancelled || isRejected
            ? "neutral"
            : booking.status === "COORDINATOR_APPROVED"
            ? "current"
            : booking.status === "APPROVED"
            ? "completed"
            : "pending",
      });
    }

    baseSteps.push({
      id: "confirmed",
      title: "Confirmed",
      desc: "Allocation locked & active",
      state:
        isCancelled || isRejected
          ? "neutral"
          : booking.status === "APPROVED"
          ? "completed"
          : "pending",
    });

    return baseSteps;
  };

  const timeline = getTimelineSteps();

  return (
    <section id="manage-section" className="py-16 relative">
      <div className="max-w-4xl mx-auto px-4 sm:px-6">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300 text-xs font-semibold uppercase tracking-wider mb-3">
            <FileText className="w-3.5 h-3.5" />
            Self-Service Tracking
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[var(--foreground)]">
            Manage Your Booking
          </h2>
          <p className="text-sm text-[var(--muted-foreground)] mt-2 max-w-xl mx-auto">
            Check approval progress, view room allotment details, or cancel your reservation using your Booking Reference and student email.
          </p>
        </div>

        {/* Lookup Card */}
        <div className="glass-card p-6 sm:p-8 shadow-xl border-[var(--border)] mb-8">
          <form onSubmit={handleLookup} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold mb-1.5 text-[var(--foreground)]">
                  Booking Reference <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. BK-20261010-ABCD"
                  value={reference}
                  onChange={(e) => setReference(e.target.value.toUpperCase())}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm font-mono focus:outline-none focus:ring-2 focus:ring-sky-500 uppercase"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold mb-1.5 text-[var(--foreground)]">
                  Student College Email <span className="text-rose-500">*</span>
                </label>
                <input
                  type="email"
                  required
                  placeholder="e.g. student@college.edu"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button
                type="submit"
                variant="primary"
                isLoading={isLoading}
                className="w-full sm:w-auto px-6"
              >
                <Search className="w-4 h-4 mr-2" />
                Track Booking
              </Button>
            </div>
          </form>

          {errorMessage && (
            <div className="mt-4 p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>

        {/* Booking Details & Timeline Card */}
        {booking && (
          <div className="glass-card p-6 sm:p-8 shadow-xl border-[var(--border)] space-y-8 animate-fade-in">
            {/* Header with Reference & Status */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[var(--border)]">
              <div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xl sm:text-2xl font-black text-sky-600 dark:text-sky-400">
                    {booking.reference}
                  </span>
                  <StatusBadge status={booking.status} />
                </div>
                <p className="text-xs text-[var(--muted-foreground)] mt-1">
                  Submitted on {new Date(booking.created_at).toLocaleString()}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {booking.status === "APPROVED" && (
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={booking.checked_in || isCheckingIn}
                    onClick={handleCheckIn}
                    className="gap-1.5"
                    aria-label="Confirm attendance check-in"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    {booking.checked_in ? "Checked In" : isCheckingIn ? "Checking In..." : "Check In"}
                  </Button>
                )}
                {booking.status !== "CANCELLED" && booking.status !== "REJECTED" && (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => setIsCancelModalOpen(true)}
                    aria-label="Cancel this booking"
                  >
                    <X className="w-4 h-4 mr-1.5" />
                    Cancel Booking
                  </Button>
                )}
              </div>
            </div>

            {/* Decision note or alert if cancelled/rejected */}
            {booking.decision_note && (
              <div className="p-3.5 rounded-xl bg-slate-100 dark:bg-slate-800/70 border border-[var(--border)] text-xs text-[var(--foreground)] flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-amber-500" />
                <span>
                  <strong>Note:</strong> {booking.decision_note}
                </span>
              </div>
            )}

            {/* Status Timeline */}
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--muted-foreground)] mb-4">
                Approval Workflow Progress
              </h4>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 relative">
                {timeline.map((step, idx) => {
                  const isDone = step.state === "completed";
                  const isCur = step.state === "current";

                  return (
                    <div
                      key={step.id}
                      className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--background)]/60 relative overflow-hidden"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        {isDone ? (
                          <div className="w-6 h-6 rounded-full bg-emerald-500 text-white flex items-center justify-center text-xs font-bold">
                            ✓
                          </div>
                        ) : isCur ? (
                          <div className="w-6 h-6 rounded-full bg-sky-500 text-white flex items-center justify-center text-xs font-bold animate-pulse">
                            •
                          </div>
                        ) : (
                          <div className="w-6 h-6 rounded-full bg-slate-200 dark:bg-slate-700 text-[var(--muted-foreground)] flex items-center justify-center text-xs font-medium">
                            {idx + 1}
                          </div>
                        )}
                        <span
                          className={`text-xs font-bold ${
                            isDone
                              ? "text-emerald-600 dark:text-emerald-400"
                              : isCur
                              ? "text-sky-600 dark:text-sky-400"
                              : "text-[var(--muted-foreground)]"
                          }`}
                        >
                          {step.title}
                        </span>
                      </div>
                      <p className="text-[11px] text-[var(--muted-foreground)]">
                        {step.desc}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Information Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 pt-4 border-t border-[var(--border)] text-sm">
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                  Venue & Slot Details
                </h4>
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-[var(--border)] space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Room:</span>
                    <strong className="text-[var(--foreground)]">{booking.room_name}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Block / Floor:</span>
                    <span>{booking.block_name || "Academic"} {booking.floor ? `(Floor ${booking.floor})` : ""}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Date:</span>
                    <strong className="text-sky-600 dark:text-sky-400">{booking.date}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Period Slot:</span>
                    <span>{booking.slot_label}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Purpose:</span>
                    <span className="font-medium text-right">{booking.purpose}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                  Student Information
                </h4>
                <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-[var(--border)] space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Student Name:</span>
                    <strong className="text-[var(--foreground)]">{booking.name}</strong>
                  </div>
                  {booking.roll_no && (
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Roll No:</span>
                      <span className="font-mono">{booking.roll_no}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Department:</span>
                    <span>{booking.department_name || "General"}</span>
                  </div>
                  {booking.class_name && (
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Class / Section:</span>
                      <span>{booking.class_name}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Email:</span>
                    <span>{booking.email}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Cancellation Dialog */}
      <Modal
        isOpen={isCancelModalOpen}
        onClose={() => setIsCancelModalOpen(false)}
        title="Confirm Booking Cancellation"
        description="Are you sure you want to release this space reservation?"
        maxWidth="sm"
      >
        <div className="space-y-4">
          <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-700 dark:text-rose-300 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              This action cannot be undone. The room slot will immediately be made available to other students and waitlisted requests.
            </span>
          </div>

          <div>
            <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
              Cancellation Reason (e.g. Emergency, Faculty unavailable)
            </label>
            <textarea
              rows={3}
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="Please specify why you are cancelling..."
              className="w-full px-3 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-xs focus:outline-none focus:ring-2 focus:ring-rose-500 resize-none"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button
              variant="outline"
              onClick={() => setIsCancelModalOpen(false)}
              disabled={isCancelling}
            >
              Keep Booking
            </Button>
            <Button
              variant="danger"
              onClick={handleConfirmCancel}
              isLoading={isCancelling}
            >
              Cancel Reservation
            </Button>
          </div>
        </div>
      </Modal>
    </section>
  );
}

