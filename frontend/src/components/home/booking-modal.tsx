"use client";

import React, { useState, useEffect } from "react";
import { z } from "zod";
import { 
  Building2, 
  Calendar, 
  Clock, 
  Users, 
  CheckCircle2, 
  Copy, 
  Check, 
  AlertCircle, 
  Sparkles, 
  Mail, 
  ShieldCheck, 
  Layers 
} from "lucide-react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Stepper } from "@/components/ui/stepper";
import { apiClient } from "@/lib/api-client";
import { showToast } from "@/components/ui/toast";

const bookingSchema = z.object({
  roll_no: z
    .string()
    .trim()
    .min(2, "Roll number must be at least 2 characters")
    .max(50, "Roll number must be less than 50 characters"),
  name: z
    .string()
    .trim()
    .min(2, "Full name must be at least 2 characters")
    .max(255, "Name must be less than 255 characters"),
  department_id: z
    .number()
    .int()
    .positive("Please select a department"),
  class_name: z
    .string()
    .trim()
    .min(1, "Class/section is required (e.g. III Year / Sec A)")
    .max(100),
  phone: z
    .string()
    .trim()
    .refine((val) => {
      const clean = val.replace(/[\s\-\+\(\)]/g, "");
      return /^\d+$/.test(clean) && clean.length >= 7 && clean.length <= 15;
    }, "Please provide a valid contact phone number (at least 7 digits)"),
  email: z
    .string()
    .trim()
    .email("Please enter a valid college email address"),
  purpose: z
    .string()
    .trim()
    .min(3, "Purpose must be at least 3 characters")
    .max(500, "Purpose cannot exceed 500 characters"),
  expected_strength: z
    .number()
    .int()
    .positive("Expected strength must be at least 1"),
});

export type BookingFormData = z.infer<typeof bookingSchema>;

interface BookingModalProps {
  isOpen: boolean;
  onClose: () => void;
  room: any | null;
  date: string;
  slot: any | null;
  departments: Array<{ id: number; name: string; code: string }>;
  expectedStrength?: number;
  initialValues?: Partial<BookingFormData & { faculty_id?: string }>;
  isFaculty?: boolean;
  onBookingSuccess?: (reference: string) => void;
}

export function BookingModal({
  isOpen,
  onClose,
  room,
  date,
  slot,
  departments,
  expectedStrength = 40,
  initialValues,
  isFaculty = false,
  onBookingSuccess,
}: BookingModalProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [formData, setFormData] = useState<Partial<BookingFormData>>({
    roll_no: initialValues?.faculty_id || initialValues?.roll_no || "",
    name: initialValues?.name || "",
    department_id: initialValues?.department_id || departments[0]?.id || 1,
    class_name: initialValues?.class_name || (isFaculty ? "Academic Session" : ""),
    phone: initialValues?.phone || "",
    email: initialValues?.email || "",
    purpose: "",
    expected_strength: expectedStrength,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [bookingResult, setBookingResult] = useState<any | null>(null);
  const [isCopied, setIsCopied] = useState(false);

  const wasOpenRef = React.useRef(false);

  useEffect(() => {
    if (isOpen && !wasOpenRef.current) {
      setCurrentStep(0);
      setErrors({});
      setBookingResult(null);
      const roomCapacity = room?.capacity || 200;
      const safeCapacity = Math.min(
        initialValues?.expected_strength || expectedStrength || roomCapacity,
        roomCapacity
      );
      const defaultDeptId =
        initialValues?.department_id ||
        room?.department_id ||
        (departments.length > 0 ? departments[0].id : 1);
      setFormData({
        roll_no: initialValues?.faculty_id || initialValues?.roll_no || "",
        name: initialValues?.name || "",
        email: initialValues?.email || "",
        phone: initialValues?.phone || "",
        class_name: initialValues?.class_name || (isFaculty ? "Academic Session" : ""),
        department_id: defaultDeptId,
        expected_strength: safeCapacity,
        purpose: "",
      });
    }
    wasOpenRef.current = isOpen;
  }, [isOpen, room, departments, expectedStrength, initialValues, isFaculty]);

  const steps = [
    { id: "summary", title: "Summary" },
    { id: "details", title: isFaculty ? "Faculty Details" : "Student Details" },
    { id: "success", title: "Confirmation" },
  ];

  const handleInputChange = (field: keyof BookingFormData, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  };

  const validateDetails = () => {
    const parseResult = bookingSchema.safeParse({
      ...formData,
      expected_strength: Number(formData.expected_strength),
      department_id: Number(formData.department_id),
    });

    if (!parseResult.success) {
      const fieldErrors: Record<string, string> = {};
      parseResult.error.issues.forEach((err: any) => {
        const field = err.path[0] as string;
        if (field) {
          fieldErrors[field] = err.message;
        }
      });
      setErrors(fieldErrors);
      return false;
    }

    setErrors({});
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!room || !slot || !date) return;

    const roomId = Number(room?.id ?? room?.room_id);
    const slotId = Number(slot?.id ?? slot?.slot_id);
    const dateStr =
      typeof date === "string"
        ? date.split("T")[0]
        : new Date().toISOString().split("T")[0];

    if (!roomId || isNaN(roomId)) {
      showToast({
        title: "Invalid Room",
        message: "No valid room was selected. Please re-select the room.",
        type: "error",
      });
      return;
    }

    if (!slotId || isNaN(slotId)) {
      showToast({
        title: "Invalid Slot",
        message: "No valid time slot was selected. Please re-select the slot.",
        type: "error",
      });
      return;
    }

    if (!validateDetails()) {
      showToast({
        title: "Validation Error",
        message: "Please fill all required student details correctly.",
        type: "error",
      });
      return;
    }

    setIsSubmitting(true);
    try {
      let res: any;
      if (isFaculty) {
        const payload = {
          room_id: roomId,
          date: dateStr,
          slot_id: slotId,
          purpose: formData.purpose?.trim(),
          expected_strength: Number(formData.expected_strength),
          required_facilities: Array.isArray(room.facilities) ? room.facilities : [],
          faculty_id: formData.roll_no?.trim() || initialValues?.faculty_id || undefined,
          class_name: formData.class_name?.trim() || "Academic Session",
          phone: formData.phone?.trim() || undefined,
        };

        res = await apiClient<any>("/api/faculty/bookings", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      } else {
        const payload = {
          room_id: roomId,
          date: dateStr,
          slot_id: slotId,
          purpose: formData.purpose?.trim(),
          expected_strength: Number(formData.expected_strength),
          required_facilities: Array.isArray(room.facilities) ? room.facilities : [],
          roll_no: formData.roll_no?.trim(),
          name: formData.name?.trim(),
          department_id: Number(formData.department_id),
          class_name: formData.class_name?.trim(),
          phone: formData.phone?.trim(),
          email: formData.email?.trim().toLowerCase(),
        };

        res = await apiClient<any>("/api/public/bookings", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }

      setBookingResult(res);
      setCurrentStep(2);

      // Trigger celebratory confetti dynamically
      import("canvas-confetti").then((mod) => {
        mod.default({
          particleCount: 120,
          spread: 80,
          origin: { y: 0.6 },
        });
      });

      if (onBookingSuccess) {
        onBookingSuccess(res.reference);
      }
    } catch (err: any) {
      if (err.fieldErrors) {
        setErrors((prev) => ({ ...prev, ...err.fieldErrors }));
      }
      showToast({
        title: "Booking Failed",
        message:
          typeof err.message === "string"
            ? err.message
            : "Failed to submit booking request. Slot might already be taken.",
        type: "error",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyReference = () => {
    if (!bookingResult?.reference) return;
    navigator.clipboard.writeText(bookingResult.reference);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
    showToast({
      title: "Copied!",
      message: `Booking reference ${bookingResult.reference} copied to clipboard.`,
      type: "success",
    });
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={currentStep === 2 ? "" : isFaculty ? "Faculty Space Reservation" : "Room Reservation Request"}
      description={currentStep === 2 ? "" : isFaculty ? "Academic Schedule Request with Prefilled Credentials" : "Student Public Space Allocation"}
      maxWidth="lg"
    >
      <Stepper steps={steps} currentStep={currentStep} className="mb-4" />

      {/* STEP 0: Selected Room & Slot Summary */}
      {currentStep === 0 && room && (
        <div className="space-y-5">
          <div className="p-4 rounded-2xl bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800/60">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] uppercase tracking-wider font-bold text-sky-700 dark:text-sky-300">
                  Selected Venue
                </span>
                <h4 className="text-xl font-extrabold text-[var(--foreground)] mt-0.5">
                  {room.name || room.room_name || "Room"}
                </h4>
                <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                  {room.block_name} • Floor {room.floor} • Type: {room.room_type}
                </p>
              </div>
              <div className="text-right">
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-sky-200 dark:bg-sky-900 text-sky-800 dark:text-sky-200">
                  {room.capacity} Seats
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-4 pt-3 border-t border-sky-200 dark:border-sky-800/60 text-xs">
              <div className="flex items-center gap-2 text-[var(--foreground)]">
                <Calendar className="w-4 h-4 text-sky-600 dark:text-sky-400 shrink-0" />
                <span>
                  Date: <strong>{date}</strong>
                </span>
              </div>
              <div className="flex items-center gap-2 text-[var(--foreground)]">
                <Clock className="w-4 h-4 text-sky-600 dark:text-sky-400 shrink-0" />
                <span>
                  Period: <strong>{slot?.label || "Slot Selected"}</strong>
                </span>
              </div>
            </div>
          </div>

          {room.facilities && room.facilities.length > 0 && (
            <div>
              <span className="text-xs font-medium text-[var(--muted-foreground)] block mb-1.5">
                Room Amenities Included:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {room.facilities.map((fac: string) => (
                  <span
                    key={fac}
                    className="text-xs px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-[var(--foreground)] border border-[var(--border)]"
                  >
                    ✓ {fac}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-[var(--border)] text-xs text-[var(--muted-foreground)] space-y-1">
            <div className="flex items-center gap-1.5 font-medium text-[var(--foreground)]">
              <ShieldCheck className="w-4 h-4 text-emerald-500" />
              Automated Approval Path
            </div>
            <p>
              Your request will be assigned to the Block Coordinator
              {room.room_type === "LAB" || room.room_type === "EXAM_HALL" ? " and Department HOD" : ""} for review. You will receive an immediate acknowledgement email with real-time tracking.
            </p>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => setCurrentStep(1)}>
              Continue to {isFaculty ? "Faculty Details" : "Student Info"} →
            </Button>
          </div>
        </div>
      )}

      {/* STEP 1: Student/Faculty Details Form */}
      {currentStep === 1 && (
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* General field errors from API (e.g., room_id, slot_id, date) */}
          {Object.entries(errors).filter(([k]) => !['roll_no', 'name', 'department_id', 'class_name', 'email', 'phone', 'purpose', 'expected_strength'].includes(k)).length > 0 && (
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300 space-y-1">
              <div className="flex items-center gap-1.5 font-bold">
                <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
                <span>Notice</span>
              </div>
              {Object.entries(errors)
                .filter(([k]) => !['roll_no', 'name', 'department_id', 'class_name', 'email', 'phone', 'purpose', 'expected_strength'].includes(k))
                .map(([k, v]) => (
                  <p key={k}>
                    <strong className="capitalize">{k.replace(/_/g, " ")}:</strong> {v}
                  </p>
                ))}
            </div>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
                {isFaculty ? "Faculty / Staff ID" : "Roll Number"} <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                placeholder={isFaculty ? "e.g. FAC-101" : "e.g. 21CS042"}
                value={formData.roll_no}
                onChange={(e) => handleInputChange("roll_no", e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              {errors.roll_no && (
                <p className="text-[11px] text-rose-500 mt-1">{errors.roll_no}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
                {isFaculty ? "Faculty Full Name" : "Student Full Name"} <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                placeholder={isFaculty ? "e.g. Dr. Amit Roy" : "e.g. Jane Doe"}
                value={formData.name}
                onChange={(e) => handleInputChange("name", e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              {errors.name && (
                <p className="text-[11px] text-rose-500 mt-1">{errors.name}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
                Department <span className="text-rose-500">*</span>
              </label>
              <select
                value={formData.department_id}
                onChange={(e) => handleInputChange("department_id", Number(e.target.value))}
                className="w-full px-3 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              >
                {departments.map((dept) => (
                  <option key={dept.id} value={dept.id}>
                    {dept.name} ({dept.code})
                  </option>
                ))}
              </select>
              {errors.department_id && (
                <p className="text-[11px] text-rose-500 mt-1">{errors.department_id}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
                {isFaculty ? "Class / Academic Session" : "Class / Section"} <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                placeholder={isFaculty ? "e.g. CS IV Year / Academic Session" : "e.g. III Year / Sec B"}
                value={formData.class_name}
                onChange={(e) => handleInputChange("class_name", e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              {errors.class_name && (
                <p className="text-[11px] text-rose-500 mt-1">{errors.class_name}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
                {isFaculty ? "Faculty College Email" : "College Email"} <span className="text-rose-500">*</span>
              </label>
              <input
                type="email"
                placeholder="e.g. jane@college.edu"
                value={formData.email}
                onChange={(e) => handleInputChange("email", e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              {errors.email && (
                <p className="text-[11px] text-rose-500 mt-1">{errors.email}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
                Contact Phone <span className="text-rose-500">*</span>
              </label>
              <input
                type="tel"
                placeholder="e.g. +91 9876543210"
                value={formData.phone}
                onChange={(e) => handleInputChange("phone", e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              {errors.phone && (
                <p className="text-[11px] text-rose-500 mt-1">{errors.phone}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
                Event / Booking Purpose <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                placeholder="e.g. Technical Seminar, Club Meet, Workshop"
                value={formData.purpose}
                onChange={(e) => handleInputChange("purpose", e.target.value)}
                className="w-full px-3.5 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              {errors.purpose && (
                <p className="text-[11px] text-rose-500 mt-1">{errors.purpose}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold mb-1 text-[var(--foreground)]">
                Attendees <span className="text-rose-500">*</span>
              </label>
              <input
                type="number"
                min={1}
                max={room?.capacity || 200}
                value={formData.expected_strength}
                onChange={(e) => handleInputChange("expected_strength", Number(e.target.value))}
                className="w-full px-3.5 py-2 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
              {errors.expected_strength && (
                <p className="text-[11px] text-rose-500 mt-1">{errors.expected_strength}</p>
              )}
            </div>
          </div>

          <div className="flex justify-between items-center pt-3 border-t border-[var(--border)]">
            <Button
              type="button"
              variant="outline"
              onClick={() => setCurrentStep(0)}
              disabled={isSubmitting}
            >
              ← Back to Room
            </Button>
            <Button
              type="submit"
              variant="primary"
              isLoading={isSubmitting}
            >
              {isFaculty ? "Submit Faculty Booking Request" : "Submit Reservation Request"}
            </Button>
          </div>
        </form>
      )}

      {/* STEP 2: Animated Success Screen */}
      {currentStep === 2 && bookingResult && (
        <div className="text-center py-4 space-y-6">
          <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 mx-auto flex items-center justify-center animate-bounce-short">
            <CheckCircle2 className="w-10 h-10" />
          </div>

          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-3 py-1 rounded-full border border-emerald-200 dark:border-emerald-800">
              Request Successfully Submitted
            </span>
            <h3 className="text-2xl font-black text-[var(--foreground)] mt-2">
              Acknowledgement email sent
            </h3>
            <p className="text-xs text-[var(--muted-foreground)] mt-1 max-w-md mx-auto">
              We have dispatched your reservation details and a secure cancellation link to{" "}
              <strong className="text-[var(--foreground)]">{bookingResult.email}</strong>.
            </p>
          </div>

          {/* Reference Card with Copy Button */}
          <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-900 border border-[var(--border)] max-w-md mx-auto">
            <div className="text-xs uppercase tracking-wider text-[var(--muted-foreground)] font-semibold mb-1">
              Your Booking Reference
            </div>
            <div className="flex items-center justify-center gap-2">
              <span className="font-mono text-2xl font-black text-sky-600 dark:text-sky-400">
                {bookingResult.reference}
              </span>
              <button
                type="button"
                onClick={copyReference}
                className="p-1.5 rounded-lg border border-[var(--border)] hover:bg-slate-200 dark:hover:bg-slate-800 text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
                title="Copy reference code"
              >
                {isCopied ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-[11px] text-[var(--muted-foreground)] mt-2">
              Keep this reference to track approval status or cancel your booking anytime.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800 text-xs text-sky-800 dark:text-sky-200 max-w-md mx-auto flex items-start gap-2 text-left">
            <Mail className="w-4 h-4 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" />
            <span>
              Check your inbox (or Mailpit in development on port 8025) for your immediate confirmation notification.
            </span>
          </div>

          <div className="pt-2 flex justify-center gap-3">
            <Button
              variant="primary"
              onClick={onClose}
              className="px-8"
            >
              Done & Return to Portal
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
