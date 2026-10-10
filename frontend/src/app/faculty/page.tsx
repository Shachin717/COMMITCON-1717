"use client";

import * as React from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import {
  Search,
  BookmarkCheck,
  RotateCw,
  Clock,
} from "lucide-react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { showToast } from "@/components/ui/toast";
import { apiClient } from "@/lib/api-client";
import {
  Booking,
  Block,
  Department,
  Facility,
  PaginatedResponse,
} from "@/lib/admin-types";
import {
  RoomSearchCard,
  TimeSlot,
} from "@/components/home/room-search-card";
import {
  RoomResultsGrid,
  AvailableRoom,
  AvailabilityData,
} from "@/components/home/room-results-grid";
import { BookingModal } from "@/components/home/booking-modal";

function getStatusBadgeVariant(status: string) {
  switch (status) {
    case "APPROVED":
      return "ACTIVE";
    case "COORDINATOR_APPROVED":
      return "INFO";
    case "PENDING":
      return "WARNING";
    case "REJECTED":
      return "INACTIVE";
    case "CANCELLED":
      return "DRAFT";
    case "RELOCATED":
      return "WARNING";
    default:
      return "DRAFT";
  }
}

function FacultyDashboardContent() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  // Tab State: book | my-bookings
  const activeTab = React.useMemo(() => {
    if (pathname === "/faculty/my-bookings") return "my-bookings";
    const currentTab = searchParams.get("tab");
    if (currentTab && ["book", "my-bookings"].includes(currentTab)) {
      return currentTab;
    }
    return "book";
  }, [pathname, searchParams]);

  const handleTabChange = (newTab: string) => {
    const route = newTab === "book" ? "/faculty" : `/faculty/${newTab}`;
    router.push(route);
  };

  // User Profile
  const [currentUser, setCurrentUser] = React.useState<any>(null);

  // Metadata
  const [blocks, setBlocks] = React.useState<Block[]>([]);
  const [departments, setDepartments] = React.useState<Department[]>([]);
  const [timeSlots, setTimeSlots] = React.useState<TimeSlot[]>([]);
  const [facilities, setFacilities] = React.useState<Facility[]>([]);

  // Real-time Pending / Active Badge State (polled every 30s)
  const [pendingCount, setPendingCount] = React.useState<number>(0);
  const [totalCount, setTotalCount] = React.useState<number>(0);

  // -------------------------------------------------------------
  // TAB 1: SEARCH & BOOKING EXPERIENCE (REUSING SHARED SEARCH & RESULTS)
  // -------------------------------------------------------------
  const todayStr = React.useMemo(() => new Date().toISOString().split("T")[0], []);
  const [searchDate, setSearchDate] = React.useState<string>(todayStr);
  const [selectedSlotIds, setSelectedSlotIds] = React.useState<number[]>([]);
  const [searchMinCapacity, setSearchMinCapacity] = React.useState<number>(40);
  const [searchRoomType, setSearchRoomType] = React.useState<string>("ALL");
  const [searchBlockId, setSearchBlockId] = React.useState<string>("all");
  const [searchDeptId, setSearchDeptId] = React.useState<string>("all");
  const [selectedFacilities, setSelectedFacilities] = React.useState<string[]>([]);

  const [availabilityResult, setAvailabilityResult] = React.useState<AvailabilityData | null>(null);
  const [searching, setSearching] = React.useState<boolean>(false);
  const [hasSearched, setHasSearched] = React.useState<boolean>(false);
  const [searchError, setSearchError] = React.useState<string | null>(null);

  // Booking Modal State (Prefilled with Faculty Details)
  const [bookingModalOpen, setBookingModalOpen] = React.useState<boolean>(false);
  const [bookingRoom, setBookingRoom] = React.useState<AvailableRoom | null>(null);
  const [bookingSlot, setBookingSlot] = React.useState<TimeSlot | null>(null);

  // -------------------------------------------------------------
  // TAB 2: MY BOOKINGS STATE
  // -------------------------------------------------------------
  const [myBookings, setMyBookings] = React.useState<Booking[]>([]);
  const [loadingMyBookings, setLoadingMyBookings] = React.useState<boolean>(false);
  const [statusFilter, setStatusFilter] = React.useState<string>("");
  const [searchKeyword, setSearchKeyword] = React.useState<string>("");

  // Cancel Booking State
  const [cancelConfirm, setCancelConfirm] = React.useState<{
    isOpen: boolean;
    booking: Booking | null;
  }>({ isOpen: false, booking: null });
  const [isCancelling, setIsCancelling] = React.useState<boolean>(false);

  // -------------------------------------------------------------
  // INITIAL FETCH & REAL-TIME POLLING
  // -------------------------------------------------------------
  const fetchProfileAndMetadata = React.useCallback(async () => {
    try {
      const [userRes, metaRes] = await Promise.all([
        apiClient("/api/auth/me").catch(() => null),
        apiClient<any>("/api/public/meta").catch(() => null),
      ]);

      if (userRes) {
        setCurrentUser(userRes);
      }

      if (metaRes) {
        const loadedSlots = metaRes.slots || metaRes.time_slots || [];
        setBlocks(metaRes.blocks || []);
        setDepartments(metaRes.departments || []);
        setTimeSlots(loadedSlots);
        setFacilities(metaRes.facilities || []);

        if (loadedSlots.length > 0 && selectedSlotIds.length === 0) {
          setSelectedSlotIds([loadedSlots[0].id]);
        }
      }
    } catch {
      // ignore
    }
  }, [selectedSlotIds.length]);

  // Polling for faculty pending bookings count every 30 seconds
  const pollFacultyStatus = React.useCallback(async () => {
    try {
      const res = await apiClient<{ pending_count: number; total_bookings: number }>(
        "/api/faculty/bookings/pending-count",
        { skipAuthRefresh: false }
      );
      if (res) {
        setPendingCount(res.pending_count);
        setTotalCount(res.total_bookings);
      }
    } catch {
      // ignore
    }
  }, []);

  React.useEffect(() => {
    fetchProfileAndMetadata();
    pollFacultyStatus();

    const interval = setInterval(() => {
      pollFacultyStatus();
    }, 30000); // 30 seconds poll

    return () => clearInterval(interval);
  }, [fetchProfileAndMetadata, pollFacultyStatus]);

  // -------------------------------------------------------------
  // TAB 1: EXECUTE AVAILABILITY SEARCH
  // -------------------------------------------------------------
  const executeSearch = React.useCallback(
    async (e?: React.FormEvent) => {
      if (e) e.preventDefault();
      if (!searchDate) return;
      setSearching(true);
      setHasSearched(true);
      setSearchError(null);
      try {
        const params: Record<string, any> = {
          date: searchDate,
        };
        if (selectedSlotIds.length > 0) {
          params.slot_ids = selectedSlotIds.join(",");
        }
        if (searchMinCapacity > 0) {
          params.min_capacity = searchMinCapacity;
        }
        if (searchRoomType && searchRoomType !== "ALL") {
          params.room_type = searchRoomType;
        }
        if (searchBlockId && searchBlockId !== "all") {
          params.block_id = Number(searchBlockId);
        }
        if (searchDeptId && searchDeptId !== "all") {
          params.department_id = Number(searchDeptId);
        }
        if (selectedFacilities.length > 0) {
          params.facilities = selectedFacilities.join(",");
        }

        let res: AvailabilityData;
        try {
          res = await apiClient<AvailabilityData>("/api/faculty/availability", {
            params,
            credentials: "include",
          });
        } catch {
          // Fallback to public availability endpoint with credentials included
          res = await apiClient<AvailabilityData>("/api/public/availability", {
            params,
            credentials: "include",
          });
        }

        setAvailabilityResult(res);
      } catch (err: any) {
        const msg = err.message || "Failed to search room availability.";
        setSearchError(msg);
        showToast({
          title: "Search Failed",
          message: msg,
          type: "error",
        });
      } finally {
        setSearching(false);
      }
    },
    [
      searchDate,
      selectedSlotIds,
      searchMinCapacity,
      searchRoomType,
      searchBlockId,
      searchDeptId,
      selectedFacilities,
    ]
  );

  // Initial auto-search once slots are loaded
  React.useEffect(() => {
    if (activeTab === "book" && timeSlots.length > 0 && selectedSlotIds.length > 0 && !hasSearched) {
      executeSearch();
    }
  }, [activeTab, timeSlots, selectedSlotIds, hasSearched, executeSearch]);

  const toggleSlotId = (slotId: number) => {
    setSelectedSlotIds((prev) =>
      prev.includes(slotId)
        ? prev.length > 1
          ? prev.filter((id) => id !== slotId)
          : prev
        : [...prev, slotId]
    );
  };

  const toggleFacility = (facilityName: string) => {
    setSelectedFacilities((prev) =>
      prev.includes(facilityName)
        ? prev.filter((f) => f !== facilityName)
        : [...prev, facilityName]
    );
  };

  const openBookingModalForRoom = (room: AvailableRoom) => {
    setBookingRoom(room);
    const targetSlot =
      timeSlots.find((s) => s.id === (selectedSlotIds[0] || (timeSlots[0]?.id ?? 1))) ||
      timeSlots[0] ||
      null;
    setBookingSlot(targetSlot);
    setBookingModalOpen(true);
  };

  // -------------------------------------------------------------
  // TAB 2: FETCH MY BOOKINGS & CANCEL
  // -------------------------------------------------------------
  const fetchMyBookings = React.useCallback(async () => {
    setLoadingMyBookings(true);
    try {
      const params: Record<string, any> = { page_size: 50 };
      if (statusFilter) params.status = statusFilter;
      if (searchKeyword.trim()) params.search = searchKeyword.trim();

      const res = await apiClient<PaginatedResponse<Booking>>("/api/faculty/bookings", {
        params,
      });
      setMyBookings(res.items || []);
    } catch (err: any) {
      showToast({
        title: "Error loading bookings",
        message: err.message || "Could not retrieve your bookings",
        type: "error",
      });
    } finally {
      setLoadingMyBookings(false);
    }
  }, [statusFilter, searchKeyword]);

  React.useEffect(() => {
    if (activeTab === "my-bookings") {
      fetchMyBookings();
    }
  }, [activeTab, fetchMyBookings]);

  const handleCancelBooking = async () => {
    if (!cancelConfirm.booking) return;
    setIsCancelling(true);
    try {
      await apiClient(`/api/faculty/bookings/${cancelConfirm.booking.id}/cancel`, {
        method: "POST",
      });
      showToast({
        title: "Booking Cancelled",
        message: `Reservation ${cancelConfirm.booking.reference} cancelled and slot released.`,
        type: "info",
      });
      setCancelConfirm({ isOpen: false, booking: null });
      fetchMyBookings();
      pollFacultyStatus();
      if (hasSearched) {
        executeSearch();
      }
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

  const getSlot = (id: number) => timeSlots.find((s) => s.id === id);

  return (
    <DashboardShell
      role="FACULTY"
      userName={currentUser?.name || "Faculty Member"}
      userEmail={currentUser?.email || "faculty@college.edu"}
      notificationCount={pendingCount}
      notificationLabel="pending bookings"
    >
      <div className="space-y-6 pb-16">
        {/* Top Header & Real-time Notification Banner */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-[var(--foreground)]">
                Faculty Academic Portal
              </h1>
              {pendingCount > 0 && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-300 animate-pulse">
                  <Clock className="w-3.5 h-3.5" />
                  {pendingCount} Pending Approval
                </span>
              )}
            </div>
            <p className="text-sm text-[var(--muted-foreground)] mt-0.5">
              Search classroom & lab availability, schedule lectures with prefilled credentials, and track your active academic allocations.
            </p>
          </div>

          {/* Quick Refresh */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                pollFacultyStatus();
                if (activeTab === "book") executeSearch();
                if (activeTab === "my-bookings") fetchMyBookings();
                showToast({ title: "Refreshed", message: "Data reloaded successfully", type: "info" });
              }}
              className="gap-2"
            >
              <RotateCw className="w-3.5 h-3.5" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="border-b border-[var(--border)]">
          <div className="flex gap-2 pb-px">
            <button
              onClick={() => handleTabChange("book")}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${
                activeTab === "book"
                  ? "border-sky-600 text-sky-600 dark:text-sky-400"
                  : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              <Search className="w-4 h-4" />
              <span>Search & Reserve Room</span>
            </button>

            <button
              onClick={() => handleTabChange("my-bookings")}
              className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all ${
                activeTab === "my-bookings"
                  ? "border-sky-600 text-sky-600 dark:text-sky-400"
                  : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              <BookmarkCheck className="w-4 h-4" />
              <span>My Bookings</span>
              {pendingCount > 0 && (
                <span className="px-2 py-0.5 text-[10px] font-extrabold rounded-full bg-amber-500 text-white animate-pulse">
                  {pendingCount}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* TAB 1: REUSABLE SEARCH & RESULTS EXPERIENCE PREFILLED FOR FACULTY */}
        {/* ========================================================================= */}
        {activeTab === "book" && (
          <div className="space-y-6">
            <RoomSearchCard
              searchDate={searchDate}
              onDateChange={setSearchDate}
              selectedSlotIds={selectedSlotIds}
              onToggleSlotId={toggleSlotId}
              slots={timeSlots}
              expectedStrength={searchMinCapacity}
              onStrengthChange={setSearchMinCapacity}
              selectedRoomType={searchRoomType}
              onRoomTypeChange={setSearchRoomType}
              blocks={blocks}
              selectedBlockId={searchBlockId}
              onBlockChange={setSearchBlockId}
              departments={departments}
              selectedDepartmentId={searchDeptId}
              onDepartmentChange={setSearchDeptId}
              facilities={facilities}
              selectedFacilities={selectedFacilities}
              onToggleFacility={toggleFacility}
              onSearch={executeSearch}
              isSearching={searching}
              cardTitle="Search Available Venues"
              cardSubtitle="Filter by date, class period, required facilities, and minimum capacity."
              isFaculty={true}
            />

            <RoomResultsGrid
              hasSearched={hasSearched}
              isSearching={searching}
              searchDate={searchDate}
              slots={timeSlots}
              selectedSlotIds={selectedSlotIds}
              expectedStrength={searchMinCapacity}
              searchResults={availabilityResult}
              error={searchError}
              onRetry={executeSearch}
              onBookRoom={openBookingModalForRoom}
              onSelectSlot={(slotId) => {
                setSelectedSlotIds([slotId]);
                setTimeout(() => executeSearch(), 50);
              }}
              isFaculty={true}
            />
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: MY BOOKINGS (WITH STATUS BADGE & ONE-CLICK CANCEL OPTION) */}
        {/* ========================================================================= */}
        {activeTab === "my-bookings" && (
          <div className="space-y-4">
            {/* Filter Toolbar */}
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3 flex-1 max-w-md">
                <Input
                  placeholder="Search reference or purpose..."
                  icon={<Search className="w-4 h-4" />}
                  value={searchKeyword}
                  onChange={(e) => setSearchKeyword(e.target.value)}
                />
              </div>

              <div className="w-48">
                <Select
                  options={[
                    { value: "", label: "All Statuses" },
                    { value: "APPROVED", label: "Approved / Active" },
                    { value: "COORDINATOR_APPROVED", label: "Coordinator Approved" },
                    { value: "PENDING", label: "Pending Verification" },
                    { value: "RELOCATED", label: "Relocated" },
                    { value: "REJECTED", label: "Rejected" },
                    { value: "CANCELLED", label: "Cancelled" },
                  ]}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                />
              </div>
            </div>

            {/* Bookings Table */}
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-[var(--foreground)]">
                  <thead className="border-b border-[var(--border)] bg-slate-50/75 dark:bg-slate-900/40 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                    <tr>
                      <th className="px-5 py-3.5">Reference</th>
                      <th className="px-5 py-3.5">Room & Venue</th>
                      <th className="px-5 py-3.5">Date & Time Slot</th>
                      <th className="px-5 py-3.5">Attendance</th>
                      <th className="px-5 py-3.5">Purpose</th>
                      <th className="px-5 py-3.5">Status</th>
                      <th className="px-5 py-3.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {loadingMyBookings ? (
                      Array.from({ length: 4 }).map((_, i) => (
                        <tr key={i}>
                          <td colSpan={7} className="px-5 py-4">
                            <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
                          </td>
                        </tr>
                      ))
                    ) : myBookings.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="p-8">
                          <EmptyState
                            title="No bookings recorded"
                            description="You have not submitted any room reservations yet."
                            action={{
                              label: "Search & Book a Room",
                              onClick: () => handleTabChange("book"),
                            }}
                          />
                        </td>
                      </tr>
                    ) : (
                      myBookings.map((b) => {
                        const slot = getSlot(b.slot_id);
                        const canCancel = ["PENDING", "COORDINATOR_APPROVED", "APPROVED", "RELOCATED"].includes(b.status);

                        return (
                          <tr key={b.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30 transition-colors">
                            <td className="px-5 py-3.5">
                              <span className="font-mono text-xs font-bold text-sky-600 dark:text-sky-400">
                                {b.reference}
                              </span>
                              <span className="text-[11px] text-[var(--muted-foreground)] block">
                                {new Date(b.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}
                              </span>
                            </td>
                            <td className="px-5 py-3.5">
                              <span className="font-bold text-[var(--foreground)]">
                                {(b as any).room?.name || `#${b.room_id}`}
                              </span>
                              <span className="text-xs text-[var(--muted-foreground)] block">
                                {(b as any).room?.block?.name || "Campus Block"}
                              </span>
                            </td>
                            <td className="px-5 py-3.5 text-xs">
                              <span className="font-semibold text-[var(--foreground)] block">{b.date}</span>
                              <span className="text-[var(--muted-foreground)]">
                                {slot ? `${slot.label} (${slot.start_time.slice(0, 5)})` : `#${b.slot_id}`}
                              </span>
                            </td>
                            <td className="px-5 py-3.5 text-xs text-[var(--foreground)]">
                              {b.expected_strength} persons
                            </td>
                            <td className="px-5 py-3.5 text-xs max-w-xs truncate text-[var(--foreground)]">
                              {b.purpose}
                            </td>
                            <td className="px-5 py-3.5">
                              <StatusBadge
                                status={getStatusBadgeVariant(b.status)}
                                label={b.status.replace(/_/g, " ")}
                              />
                              {b.decision_note && (
                                <span className="text-[10px] text-amber-600 dark:text-amber-400 block max-w-xs truncate mt-0.5">
                                  {b.decision_note}
                                </span>
                              )}
                            </td>
                            <td className="px-5 py-3.5 text-right">
                              {canCancel ? (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="h-8 px-2.5 text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/40 border-rose-200 dark:border-rose-900"
                                  onClick={() => setCancelConfirm({ isOpen: true, booking: b })}
                                >
                                  Cancel Booking
                                </Button>
                              ) : (
                                <span className="text-xs text-[var(--muted-foreground)]">—</span>
                              )}
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
      </div>

      {/* ========================================================================= */}
      {/* SHARED BOOKING MODAL PREFILLED WITH FACULTY CREDENTIALS */}
      {/* ========================================================================= */}
      <BookingModal
        isOpen={bookingModalOpen}
        onClose={() => setBookingModalOpen(false)}
        room={bookingRoom}
        date={searchDate}
        slot={bookingSlot}
        departments={departments}
        expectedStrength={searchMinCapacity}
        isFaculty={true}
        initialValues={{
          faculty_id: currentUser ? `FAC-${currentUser.id}` : "FAC-1",
          roll_no: currentUser ? `FAC-${currentUser.id}` : "FAC-1",
          name: currentUser?.name || "",
          email: currentUser?.email || "",
          phone: currentUser?.phone || "+91 9876543230",
          department_id: bookingRoom?.department_id || currentUser?.department_id || (departments[0]?.id ?? 1),
          class_name: "Academic Session",
          expected_strength: Math.min(bookingRoom?.capacity || 200, searchMinCapacity || 40),
        }}
        onBookingSuccess={() => {
          pollFacultyStatus();
          fetchMyBookings();
          executeSearch();
        }}
      />

      {/* ========================================================================= */}
      {/* CANCEL BOOKING CONFIRMATION DIALOG */}
      {/* ========================================================================= */}
      <ConfirmDialog
        isOpen={cancelConfirm.isOpen}
        onClose={() => setCancelConfirm({ isOpen: false, booking: null })}
        title={`Cancel Booking ${cancelConfirm.booking?.reference}?`}
        message="This will release the reserved room and time slot immediately, updating its status to CANCELLED."
        confirmText="Confirm Cancellation"
        variant="danger"
        isLoading={isCancelling}
        onConfirm={handleCancelBooking}
      />
    </DashboardShell>
  );
}

export default function FacultyDashboardPage() {
  return (
    <React.Suspense
      fallback={
        <div className="min-h-screen bg-[var(--background)] flex items-center justify-center p-8">
          <div className="flex items-center gap-3 text-sm text-[var(--muted-foreground)]">
            <div className="h-5 w-5 border-2 border-sky-500 border-t-transparent rounded-full animate-spin" />
            <span>Loading faculty portal...</span>
          </div>
        </div>
      }
    >
      <FacultyDashboardContent />
    </React.Suspense>
  );
}
