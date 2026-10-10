"use client";

import * as React from "react";
import {
  History,
  Search,
  RotateCw,
  Download,
  Calendar,
  Clock,
  DoorOpen,
  User,
  ShieldCheck,
  Building2,
  FileText,
  X,
  ExternalLink,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Sparkles,
} from "lucide-react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { EmptyState } from "@/components/ui/empty-state";
import { showToast } from "@/components/ui/toast";
import { apiClient } from "@/lib/api-client";
import {
  Booking,
  BookingStatus,
  RequesterType,
  Room,
  Department,
  Block,
  TimeSlot,
  PaginatedResponse,
} from "@/lib/admin-types";

export default function AdminBookingsPage() {
  const [bookings, setBookings] = React.useState<Booking[]>([]);
  const [rooms, setRooms] = React.useState<Room[]>([]);
  const [departments, setDepartments] = React.useState<Department[]>([]);
  const [blocks, setBlocks] = React.useState<Block[]>([]);
  const [timeSlots, setTimeSlots] = React.useState<TimeSlot[]>([]);

  const [loading, setLoading] = React.useState(true);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [pageSize] = React.useState(15);

  // Filters
  const [search, setSearch] = React.useState("");
  const [debouncedSearch, setDebouncedSearch] = React.useState("");

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const [statusFilter, setStatusFilter] = React.useState<string>("");
  const [requesterTypeFilter, setRequesterTypeFilter] = React.useState<string>("");
  const [roomFilter, setRoomFilter] = React.useState<string>("");
  const [blockFilter, setBlockFilter] = React.useState<string>("");
  const [deptFilter, setDeptFilter] = React.useState<string>("");
  const [dateFrom, setDateFrom] = React.useState<string>("");
  const [dateTo, setDateTo] = React.useState<string>("");

  // Detail Drawer state
  const [selectedBooking, setSelectedBooking] = React.useState<Booking | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  // Fetch metadata
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
    } catch {
      // ignore
    }
  }, []);

  // Fetch bookings
  const fetchBookings = React.useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        page_size: pageSize,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (statusFilter) params.status = statusFilter;
      if (requesterTypeFilter) params.requester_type = requesterTypeFilter;
      if (roomFilter) params.room_id = roomFilter;
      if (blockFilter) params.block_id = blockFilter;
      if (deptFilter) params.department_id = deptFilter;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;

      const res = await apiClient<PaginatedResponse<Booking>>("/api/admin/bookings", {
        params,
      });
      setBookings(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      showToast({
        title: "Error loading bookings",
        message: err.message || "Failed to load booking history",
        type: "error",
      });
    } finally {
      setLoading(false);
    }
  }, [
    page,
    pageSize,
    debouncedSearch,
    statusFilter,
    requesterTypeFilter,
    roomFilter,
    blockFilter,
    deptFilter,
    dateFrom,
    dateTo,
  ]);

  React.useEffect(() => {
    fetchMetadata();
  }, [fetchMetadata]);

  React.useEffect(() => {
    fetchBookings();
  }, [fetchBookings]);

  // CSV Export
  const handleExportCsv = () => {
    const searchParams = new URLSearchParams();
    if (search.trim()) searchParams.append("search", search.trim());
    if (statusFilter) searchParams.append("status", statusFilter);
    if (requesterTypeFilter) searchParams.append("requester_type", requesterTypeFilter);
    if (roomFilter) searchParams.append("room_id", roomFilter);
    if (blockFilter) searchParams.append("block_id", blockFilter);
    if (deptFilter) searchParams.append("department_id", deptFilter);
    if (dateFrom) searchParams.append("date_from", dateFrom);
    if (dateTo) searchParams.append("date_to", dateTo);

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const exportUrl = `${baseUrl}/api/admin/bookings/export-csv?${searchParams.toString()}`;

    // Trigger download
    const link = document.createElement("a");
    link.href = exportUrl;
    link.setAttribute("download", `bookings_export_${new Date().toISOString().split("T")[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast({
      title: "Export Initiated",
      message: "Downloading booking records CSV.",
      type: "info",
    });
  };

  // Open drawer
  const openDrawer = (b: Booking) => {
    setSelectedBooking(b);
    setDrawerOpen(true);
  };

  // Helpers
  const getRoom = (roomId: number) => rooms.find((r) => r.id === roomId);
  const getDept = (deptId: number) => departments.find((d) => d.id === deptId);
  const getSlot = (slotId: number) => timeSlots.find((s) => s.id === slotId);

  const getStatusBadgeVariant = (status: BookingStatus) => {
    switch (status) {
      case "APPROVED":
        return "ACTIVE";
      case "COORDINATOR_APPROVED":
        return "INFO";
      case "PENDING":
        return "MAINTENANCE";
      case "REJECTED":
        return "REJECTED";
      case "CANCELLED":
        return "CANCELLED";
      default:
        return "INFO";
    }
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
              Booking History & Audit Dossier
            </h1>
            <p className="text-sm text-[var(--muted-foreground)]">
              Track historical and active room bookings, filter by requester, status, and department, and export audit CSVs.
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchBookings}
              isLoading={loading}
              className="gap-2"
            >
              <RotateCw className="w-4 h-4" />
              Refresh
            </Button>
            <Button
              size="sm"
              onClick={handleExportCsv}
              className="gap-2 bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </Button>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <Input
              placeholder="Search reference, name, roll no, purpose..."
              icon={<Search className="w-4 h-4" />}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
            <Select
              options={[
                { value: "", label: "All Statuses" },
                { value: "PENDING", label: "Pending Verification" },
                { value: "COORDINATOR_APPROVED", label: "Coordinator Approved" },
                { value: "APPROVED", label: "Confirmed / Approved" },
                { value: "REJECTED", label: "Rejected" },
                { value: "CANCELLED", label: "Cancelled" },
              ]}
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
            />
            <Select
              options={[
                { value: "", label: "All Requesters" },
                { value: "STUDENT", label: "Student Bookings" },
                { value: "FACULTY", label: "Faculty Bookings" },
              ]}
              value={requesterTypeFilter}
              onChange={(e) => {
                setRequesterTypeFilter(e.target.value);
                setPage(1);
              }}
            />
            <Select
              options={[
                { value: "", label: "All Rooms" },
                ...rooms.map((r) => ({ value: String(r.id), label: r.name })),
              ]}
              value={roomFilter}
              onChange={(e) => {
                setRoomFilter(e.target.value);
                setPage(1);
              }}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2 border-t border-[var(--border)]">
            <Select
              options={[
                { value: "", label: "All Blocks" },
                ...blocks.map((b) => ({ value: String(b.id), label: b.name })),
              ]}
              value={blockFilter}
              onChange={(e) => {
                setBlockFilter(e.target.value);
                setPage(1);
              }}
            />
            <Select
              options={[
                { value: "", label: "All Departments" },
                ...departments.map((d) => ({ value: String(d.id), label: `${d.code} - ${d.name}` })),
              ]}
              value={deptFilter}
              onChange={(e) => {
                setDeptFilter(e.target.value);
                setPage(1);
              }}
            />
            <div>
              <Input
                type="date"
                placeholder="Date From"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setPage(1);
                }}
              />
            </div>
            <div>
              <Input
                type="date"
                placeholder="Date To"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setPage(1);
                }}
              />
            </div>
          </div>
        </div>

        {/* Bookings Table */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-[var(--foreground)]">
              <thead className="border-b border-[var(--border)] bg-slate-50/75 dark:bg-slate-900/40 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Reference</th>
                  <th className="px-5 py-3.5">Requester</th>
                  <th className="px-5 py-3.5">Room</th>
                  <th className="px-5 py-3.5">Date & Slot</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">Decision Note</th>
                  <th className="px-5 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {loading ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={7} className="px-5 py-4">
                        <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                ) : bookings.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-8">
                      <EmptyState
                        title="No booking records found"
                        description="Adjust date range or keyword filters to browse past allocations."
                        action={{
                          label: "Reset Filters",
                          onClick: () => {
                            setSearch("");
                            setStatusFilter("");
                            setRequesterTypeFilter("");
                            setRoomFilter("");
                            setBlockFilter("");
                            setDeptFilter("");
                            setDateFrom("");
                            setDateTo("");
                            setPage(1);
                          },
                        }}
                      />
                    </td>
                  </tr>
                ) : (
                  bookings.map((booking) => {
                    const room = getRoom(booking.room_id);
                    const slot = getSlot(booking.slot_id);

                    return (
                      <tr
                        key={booking.id}
                        onClick={() => openDrawer(booking)}
                        className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30 transition-colors cursor-pointer"
                      >
                        <td className="px-5 py-3.5">
                          <span className="font-mono text-xs font-bold text-sky-600 dark:text-sky-400">
                            {booking.reference}
                          </span>
                          <span className="text-[11px] text-[var(--muted-foreground)] block">
                            {new Date(booking.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}
                          </span>
                        </td>
                        <td className="px-5 py-3.5">
                          <div className="font-semibold text-[var(--foreground)]">{booking.name}</div>
                          <div className="text-xs text-[var(--muted-foreground)] flex items-center gap-1.5">
                            <span className="capitalize">{booking.requester_type.toLowerCase()}</span>
                            {booking.roll_no && <span>• {booking.roll_no}</span>}
                          </div>
                        </td>
                        <td className="px-5 py-3.5">
                          <span className="font-bold text-[var(--foreground)]">{room?.name || `#${booking.room_id}`}</span>
                          <span className="text-xs text-[var(--muted-foreground)] block">{room?.room_type}</span>
                        </td>
                        <td className="px-5 py-3.5 text-xs">
                          <span className="font-semibold text-[var(--foreground)] block">{booking.date}</span>
                          <span className="text-[var(--muted-foreground)]">
                            {slot ? `${slot.label} (${slot.start_time.slice(0, 5)})` : `#${booking.slot_id}`}
                          </span>
                        </td>
                        <td className="px-5 py-3.5">
                          <StatusBadge
                            status={getStatusBadgeVariant(booking.status)}
                            label={booking.status.replace(/_/g, " ")}
                          />
                        </td>
                        <td className="px-5 py-3.5 text-xs text-[var(--muted-foreground)] max-w-xs truncate">
                          {booking.decision_note || "—"}
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 text-xs text-sky-600 hover:text-sky-700"
                            onClick={(e) => {
                              e.stopPropagation();
                              openDrawer(booking);
                            }}
                          >
                            Details
                          </Button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {total > pageSize && (
            <div className="p-4 border-t border-[var(--border)] flex items-center justify-between text-xs text-[var(--muted-foreground)]">
              <span>Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {total} bookings</span>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                  Previous
                </Button>
                <Button variant="outline" size="sm" disabled={page >= Math.ceil(total / pageSize)} onClick={() => setPage((p) => p + 1)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* DETAIL DRAWER */}
        {drawerOpen && selectedBooking && (
          <div className="fixed inset-0 z-50 flex justify-end">
            {/* Backdrop */}
            <div
              className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
              onClick={() => setDrawerOpen(false)}
            />

            {/* Slide-over Drawer Panel */}
            <div className="relative z-10 w-full max-w-lg bg-[var(--card)] border-l border-[var(--border)] shadow-2xl h-full flex flex-col p-6 overflow-y-auto">
              {/* Drawer Header */}
              <div className="flex items-center justify-between pb-4 border-b border-[var(--border)]">
                <div>
                  <span className="font-mono text-xs font-bold text-sky-600 dark:text-sky-400">
                    {selectedBooking.reference}
                  </span>
                  <h2 className="text-lg font-bold text-[var(--foreground)] mt-0.5">
                    Booking Dossier
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={() => setDrawerOpen(false)}
                  className="p-1.5 rounded-lg text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Drawer Content */}
              <div className="space-y-6 py-6 flex-1 text-sm">
                {/* Status Box */}
                <div className="p-4 rounded-xl border border-[var(--border)] bg-slate-50 dark:bg-slate-900 flex items-center justify-between">
                  <div>
                    <span className="text-xs text-[var(--muted-foreground)] block">Lifecycle Status</span>
                    <span className="font-bold text-[var(--foreground)]">{selectedBooking.status.replace(/_/g, " ")}</span>
                  </div>
                  <StatusBadge
                    status={getStatusBadgeVariant(selectedBooking.status)}
                    label={selectedBooking.status}
                  />
                </div>

                {/* Requester Dossier */}
                <div className="space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                    Requester Information
                  </h3>
                  <div className="p-4 rounded-xl border border-[var(--border)] space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Name:</span>
                      <span className="font-semibold text-[var(--foreground)]">{selectedBooking.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Email:</span>
                      <span className="font-medium text-[var(--foreground)]">{selectedBooking.email}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Phone:</span>
                      <span className="font-medium text-[var(--foreground)]">{selectedBooking.phone}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Affiliation:</span>
                      <span className="font-medium text-[var(--foreground)]">{selectedBooking.requester_type}</span>
                    </div>
                    {selectedBooking.roll_no && (
                      <div className="flex justify-between">
                        <span className="text-[var(--muted-foreground)]">Roll No:</span>
                        <span className="font-medium text-[var(--foreground)]">{selectedBooking.roll_no}</span>
                      </div>
                    )}
                    {selectedBooking.class_name && (
                      <div className="flex justify-between">
                        <span className="text-[var(--muted-foreground)]">Class / Section:</span>
                        <span className="font-medium text-[var(--foreground)]">{selectedBooking.class_name}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Department:</span>
                      <span className="font-medium text-[var(--foreground)]">{getDept(selectedBooking.department_id)?.name || `#${selectedBooking.department_id}`}</span>
                    </div>
                  </div>
                </div>

                {/* Reservation Details */}
                <div className="space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                    Room & Time Reservation
                  </h3>
                  <div className="p-4 rounded-xl border border-[var(--border)] space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Allocated Room:</span>
                      <span className="font-bold text-[var(--foreground)]">{getRoom(selectedBooking.room_id)?.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Room Category:</span>
                      <span className="font-medium text-[var(--foreground)]">{getRoom(selectedBooking.room_id)?.room_type}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Date:</span>
                      <span className="font-semibold text-[var(--foreground)]">{selectedBooking.date}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Time Slot:</span>
                      <span className="font-semibold text-sky-600 dark:text-sky-400">
                        {getSlot(selectedBooking.slot_id)?.label} ({getSlot(selectedBooking.slot_id)?.start_time.slice(0, 5)} - {getSlot(selectedBooking.slot_id)?.end_time.slice(0, 5)})
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Expected Attendees:</span>
                      <span className="font-semibold text-[var(--foreground)]">{selectedBooking.expected_strength} persons</span>
                    </div>
                    <div className="pt-2 border-t border-[var(--border)]">
                      <span className="text-[var(--muted-foreground)] block mb-1">Event Purpose:</span>
                      <p className="font-medium text-[var(--foreground)] bg-slate-50 dark:bg-slate-900 p-2.5 rounded-lg">
                        {selectedBooking.purpose}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Required Facilities */}
                {selectedBooking.required_facilities && selectedBooking.required_facilities.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                      Requested Facilities
                    </h3>
                    <div className="flex flex-wrap gap-1.5">
                      {selectedBooking.required_facilities.map((fac, idx) => (
                        <span
                          key={idx}
                          className="px-2.5 py-1 rounded-full text-xs font-medium bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-500/20"
                        >
                          {fac}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Approval Audit Trail */}
                <div className="space-y-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                    Approval History & Decisions
                  </h3>
                  <div className="p-4 rounded-xl border border-[var(--border)] bg-slate-50 dark:bg-slate-900 text-xs space-y-2">
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Requires HOD Sign-off:</span>
                      <span className="font-semibold">{selectedBooking.requires_hod_approval ? "Yes" : "No"}</span>
                    </div>
                    {selectedBooking.decided_by && (
                      <div className="flex justify-between">
                        <span className="text-[var(--muted-foreground)]">Decided By (User ID):</span>
                        <span className="font-semibold">User #{selectedBooking.decided_by}</span>
                      </div>
                    )}
                    {selectedBooking.decision_note && (
                      <div>
                        <span className="text-[var(--muted-foreground)] block mb-1">Decision Note:</span>
                        <p className="p-2 rounded bg-[var(--card)] border border-[var(--border)] italic">
                          "{selectedBooking.decision_note}"
                        </p>
                      </div>
                    )}
                    <div className="flex justify-between pt-2 border-t border-[var(--border)] text-[11px] text-[var(--muted-foreground)]">
                      <span>Submitted at:</span>
                      <span>{new Date(selectedBooking.created_at).toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Drawer Footer */}
              <div className="pt-4 border-t border-[var(--border)] flex justify-end">
                <Button variant="outline" onClick={() => setDrawerOpen(false)}>
                  Close Dossier
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
