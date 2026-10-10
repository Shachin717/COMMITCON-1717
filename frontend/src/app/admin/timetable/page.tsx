"use client";

import * as React from "react";
import {
  CalendarDays,
  Clock,
  Plus,
  Upload,
  Search,
  RotateCw,
  Edit2,
  Trash2,
  Download,
  DoorOpen,
  Calendar,
  Building2,
  CheckCircle,
  XCircle,
  FileSpreadsheet,
  AlertCircle,
  Filter,
} from "lucide-react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Modal } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { showToast } from "@/components/ui/toast";
import { apiClient } from "@/lib/api-client";
import {
  TimeSlot,
  TimetableEntry,
  Room,
  Department,
  Block,
  PaginatedResponse,
} from "@/lib/admin-types";

const DAYS_OF_WEEK = [
  { value: 0, label: "Monday" },
  { value: 1, label: "Tuesday" },
  { value: 2, label: "Wednesday" },
  { value: 3, label: "Thursday" },
  { value: 4, label: "Friday" },
  { value: 5, label: "Saturday" },
];

export default function AdminTimetablePage() {
  const [activeTab, setActiveTab] = React.useState<"grid" | "slots" | "availability">("grid");

  // Metadata
  const [rooms, setRooms] = React.useState<Room[]>([]);
  const [departments, setDepartments] = React.useState<Department[]>([]);
  const [blocks, setBlocks] = React.useState<Block[]>([]);
  const [timeSlots, setTimeSlots] = React.useState<TimeSlot[]>([]);

  // Timetable Entries state
  const [entries, setEntries] = React.useState<TimetableEntry[]>([]);
  const [loadingEntries, setLoadingEntries] = React.useState(true);
  const [selectedRoomId, setSelectedRoomId] = React.useState<string>("");
  const [selectedDay, setSelectedDay] = React.useState<string>("");

  // Slots state
  const [loadingSlots, setLoadingSlots] = React.useState(false);

  // Availability Date Query state
  const [queryDate, setQueryDate] = React.useState<string>(() => {
    return new Date().toISOString().split("T")[0];
  });
  const [availBlockFilter, setAvailBlockFilter] = React.useState<string>("");
  const [availData, setAvailData] = React.useState<any>(null);
  const [loadingAvail, setLoadingAvail] = React.useState(false);

  // Modals
  const [entryModalOpen, setEntryModalOpen] = React.useState(false);
  const [editingEntry, setEditingEntry] = React.useState<TimetableEntry | null>(null);
  const [slotModalOpen, setSlotModalOpen] = React.useState(false);
  const [editingSlot, setEditingSlot] = React.useState<TimeSlot | null>(null);
  const [csvModalOpen, setCsvModalOpen] = React.useState(false);
  const [deleteConfirm, setDeleteConfirm] = React.useState<{
    isOpen: boolean;
    type: "entry" | "slot";
    id: number;
    title: string;
  }>({ isOpen: false, type: "entry", id: 0, title: "" });

  // Entry Form
  const [entryForm, setEntryForm] = React.useState({
    room_id: "",
    day_of_week: "0",
    slot_id: "",
    department_id: "",
    subject: "",
    faculty_name: "",
  });

  // Slot Form
  const [slotForm, setSlotForm] = React.useState({
    label: "",
    start_time: "09:00",
    end_time: "10:00",
    order: 1,
  });

  // CSV Import State
  const [csvFile, setCsvFile] = React.useState<File | null>(null);
  const [csvResult, setCsvResult] = React.useState<any>(null);
  const [submitting, setSubmitting] = React.useState(false);

  // Fetch initial metadata
  const fetchMetadata = React.useCallback(async () => {
    try {
      const [rRes, dRes, bRes, sRes] = await Promise.all([
        apiClient<PaginatedResponse<Room>>("/api/admin/rooms?page_size=100"),
        apiClient<PaginatedResponse<Department>>("/api/admin/departments?page_size=100"),
        apiClient<PaginatedResponse<Block>>("/api/admin/blocks?page_size=100"),
        apiClient<PaginatedResponse<TimeSlot>>("/api/admin/time-slots?page_size=100"),
      ]);
      setRooms(rRes.items || []);
      setDepartments(dRes.items || []);
      setBlocks(bRes.items || []);
      setTimeSlots(sRes.items || []);
      if (rRes.items?.[0] && !selectedRoomId) {
        setSelectedRoomId(String(rRes.items[0].id));
      }
    } catch {
      // ignore
    }
  }, [selectedRoomId]);

  // Fetch timetable entries
  const fetchEntries = React.useCallback(async () => {
    setLoadingEntries(true);
    try {
      const params: Record<string, any> = { page_size: 100 };
      if (selectedRoomId) params.room_id = selectedRoomId;
      if (selectedDay !== "") params.day_of_week = selectedDay;

      const res = await apiClient<PaginatedResponse<TimetableEntry>>("/api/admin/timetable", {
        params,
      });
      setEntries(res.items || []);
    } catch (err: any) {
      showToast({
        title: "Error",
        message: err.message || "Failed to load timetable",
        type: "error",
      });
    } finally {
      setLoadingEntries(false);
    }
  }, [selectedRoomId, selectedDay]);

  // Fetch slots
  const fetchSlots = React.useCallback(async () => {
    setLoadingSlots(true);
    try {
      const res = await apiClient<PaginatedResponse<TimeSlot>>("/api/admin/time-slots?page_size=100");
      setTimeSlots(res.items || []);
    } catch (err: any) {
      showToast({
        title: "Error",
        message: err.message || "Failed to load time slots",
        type: "error",
      });
    } finally {
      setLoadingSlots(false);
    }
  }, []);

  // Fetch Availability for query date
  const fetchAvailability = React.useCallback(async () => {
    if (!queryDate) return;
    setLoadingAvail(true);
    try {
      const params: Record<string, any> = { date: queryDate };
      if (availBlockFilter) params.block_id = availBlockFilter;

      const [gridRes, freeRes] = await Promise.all([
        apiClient<any>("/api/public/timetable", { params }).catch(() => null),
        apiClient<any>("/api/public/availability", { params }).catch(() => null),
      ]);

      setAvailData({
        grid: gridRes,
        availability: freeRes,
      });
    } catch (err: any) {
      showToast({
        title: "Query Error",
        message: err.message || "Could not check date schedule",
        type: "error",
      });
    } finally {
      setLoadingAvail(false);
    }
  }, [queryDate, availBlockFilter]);

  React.useEffect(() => {
    fetchMetadata();
  }, [fetchMetadata]);

  React.useEffect(() => {
    if (activeTab === "grid") {
      fetchEntries();
    } else if (activeTab === "slots") {
      fetchSlots();
    } else if (activeTab === "availability") {
      fetchAvailability();
    }
  }, [activeTab, fetchEntries, fetchSlots, fetchAvailability]);

  // Create / Edit Timetable Entry
  const handleSaveEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!entryForm.room_id || !entryForm.slot_id || !entryForm.subject.trim() || !entryForm.faculty_name.trim()) {
      showToast({ title: "Validation Error", message: "All fields are required", type: "error" });
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        room_id: parseInt(entryForm.room_id, 10),
        day_of_week: parseInt(entryForm.day_of_week, 10),
        slot_id: parseInt(entryForm.slot_id, 10),
        department_id: entryForm.department_id ? parseInt(entryForm.department_id, 10) : departments[0]?.id || 1,
        subject: entryForm.subject.trim(),
        faculty_name: entryForm.faculty_name.trim(),
      };

      if (editingEntry) {
        await apiClient(`/api/admin/timetable/${editingEntry.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        showToast({ title: "Updated", message: "Class entry updated.", type: "success" });
      } else {
        await apiClient("/api/admin/timetable", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        showToast({ title: "Class Scheduled", message: "Timetable entry saved.", type: "success" });
      }

      setEntryModalOpen(false);
      fetchEntries();
    } catch (err: any) {
      showToast({
        title: "Save Failed",
        message: err.message || "Could not save entry (slot conflict may exist)",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Create / Edit Time Slot
  const handleSaveSlot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!slotForm.label.trim() || !slotForm.start_time || !slotForm.end_time) {
      showToast({ title: "Validation Error", message: "Label and times required", type: "error" });
      return;
    }

    setSubmitting(true);
    try {
      // Ensure times in HH:MM:SS format
      const start = slotForm.start_time.length === 5 ? `${slotForm.start_time}:00` : slotForm.start_time;
      const end = slotForm.end_time.length === 5 ? `${slotForm.end_time}:00` : slotForm.end_time;

      const payload = {
        label: slotForm.label.trim(),
        start_time: start,
        end_time: end,
        order: Number(slotForm.order) || 1,
      };

      if (editingSlot) {
        await apiClient(`/api/admin/time-slots/${editingSlot.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        showToast({ title: "Period Updated", message: "Slot details saved.", type: "success" });
      } else {
        await apiClient("/api/admin/time-slots", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        showToast({ title: "Period Created", message: "New time slot added.", type: "success" });
      }

      setSlotModalOpen(false);
      fetchSlots();
      fetchMetadata();
    } catch (err: any) {
      showToast({
        title: "Save Failed",
        message: err.message || "Failed to save time slot",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Delete Item
  const handleDeleteItem = async () => {
    try {
      if (deleteConfirm.type === "entry") {
        await apiClient(`/api/admin/timetable/${deleteConfirm.id}`, { method: "DELETE" });
        showToast({ title: "Entry Removed", message: "Timetable class deleted.", type: "info" });
        fetchEntries();
      } else {
        await apiClient(`/api/admin/time-slots/${deleteConfirm.id}`, { method: "DELETE" });
        showToast({ title: "Slot Deleted", message: "Time slot deleted.", type: "info" });
        fetchSlots();
        fetchMetadata();
      }
      setDeleteConfirm({ isOpen: false, type: "entry", id: 0, title: "" });
    } catch (err: any) {
      showToast({
        title: "Delete Failed",
        message: err.message || "Cannot delete item",
        type: "error",
      });
    }
  };

  // CSV Import for Timetable
  const handleCsvImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) return;

    setSubmitting(true);
    setCsvResult(null);
    try {
      const formData = new FormData();
      formData.append("file", csvFile);

      const res = await apiClient<{
        total_rows: number;
        imported: number;
        errors: { row: number; error: string }[];
      }>("/api/admin/timetable/import-csv", {
        method: "POST",
        body: formData,
      });

      setCsvResult(res);
      showToast({
        title: "Timetable CSV Processed",
        message: `Imported ${res.imported} of ${res.total_rows} entries.`,
        type: res.errors.length === 0 ? "success" : "warning",
      });
      fetchEntries();
    } catch (err: any) {
      showToast({
        title: "CSV Import Failed",
        message: err.message || "Failed to parse timetable spreadsheet",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Download Sample Timetable CSV
  const handleDownloadSample = () => {
    const csvContent =
      "room,day,slot,department,subject,faculty\n" +
      "A-101,Monday,1,CSE,Data Structures & Algorithms,Dr. Arvind Rao\n" +
      "A-101,Monday,2,CSE,Database Management Systems,Dr. Amit Roy\n" +
      "CS-LAB-01,Tuesday,3,CSE,Machine Learning Lab,Prof. Sneha Deshpande\n" +
      "EXAM-HALL-1,Wednesday,1,ECE,Microprocessors,Dr. K. Sharma\n";

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "sample_timetable.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <DashboardShell
      role="ADMIN"
      userName="System Admin"
      userEmail="admin@git.edu"
    >
      <div className="space-y-6 pb-12">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-[var(--foreground)]">
              Time Slots & Academic Timetable
            </h1>
            <p className="text-sm text-[var(--muted-foreground)]">
              Configure institutional class periods, manage the master weekly timetable grid, and check live date availability.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-xl bg-slate-100 dark:bg-slate-800 p-1 border border-[var(--border)]">
              <button
                type="button"
                onClick={() => setActiveTab("grid")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === "grid"
                    ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                Weekly Timetable
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("slots")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === "slots"
                    ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                Manage Periods
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("availability")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === "availability"
                    ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                Date Schedule Lookup
              </button>
            </div>
          </div>
        </div>

        {/* TAB 1: WEEKLY TIMETABLE GRID */}
        {activeTab === "grid" && (
          <div className="space-y-4">
            {/* Filter toolbar */}
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <div className="w-56">
                  <Select
                    options={[
                      { value: "", label: "All Rooms" },
                      ...rooms.map((r) => ({ value: String(r.id), label: `${r.name} (${r.capacity} seats)` })),
                    ]}
                    value={selectedRoomId}
                    onChange={(e) => setSelectedRoomId(e.target.value)}
                  />
                </div>
                <div className="w-44">
                  <Select
                    options={[
                      { value: "", label: "All Days (Mon-Sat)" },
                      ...DAYS_OF_WEEK.map((d) => ({ value: String(d.value), label: d.label })),
                    ]}
                    value={selectedDay}
                    onChange={(e) => setSelectedDay(e.target.value)}
                  />
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setCsvFile(null);
                    setCsvResult(null);
                    setCsvModalOpen(true);
                  }}
                  className="gap-2 text-xs"
                >
                  <Upload className="w-3.5 h-3.5" />
                  CSV Import
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    setEditingEntry(null);
                    setEntryForm({
                      room_id: selectedRoomId || (rooms[0] ? String(rooms[0].id) : ""),
                      day_of_week: selectedDay !== "" ? selectedDay : "0",
                      slot_id: timeSlots[0] ? String(timeSlots[0].id) : "",
                      department_id: departments[0] ? String(departments[0].id) : "",
                      subject: "",
                      faculty_name: "",
                    });
                    setEntryModalOpen(true);
                  }}
                  className="gap-2 text-xs bg-sky-600 hover:bg-sky-700 text-white"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Class
                </Button>
              </div>
            </div>

            {/* Timetable Entries List */}
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-[var(--foreground)]">
                  <thead className="border-b border-[var(--border)] bg-slate-50/75 dark:bg-slate-900/40 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                    <tr>
                      <th className="px-5 py-3.5">Day</th>
                      <th className="px-5 py-3.5">Period / Time Slot</th>
                      <th className="px-5 py-3.5">Room</th>
                      <th className="px-5 py-3.5">Course / Subject</th>
                      <th className="px-5 py-3.5">Faculty Member</th>
                      <th className="px-5 py-3.5">Department</th>
                      <th className="px-5 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {loadingEntries ? (
                      Array.from({ length: 5 }).map((_, i) => (
                        <tr key={i}>
                          <td colSpan={7} className="px-5 py-4">
                            <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
                          </td>
                        </tr>
                      ))
                    ) : entries.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="p-8">
                          <EmptyState
                            title="No scheduled classes found"
                            description="Use the 'Add Class' button or bulk import a weekly CSV timetable."
                          />
                        </td>
                      </tr>
                    ) : (
                      entries.map((entry) => {
                        const dayLabel = DAYS_OF_WEEK.find((d) => d.value === entry.day_of_week)?.label || `Day ${entry.day_of_week}`;
                        const slot = timeSlots.find((s) => s.id === entry.slot_id);
                        const room = rooms.find((r) => r.id === entry.room_id);
                        const dept = departments.find((d) => d.id === entry.department_id);

                        return (
                          <tr key={entry.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30 transition-colors">
                            <td className="px-5 py-3.5 font-semibold text-xs text-[var(--foreground)]">
                              {dayLabel}
                            </td>
                            <td className="px-5 py-3.5 text-xs">
                              <span className="font-medium text-sky-600 dark:text-sky-400">
                                {slot ? slot.label : `#${entry.slot_id}`}
                              </span>
                              {slot && (
                                <span className="block text-[11px] text-[var(--muted-foreground)]">
                                  {slot.start_time.slice(0, 5)} - {slot.end_time.slice(0, 5)}
                                </span>
                              )}
                            </td>
                            <td className="px-5 py-3.5 font-bold text-xs text-[var(--foreground)]">
                              {room ? room.name : `#${entry.room_id}`}
                            </td>
                            <td className="px-5 py-3.5 font-semibold text-sm text-[var(--foreground)]">
                              {entry.subject}
                            </td>
                            <td className="px-5 py-3.5 text-xs text-[var(--foreground)]">
                              {entry.faculty_name}
                            </td>
                            <td className="px-5 py-3.5 text-xs text-[var(--muted-foreground)] font-medium">
                              {dept ? `${dept.code}` : `#${entry.department_id}`}
                            </td>
                            <td className="px-5 py-3.5 text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-8 w-8 p-0"
                                  onClick={() => {
                                    setEditingEntry(entry);
                                    setEntryForm({
                                      room_id: String(entry.room_id),
                                      day_of_week: String(entry.day_of_week),
                                      slot_id: String(entry.slot_id),
                                      department_id: String(entry.department_id),
                                      subject: entry.subject,
                                      faculty_name: entry.faculty_name,
                                    });
                                    setEntryModalOpen(true);
                                  }}
                                >
                                  <Edit2 className="w-3.5 h-3.5" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-8 w-8 p-0 text-rose-500 hover:text-rose-600"
                                  onClick={() => {
                                    setDeleteConfirm({
                                      isOpen: true,
                                      type: "entry",
                                      id: entry.id,
                                      title: `Delete class '${entry.subject}'?`,
                                    });
                                  }}
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </Button>
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: MANAGE TIME SLOTS / PERIODS */}
        {activeTab === "slots" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-[var(--foreground)]">
                  College Class Periods (Time Slots)
                </h2>
                <p className="text-xs text-[var(--muted-foreground)]">
                  Standard scheduling intervals for classroom lecture periods and assessment slots.
                </p>
              </div>
              <Button
                size="sm"
                onClick={() => {
                  setEditingSlot(null);
                  setSlotForm({
                    label: `Period ${timeSlots.length + 1}`,
                    start_time: "09:00",
                    end_time: "10:00",
                    order: timeSlots.length + 1,
                  });
                  setSlotModalOpen(true);
                }}
                className="gap-2 bg-sky-600 hover:bg-sky-700 text-white"
              >
                <Plus className="w-4 h-4" />
                Add Time Slot
              </Button>
            </div>

            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
              <table className="w-full text-left text-sm text-[var(--foreground)]">
                <thead className="border-b border-[var(--border)] bg-slate-50/75 dark:bg-slate-900/40 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                  <tr>
                    <th className="px-5 py-3.5">Sequence Order</th>
                    <th className="px-5 py-3.5">Slot Label</th>
                    <th className="px-5 py-3.5">Start Time</th>
                    <th className="px-5 py-3.5">End Time</th>
                    <th className="px-5 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {loadingSlots ? (
                    Array.from({ length: 4 }).map((_, i) => (
                      <tr key={i}>
                        <td colSpan={5} className="px-5 py-4">
                          <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
                        </td>
                      </tr>
                    ))
                  ) : timeSlots.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-8">
                        <EmptyState title="No periods configured" description="Add time slots to define standard schedule periods." />
                      </td>
                    </tr>
                  ) : (
                    timeSlots
                      .sort((a, b) => a.order - b.order)
                      .map((slot) => (
                        <tr key={slot.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30 transition-colors">
                          <td className="px-5 py-3.5 font-bold font-mono text-xs">
                            #{slot.order}
                          </td>
                          <td className="px-5 py-3.5 font-semibold text-[var(--foreground)]">
                            {slot.label}
                          </td>
                          <td className="px-5 py-3.5 font-mono text-xs text-sky-600 dark:text-sky-400">
                            {slot.start_time.slice(0, 5)}
                          </td>
                          <td className="px-5 py-3.5 font-mono text-xs text-sky-600 dark:text-sky-400">
                            {slot.end_time.slice(0, 5)}
                          </td>
                          <td className="px-5 py-3.5 text-right">
                            <div className="flex items-center justify-end gap-1.5">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0"
                                onClick={() => {
                                  setEditingSlot(slot);
                                  setSlotForm({
                                    label: slot.label,
                                    start_time: slot.start_time.slice(0, 5),
                                    end_time: slot.end_time.slice(0, 5),
                                    order: slot.order,
                                  });
                                  setSlotModalOpen(true);
                                }}
                              >
                                <Edit2 className="w-3.5 h-3.5" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0 text-rose-500 hover:text-rose-600"
                                onClick={() => {
                                  setDeleteConfirm({
                                    isOpen: true,
                                    type: "slot",
                                    id: slot.id,
                                    title: `Delete time slot '${slot.label}'?`,
                                  });
                                }}
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: DATE AVAILABILITY & CLASS LOOKUP */}
        {activeTab === "availability" && (
          <div className="space-y-4">
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <div>
                  <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                    Select Target Date
                  </label>
                  <Input
                    type="date"
                    value={queryDate}
                    onChange={(e) => setQueryDate(e.target.value)}
                    className="w-48 text-xs font-medium"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                    Building Block (Optional)
                  </label>
                  <div className="w-48">
                    <Select
                      options={[
                        { value: "", label: "All Campus Blocks" },
                        ...blocks.map((b) => ({ value: String(b.id), label: b.name })),
                      ]}
                      value={availBlockFilter}
                      onChange={(e) => setAvailBlockFilter(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-end">
                <Button size="sm" onClick={fetchAvailability} isLoading={loadingAvail} className="gap-2">
                  <RotateCw className="w-3.5 h-3.5" />
                  Check Schedule
                </Button>
              </div>
            </div>

            {/* Results Grid View */}
            {loadingAvail ? (
              <div className="p-8 text-center">
                <div className="h-8 w-8 border-2 border-sky-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                <p className="text-xs text-[var(--muted-foreground)]">Evaluating room status and timetable bookings for {queryDate}...</p>
              </div>
            ) : availData?.grid ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
                    <span className="text-xs text-[var(--muted-foreground)] block">Target Date</span>
                    <span className="text-base font-bold text-[var(--foreground)]">{availData.grid.date} ({availData.grid.day_name})</span>
                  </div>
                  <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
                    <span className="text-xs text-[var(--muted-foreground)] block">Catalog Rooms Checked</span>
                    <span className="text-base font-bold text-sky-600 dark:text-sky-400">{availData.grid.rooms?.length || 0} Rooms</span>
                  </div>
                  <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
                    <span className="text-xs text-[var(--muted-foreground)] block">Standard Periods Tracked</span>
                    <span className="text-base font-bold text-emerald-600 dark:text-emerald-400">{availData.grid.slots?.length || 0} Slots</span>
                  </div>
                </div>

                {/* Visual Room x Slot Matrix */}
                <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs text-[var(--foreground)]">
                      <thead className="border-b border-[var(--border)] bg-slate-50/75 dark:bg-slate-900/40 text-[11px] font-semibold text-[var(--muted-foreground)] uppercase">
                        <tr>
                          <th className="px-4 py-3 sticky left-0 bg-[var(--card)] z-10">Room</th>
                          {availData.grid.slots?.map((s: any) => (
                            <th key={s.id} className="px-3 py-3 text-center min-w-[120px]">
                              <div>{s.label}</div>
                              <span className="font-mono text-[10px] opacity-60">
                                {s.start_time.slice(0, 5)}-{s.end_time.slice(0, 5)}
                              </span>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border)]">
                        {availData.grid.rooms?.map((r: any) => {
                          const roomSlots = availData.grid.grid?.[String(r.id)] || {};
                          return (
                            <tr key={r.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30">
                              <td className="px-4 py-3 font-bold sticky left-0 bg-[var(--card)] z-10 border-r border-[var(--border)]">
                                <div>{r.name}</div>
                                <span className="text-[10px] text-[var(--muted-foreground)] font-normal">
                                  {r.capacity} seats • {r.room_type}
                                </span>
                              </td>
                              {availData.grid.slots?.map((s: any) => {
                                const cell = roomSlots[String(s.id)];
                                const isFree = !cell || cell.type === "FREE";
                                const isMaint = cell?.type === "MAINTENANCE";
                                const isBooking = cell?.type === "BOOKING";
                                const isClass = cell?.type === "TIMETABLE";

                                return (
                                  <td key={s.id} className="px-2 py-2 text-center">
                                    {isFree ? (
                                      <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-semibold text-[11px] border border-emerald-500/20">
                                        Free
                                      </div>
                                    ) : isMaint ? (
                                      <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 font-semibold text-[10px] border border-amber-500/20 truncate" title={cell.reason}>
                                        Maintenance
                                      </div>
                                    ) : isBooking ? (
                                      <div className="p-1.5 rounded-lg bg-sky-500/10 text-sky-700 dark:text-sky-300 font-medium text-[10px] border border-sky-500/20" title={cell.purpose}>
                                        <span className="font-bold block truncate">{cell.requester_name || "Booked"}</span>
                                        <span className="opacity-75 block truncate">{cell.purpose}</span>
                                      </div>
                                    ) : isClass ? (
                                      <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-700 dark:text-purple-300 font-medium text-[10px] border border-purple-500/20" title={cell.subject}>
                                        <span className="font-bold block truncate">{cell.subject}</span>
                                        <span className="opacity-75 block truncate">{cell.faculty_name}</span>
                                      </div>
                                    ) : null}
                                  </td>
                                );
                              })}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState title="Schedule lookup ready" description="Select date and click 'Check Schedule' to inspect room allocations." />
            )}
          </div>
        )}

        {/* Add / Edit Timetable Entry Modal */}
        <Modal
          isOpen={entryModalOpen}
          onClose={() => setEntryModalOpen(false)}
          title={editingEntry ? "Edit Timetable Class" : "Schedule Weekly Class"}
          description="Map a subject and faculty member to a recurring weekly room & period."
          maxWidth="md"
        >
          <form onSubmit={handleSaveEntry} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Room *
              </label>
              <Select
                options={rooms.map((r) => ({ value: String(r.id), label: `${r.name} (${r.capacity} seats)` }))}
                value={entryForm.room_id}
                onChange={(e) => setEntryForm({ ...entryForm, room_id: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Day of Week *
                </label>
                <Select
                  options={DAYS_OF_WEEK.map((d) => ({ value: String(d.value), label: d.label }))}
                  value={entryForm.day_of_week}
                  onChange={(e) => setEntryForm({ ...entryForm, day_of_week: e.target.value })}
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Time Slot / Period *
                </label>
                <Select
                  options={timeSlots.map((s) => ({
                    value: String(s.id),
                    label: `${s.label} (${s.start_time.slice(0, 5)}-${s.end_time.slice(0, 5)})`,
                  }))}
                  value={entryForm.slot_id}
                  onChange={(e) => setEntryForm({ ...entryForm, slot_id: e.target.value })}
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Department Affiliation *
              </label>
              <Select
                options={departments.map((d) => ({ value: String(d.id), label: `${d.code} - ${d.name}` }))}
                value={entryForm.department_id}
                onChange={(e) => setEntryForm({ ...entryForm, department_id: e.target.value })}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Course / Subject Title *
              </label>
              <Input
                placeholder="e.g. Operating Systems & Linux Kernel"
                value={entryForm.subject}
                onChange={(e) => setEntryForm({ ...entryForm, subject: e.target.value })}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Faculty Instructor Name *
              </label>
              <Input
                placeholder="e.g. Prof. Sneha Deshpande"
                value={entryForm.faculty_name}
                onChange={(e) => setEntryForm({ ...entryForm, faculty_name: e.target.value })}
              />
            </div>

            <div className="flex justify-end gap-2.5 pt-4 border-t border-[var(--border)]">
              <Button type="button" variant="outline" onClick={() => setEntryModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={submitting} className="bg-sky-600 hover:bg-sky-700 text-white">
                Save Class
              </Button>
            </div>
          </form>
        </Modal>

        {/* Add / Edit Time Slot Modal */}
        <Modal
          isOpen={slotModalOpen}
          onClose={() => setSlotModalOpen(false)}
          title={editingSlot ? "Edit Period Slot" : "Add Time Slot"}
          description="Define standard scheduling period duration and order."
          maxWidth="sm"
        >
          <form onSubmit={handleSaveSlot} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Slot Label *
              </label>
              <Input
                placeholder="e.g. Period 1, Afternoon Slot"
                value={slotForm.label}
                onChange={(e) => setSlotForm({ ...slotForm, label: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Start Time (HH:MM) *
                </label>
                <Input
                  type="time"
                  value={slotForm.start_time}
                  onChange={(e) => setSlotForm({ ...slotForm, start_time: e.target.value })}
                />
              </div>
              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  End Time (HH:MM) *
                </label>
                <Input
                  type="time"
                  value={slotForm.end_time}
                  onChange={(e) => setSlotForm({ ...slotForm, end_time: e.target.value })}
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Display / Sorting Order
              </label>
              <Input
                type="number"
                value={slotForm.order}
                onChange={(e) => setSlotForm({ ...slotForm, order: parseInt(e.target.value, 10) || 1 })}
              />
            </div>

            <div className="flex justify-end gap-2.5 pt-4 border-t border-[var(--border)]">
              <Button type="button" variant="outline" onClick={() => setSlotModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={submitting} className="bg-sky-600 hover:bg-sky-700 text-white">
                Save Time Slot
              </Button>
            </div>
          </form>
        </Modal>

        {/* Timetable CSV Import Modal */}
        <Modal
          isOpen={csvModalOpen}
          onClose={() => setCsvModalOpen(false)}
          title="Import Timetable via CSV"
          description="Bulk schedule classes across multiple rooms and periods."
          maxWidth="lg"
        >
          <div className="space-y-4 pt-2">
            <div className="flex items-center justify-between p-3.5 rounded-xl bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800 text-xs text-sky-800 dark:text-sky-300">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-sky-600 shrink-0" />
                <span>Columns: room, day, slot, department, subject, faculty</span>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-1.5 shrink-0"
                onClick={handleDownloadSample}
              >
                <Download className="w-3.5 h-3.5" />
                Sample CSV
              </Button>
            </div>

            <form onSubmit={handleCsvImport} className="space-y-4">
              <div className="border-2 border-dashed border-[var(--border)] rounded-2xl p-6 text-center hover:border-sky-500/50 transition-colors">
                <input
                  type="file"
                  id="timetable-csv-file"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setCsvFile(f);
                  }}
                />
                <label htmlFor="timetable-csv-file" className="cursor-pointer block">
                  <Upload className="w-8 h-8 text-[var(--muted-foreground)] mx-auto mb-2" />
                  <span className="text-sm font-semibold text-[var(--foreground)] block">
                    {csvFile ? csvFile.name : "Select Timetable CSV file"}
                  </span>
                </label>
              </div>

              {csvResult && (
                <div className="p-4 rounded-xl border border-[var(--border)] bg-slate-50 dark:bg-slate-900 text-xs space-y-2">
                  <div className="flex items-center justify-between font-semibold">
                    <span>Processed: {csvResult.total_rows} rows</span>
                    <span className="text-emerald-600 dark:text-emerald-400">Imported: {csvResult.imported}</span>
                  </div>
                  {csvResult.errors?.length > 0 && (
                    <div className="pt-2 border-t border-[var(--border)] space-y-1">
                      <span className="text-rose-500 font-bold block">Errors:</span>
                      <div className="max-h-32 overflow-y-auto space-y-1 text-[11px] text-rose-600 dark:text-rose-400">
                        {csvResult.errors.map((err: any, idx: number) => (
                          <div key={idx}>Row {err.row}: {err.error}</div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="flex justify-end gap-2.5 pt-2 border-t border-[var(--border)]">
                <Button type="button" variant="outline" onClick={() => setCsvModalOpen(false)}>
                  Close
                </Button>
                <Button
                  type="submit"
                  disabled={!csvFile}
                  isLoading={submitting}
                  className="bg-sky-600 hover:bg-sky-700 text-white"
                >
                  Upload & Import
                </Button>
              </div>
            </form>
          </div>
        </Modal>

        {/* Delete Confirmation */}
        <ConfirmDialog
          isOpen={deleteConfirm.isOpen}
          onClose={() => setDeleteConfirm({ isOpen: false, type: "entry", id: 0, title: "" })}
          onConfirm={handleDeleteItem}
          title={deleteConfirm.title}
          message="Are you sure you want to delete this item? This action cannot be reversed."
          confirmText="Delete"
          variant="danger"
        />
      </div>
    </DashboardShell>
  );
}
