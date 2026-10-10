"use client";

import * as React from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import {
  Clock,
  LayoutDashboard,
  Boxes,
  ShieldAlert,
  History,
  CalendarDays,
  CheckCircle2,
  XCircle,
  RotateCw,
  Search,
  Filter,
  CheckSquare,
  Square,
  AlertTriangle,
  ArrowRight,
  Eye,
  Lock,
  Download,
  Calendar,
  Building2,
  DoorOpen,
  User,
  ShieldCheck,
  FileText,
  X,
  Sparkles,
  Info,
  RefreshCw,
  Ban,
  Layers,
  Unlock,
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
import { AllocationInsightsView } from "@/components/allocation/allocation-insights-view";
import { BlockedRoomsView } from "@/components/coordinator/blocked-rooms-view";
import {
  Booking,
  BookingStatus,
  Room,
  CoordinatorRoom,
  Department,
  Block,
  TimeSlot,
  PaginatedResponse,
  BlockOverviewResponse,
  BlockOverviewRoom,
  RoomBlockPreviewResponse,
  AffectedBookingItem,
  BlockedRoomItem,
  BlockedRoomsSummaryCounts,
} from "@/lib/admin-types";

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

function formatErrorMessage(err: any, fallback = "An unexpected error occurred"): string {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  if (typeof err.message === "string" && err.message.trim() && err.message !== "[object Object]") {
    return err.message;
  }
  if (err.detail) {
    if (typeof err.detail === "string") return err.detail;
    if (Array.isArray(err.detail)) {
      return err.detail
        .map((d: any) => (typeof d === "string" ? d : d.msg || JSON.stringify(d)))
        .join("; ");
    }
    if (typeof err.detail === "object") {
      try {
        return JSON.stringify(err.detail);
      } catch {
        return fallback;
      }
    }
  }
  if (typeof err === "object") {
    try {
      const json = JSON.stringify(err);
      if (json !== "{}") return json;
    } catch {
      return fallback;
    }
  }
  return String(err);
}

function CoordinatorDashboardContent() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();

  // Tab State: pending | overview | block-room | history | timetable | allocation
  const activeTab = React.useMemo(() => {
    if (pathname === "/coordinator/overview") return "overview";
    if (pathname === "/coordinator/block-room") return "block-room";
    if (pathname === "/coordinator/history") return "history";
    if (pathname === "/coordinator/timetable") return "timetable";
    if (pathname === "/coordinator/allocation") return "allocation";
    const currentTab = searchParams.get("tab");
    if (currentTab && ["pending", "overview", "block-room", "history", "timetable", "allocation"].includes(currentTab)) {
      return currentTab;
    }
    return "pending";
  }, [pathname, searchParams]);

  const handleTabChange = (newTab: string) => {
    const route = newTab === "pending" ? "/coordinator" : `/coordinator/${newTab}`;
    router.push(route);
  };

  // User Profile
  const [currentUser, setCurrentUser] = React.useState<any>(null);

  // Metadata
  const [rooms, setRooms] = React.useState<CoordinatorRoom[]>([]);
  const [blocks, setBlocks] = React.useState<Block[]>([]);
  const [departments, setDepartments] = React.useState<Department[]>([]);
  const [timeSlots, setTimeSlots] = React.useState<TimeSlot[]>([]);

  // Real-time Pending Badge State (polled every 30s)
  const [pendingCount, setPendingCount] = React.useState<number>(0);

  // Detail Drawer State (shared across pending & history)
  const [selectedBooking, setSelectedBooking] = React.useState<Booking | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState<boolean>(false);

  // Reject Modal State
  const [rejectModalOpen, setRejectModalOpen] = React.useState<boolean>(false);
  const [rejectingBookingId, setRejectingBookingId] = React.useState<number | null>(null);
  const [rejectionReason, setRejectionReason] = React.useState<string>("");
  const [rejectionError, setRejectionError] = React.useState<string>("");
  const [isRejecting, setIsRejecting] = React.useState<boolean>(false);

  // -------------------------------------------------------------
  // TAB 1: PENDING INBOX STATE
  // -------------------------------------------------------------
  const [pendingBookings, setPendingBookings] = React.useState<Booking[]>([]);
  const [loadingPending, setLoadingPending] = React.useState<boolean>(true);
  const [selectedPendingIds, setSelectedPendingIds] = React.useState<number[]>([]);
  const [pendingSearch, setPendingSearch] = React.useState<string>("");
  const [debouncedPendingSearch, setDebouncedPendingSearch] = React.useState<string>("");

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedPendingSearch(pendingSearch.trim());
    }, 300);
    return () => clearTimeout(timer);
  }, [pendingSearch]);

  const [bulkConfirmOpen, setBulkConfirmOpen] = React.useState<boolean>(false);
  const [isBulkApproving, setIsBulkApproving] = React.useState<boolean>(false);

  // -------------------------------------------------------------
  // TAB 2: ALL-BLOCKS OVERVIEW STATE
  // -------------------------------------------------------------
  const [overviewDate, setOverviewDate] = React.useState<string>(() => {
    return new Date().toISOString().split("T")[0];
  });
  const [overviewSlotId, setOverviewSlotId] = React.useState<string>("");
  const [overviewData, setOverviewData] = React.useState<BlockOverviewResponse | null>(null);
  const [loadingOverview, setLoadingOverview] = React.useState<boolean>(false);

  // -------------------------------------------------------------
  // TAB 3: BLOCK A ROOM (WITH REAL-TIME ENGINE REALLOCATION PREVIEW)
  // -------------------------------------------------------------
  const [blockSelectedBlockId, setBlockSelectedBlockId] = React.useState<string>("");
  const [blockRoomId, setBlockRoomId] = React.useState<string>("");
  const [roomSearch, setRoomSearch] = React.useState<string>("");
  const [loadingRooms, setLoadingRooms] = React.useState<boolean>(false);
  const [roomsError, setRoomsError] = React.useState<string>("");
  const [blockDateFrom, setBlockDateFrom] = React.useState<string>(() => {
    return new Date().toISOString().split("T")[0];
  });
  const [blockDateTo, setBlockDateTo] = React.useState<string>(() => {
    return new Date().toISOString().split("T")[0];
  });
  const [blockSelectedSlots, setBlockSelectedSlots] = React.useState<number[]>([]);
  const [blockReason, setBlockReason] = React.useState<string>("MAINTENANCE");
  const [blockNote, setBlockNote] = React.useState<string>("");
  const [blockMarkExamHall, setBlockMarkExamHall] = React.useState<boolean>(false);

  const [previewData, setPreviewData] = React.useState<RoomBlockPreviewResponse | null>(null);
  const [loadingPreview, setLoadingPreview] = React.useState<boolean>(false);
  const [previewError, setPreviewError] = React.useState<string>("");
  const [isConfirmingBlock, setIsConfirmingBlock] = React.useState<boolean>(false);

  // Subtabs for block-room: "block" (form) vs "list" (table) synchronized with URL
  const blockRoomSubTab = searchParams.get("tab") === "blocked" ? "list" : "block";

  const handleBlockRoomSubTabChange = (newSubTab: "block" | "list") => {
    if (newSubTab === "list") {
      router.push("/coordinator/block-room?tab=blocked");
    } else {
      router.push("/coordinator/block-room");
    }
  };

  const [blockedRoomsCounts, setBlockedRoomsCounts] = React.useState<BlockedRoomsSummaryCounts>({
    currently_blocked: 0,
    upcoming_blocks: 0,
    maintenance_rooms: 0,
  });
  const [activeBlockedItems, setActiveBlockedItems] = React.useState<BlockedRoomItem[]>([]);

  // -------------------------------------------------------------
  // TAB 4: HISTORY TABLE STATE
  // -------------------------------------------------------------
  const [historyBookings, setHistoryBookings] = React.useState<Booking[]>([]);
  const [historyTotal, setHistoryTotal] = React.useState<number>(0);
  const [historyPage, setHistoryPage] = React.useState<number>(1);
  const [historyPageSize] = React.useState<number>(15);
  const [loadingHistory, setLoadingHistory] = React.useState<boolean>(false);
  const [historySearch, setHistorySearch] = React.useState<string>("");
  const [debouncedHistorySearch, setDebouncedHistorySearch] = React.useState<string>("");

  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedHistorySearch(historySearch.trim());
      setHistoryPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [historySearch]);

  const [historyStatusFilter, setHistoryStatusFilter] = React.useState<string>("");
  const [historyRoomFilter, setHistoryRoomFilter] = React.useState<string>("");
  const [historyBlockFilter, setHistoryBlockFilter] = React.useState<string>("");
  const [historyDateFrom, setHistoryDateFrom] = React.useState<string>("");
  const [historyDateTo, setHistoryDateTo] = React.useState<string>("");

  // -------------------------------------------------------------
  // TAB 5: TIMETABLE GRID STATE
  // -------------------------------------------------------------
  const [timetableDate, setTimetableDate] = React.useState<string>(() => {
    return new Date().toISOString().split("T")[0];
  });
  const [timetableBlockFilter, setTimetableBlockFilter] = React.useState<string>("");
  const [timetableData, setTimetableData] = React.useState<any>(null);
  const [loadingTimetable, setLoadingTimetable] = React.useState<boolean>(false);

  // Fetch coordinator rooms (supports optional block_id filter, never sends empty string)
  const fetchCoordinatorRooms = React.useCallback(async (blockId?: string) => {
    setLoadingRooms(true);
    setRoomsError("");
    try {
      const params: Record<string, any> = {};
      if (blockId && blockId.trim() !== "") {
        params.block_id = Number(blockId);
      }
      const res = await apiClient<any>("/api/coordinator/rooms", { params });
      const items: CoordinatorRoom[] = Array.isArray(res) ? res : res?.items || [];
      setRooms(items);

      if (items.length > 0) {
        setBlockRoomId((prev) => {
          if (prev && items.some((r) => String(r.id) === prev)) {
            return prev;
          }
          return String(items[0].id);
        });
      } else {
        setBlockRoomId("");
      }
    } catch (err: any) {
      const msg = formatErrorMessage(err, "Failed to load rooms for this block.");
      setRoomsError(msg);
      setRooms([]);
      setBlockRoomId("");
    } finally {
      setLoadingRooms(false);
    }
  }, []);

  // -------------------------------------------------------------
  // INITIAL FETCHES & REAL-TIME POLLING
  // -------------------------------------------------------------
  const fetchProfileAndMetadata = React.useCallback(async () => {
    try {
      const [userRes, bRes, metaRes] = await Promise.all([
        apiClient("/api/auth/me").catch(() => null),
        apiClient<any>("/api/coordinator/blocks").catch(() => ({ items: [], total: 0 })),
        apiClient<any>("/api/public/meta").catch(() => ({})),
      ]);

      if (userRes) setCurrentUser(userRes);
      const fetchedBlocks: Block[] = Array.isArray(bRes) ? bRes : bRes?.items || [];
      setBlocks(fetchedBlocks);
      setDepartments(metaRes?.departments || []);
      setTimeSlots(metaRes?.slots || metaRes?.time_slots || []);

      if (fetchedBlocks.length > 0) {
        setBlockSelectedBlockId((prev) => prev || String(fetchedBlocks[0].id));
      }
    } catch {
      // ignore
    }
  }, []);

  React.useEffect(() => {
    if (blockSelectedBlockId) {
      fetchCoordinatorRooms(blockSelectedBlockId);
    } else if (blocks.length === 0) {
      setRooms([]);
      setBlockRoomId("");
    }
  }, [blockSelectedBlockId, blocks.length, fetchCoordinatorRooms]);

  // Polling for pending count every 30 seconds (silent, paused when tab is hidden)
  const pollPendingCount = React.useCallback(async () => {
    if (typeof document !== "undefined" && document.hidden) return;
    try {
      const res = await apiClient<PaginatedResponse<Booking>>(
        "/api/coordinator/bookings/pending?page_size=1",
        { skipAuthRefresh: false }
      );
      if (res && typeof res.total === "number") {
        setPendingCount((prev) => (prev !== res.total ? res.total : prev));
      }
    } catch {
      // ignore
    }
  }, []);

  React.useEffect(() => {
    fetchProfileAndMetadata();
    pollPendingCount();

    const interval = setInterval(() => {
      pollPendingCount();
    }, 30000); // 30 seconds poll

    return () => clearInterval(interval);
  }, [fetchProfileAndMetadata, pollPendingCount]);

  // -------------------------------------------------------------
  // TAB 1: PENDING INBOX FETCH & ACTIONS
  // -------------------------------------------------------------
  const fetchPendingBookings = React.useCallback(async () => {
    setLoadingPending(true);
    try {
      const params: Record<string, any> = { page_size: 50 };
      if (debouncedPendingSearch) params.search = debouncedPendingSearch;

      const res = await apiClient<PaginatedResponse<Booking>>(
        "/api/coordinator/bookings/pending",
        { params }
      );
      setPendingBookings(res.items || []);
      setPendingCount(res.total || 0);
    } catch (err: any) {
      showToast({
        title: "Error loading pending requests",
        message: formatErrorMessage(err, "Failed to load requests"),
        type: "error",
      });
    } finally {
      setLoadingPending(false);
    }
  }, [debouncedPendingSearch]);

  React.useEffect(() => {
    if (activeTab === "pending") {
      fetchPendingBookings();
    }
  }, [activeTab, fetchPendingBookings]);

  const handleApproveSingle = async (bookingId: number) => {
    try {
      await apiClient(`/api/coordinator/bookings/${bookingId}/decision`, {
        method: "POST",
        body: JSON.stringify({ action: "approve" }),
      });
      showToast({
        title: "Booking Approved",
        message: "The room reservation has been approved successfully.",
        type: "success",
      });
      fetchPendingBookings();
      pollPendingCount();
      if (drawerOpen && selectedBooking?.id === bookingId) {
        setDrawerOpen(false);
      }
    } catch (err: any) {
      showToast({
        title: "Approval Failed",
        message: formatErrorMessage(err, "Could not approve booking."),
        type: "error",
      });
    }
  };

  const openRejectModal = (bookingId: number) => {
    setRejectingBookingId(bookingId);
    setRejectionReason("");
    setRejectionError("");
    setRejectModalOpen(true);
  };

  const handleConfirmReject = async () => {
    if (!rejectingBookingId) return;
    if (!rejectionReason.trim()) {
      setRejectionError("A rejection reason is required.");
      return;
    }

    setIsRejecting(true);
    try {
      await apiClient(`/api/coordinator/bookings/${rejectingBookingId}/decision`, {
        method: "POST",
        body: JSON.stringify({ action: "reject", note: rejectionReason.trim() }),
      });
      showToast({
        title: "Booking Rejected",
        message: "Rejection decision and notification sent to requester.",
        type: "info",
      });
      setRejectModalOpen(false);
      setRejectingBookingId(null);
      fetchPendingBookings();
      pollPendingCount();
      if (drawerOpen && selectedBooking?.id === rejectingBookingId) {
        setDrawerOpen(false);
      }
    } catch (err: any) {
      showToast({
        title: "Rejection Failed",
        message: formatErrorMessage(err, "Failed to reject booking."),
        type: "error",
      });
    } finally {
      setIsRejecting(false);
    }
  };

  const handleToggleSelectPending = (id: number) => {
    setSelectedPendingIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const handleSelectAllPending = () => {
    if (selectedPendingIds.length === pendingBookings.length) {
      setSelectedPendingIds([]);
    } else {
      setSelectedPendingIds(pendingBookings.map((b) => b.id));
    }
  };

  const handleBulkApprove = async () => {
    if (selectedPendingIds.length === 0) return;
    setIsBulkApproving(true);
    try {
      const res = await apiClient<any>("/api/coordinator/bookings/bulk-decision", {
        method: "POST",
        body: JSON.stringify({
          booking_ids: selectedPendingIds,
          action: "approve",
        }),
      });
      showToast({
        title: "Bulk Approval Completed",
        message: `Successfully approved ${res.success_count} booking(s).`,
        type: "success",
      });
      setSelectedPendingIds([]);
      setBulkConfirmOpen(false);
      fetchPendingBookings();
      pollPendingCount();
    } catch (err: any) {
      showToast({
        title: "Bulk Approval Failed",
        message: formatErrorMessage(err, "Could not complete bulk approval."),
        type: "error",
      });
    } finally {
      setIsBulkApproving(false);
    }
  };

  // -------------------------------------------------------------
  // TAB 2: ALL-BLOCKS OVERVIEW FETCH
  // -------------------------------------------------------------
  const fetchOverview = React.useCallback(async () => {
    setLoadingOverview(true);
    try {
      const params: Record<string, any> = { date: overviewDate };
      if (overviewSlotId) params.slot_id = Number(overviewSlotId);

      const res = await apiClient<BlockOverviewResponse>("/api/coordinator/overview", {
        params,
      });
      setOverviewData(res);
    } catch (err: any) {
      showToast({
        title: "Overview Failed",
        message: formatErrorMessage(err, "Could not load blocks overview."),
        type: "error",
      });
    } finally {
      setLoadingOverview(false);
    }
  }, [overviewDate, overviewSlotId]);

  React.useEffect(() => {
    if (activeTab === "overview") {
      fetchOverview();
    }
  }, [activeTab, fetchOverview]);

  // Group rooms by Block
  const groupedBlocks = React.useMemo(() => {
    if (!overviewData?.rooms) return [];
    const map = new Map<number, { block_id: number; block_name: string; is_my_block: boolean; rooms: BlockOverviewRoom[] }>();

    for (const r of overviewData.rooms) {
      if (!map.has(r.block_id)) {
        map.set(r.block_id, {
          block_id: r.block_id,
          block_name: r.block_name || `Block ${r.block_id}`,
          is_my_block: r.is_my_block,
          rooms: [],
        });
      }
      map.get(r.block_id)!.rooms.push(r);
    }

    return Array.from(map.values());
  }, [overviewData]);

  // -------------------------------------------------------------
  // TAB 3: BLOCK A ROOM & REALLOCATION PREVIEW / CONFIRM
  // -------------------------------------------------------------
  const fetchBlockPreview = React.useCallback(async () => {
    if (!blockRoomId || !blockDateFrom || !blockDateTo) return;
    setLoadingPreview(true);
    try {
      const payload: any = {
        room_id: Number(blockRoomId),
        date_from: blockDateFrom,
        date_to: blockDateTo,
        reason: blockReason,
      };
      if (blockSelectedSlots.length > 0) {
        payload.slot_ids = blockSelectedSlots;
      }

      const res = await apiClient<RoomBlockPreviewResponse>(
        "/api/coordinator/room-blocks/preview",
        {
          method: "POST",
          body: JSON.stringify(payload),
        }
      );
      setPreviewData(res);
    } catch (err: any) {
      const msg = formatErrorMessage(err, "Could not evaluate room conflicts.");
      setPreviewError(msg);
      showToast({
        title: "Relocation Preview Error",
        message: msg,
        type: "error",
      });
    } finally {
      setLoadingPreview(false);
    }
  }, [blockRoomId, blockDateFrom, blockDateTo, blockReason, blockSelectedSlots]);

  const handleBlockedRoomsCountChange = React.useCallback(
    (counts: BlockedRoomsSummaryCounts) => {
      setBlockedRoomsCounts((prev) => {
        if (
          prev.currently_blocked === counts.currently_blocked &&
          prev.upcoming_blocks === counts.upcoming_blocks &&
          prev.maintenance_rooms === counts.maintenance_rooms
        ) {
          return prev;
        }
        return counts;
      });
    },
    []
  );

  const fetchActiveBlockedRooms = React.useCallback(async () => {
    try {
      const res = await apiClient<any>("/api/coordinator/room-blocks?status=active");
      setActiveBlockedItems(res.items || []);
      if (res.summary) {
        handleBlockedRoomsCountChange(res.summary);
      }
    } catch {
      // ignore
    }
  }, [handleBlockedRoomsCountChange]);

  React.useEffect(() => {
    if (activeTab === "block-room" || activeTab === "overview") {
      fetchActiveBlockedRooms();
    }
  }, [activeTab, fetchActiveBlockedRooms]);

  React.useEffect(() => {
    if (activeTab === "block-room" && blockRoomId) {
      fetchBlockPreview();
    }
  }, [activeTab, blockRoomId, blockDateFrom, blockDateTo, blockReason, blockSelectedSlots, fetchBlockPreview]);

  const activeBlockedRoomsMap = React.useMemo(() => {
    const map = new Map<number, string>();
    for (const item of activeBlockedItems) {
      map.set(item.room_id, item.reason || "BLOCKED");
    }
    return map;
  }, [activeBlockedItems]);

  const filteredRooms = React.useMemo(() => {
    if (!roomSearch.trim()) return rooms;
    const q = roomSearch.toLowerCase().trim();
    return rooms.filter((r) => {
      const nameMatch = r.name.toLowerCase().includes(q);
      const floorMatch = String(r.floor).includes(q);
      const capMatch = String(r.capacity).includes(q);
      const typeMatch = r.room_type.toLowerCase().includes(q);
      const statusMatch = r.status ? r.status.toLowerCase().includes(q) : false;
      return nameMatch || floorMatch || capMatch || typeMatch || statusMatch;
    });
  }, [rooms, roomSearch]);

  const selectedBlockRoom = React.useMemo(() => {
    return rooms.find((r) => String(r.id) === blockRoomId) || null;
  }, [rooms, blockRoomId]);

  const handleConfirmRoomBlockAndRelocate = async () => {
    if (!blockRoomId || !blockDateFrom || !blockDateTo) return;
    setIsConfirmingBlock(true);
    setPreviewError("");
    try {
      const payload: any = {
        room_id: Number(blockRoomId),
        date_from: blockDateFrom,
        date_to: blockDateTo,
        reason: blockReason,
        note: blockNote.trim() || undefined,
        mark_as_exam_hall: blockMarkExamHall,
      };
      if (blockSelectedSlots.length > 0) {
        payload.slot_ids = blockSelectedSlots;
      }

      const res = await apiClient<any>(
        "/api/coordinator/room-blocks/confirm-relocation",
        {
          method: "POST",
          body: JSON.stringify(payload),
        }
      );

      showToast({
        title: "Room Blocked & Relocations Confirmed",
        message: res.message || "Room blocked and affected bookings relocated successfully.",
        type: "success",
      });

      // Refresh preview, rooms, active blocks, and reset note
      setBlockNote("");
      fetchBlockPreview();
      fetchActiveBlockedRooms();
      pollPendingCount();
      if (blockSelectedBlockId) {
        fetchCoordinatorRooms(blockSelectedBlockId);
      }
      // Navigate to Blocked Rooms list so the newly blocked venue is visible
      router.push("/coordinator/block-room?tab=blocked");
    } catch (err: any) {
      const msg = formatErrorMessage(err, "Could not confirm room block and relocation.");
      setPreviewError(msg);
      showToast({
        title: "Room Block Creation Failed",
        message: msg,
        type: "error",
      });
    } finally {
      setIsConfirmingBlock(false);
    }
  };

  // -------------------------------------------------------------
  // TAB 4: HISTORY TABLE FETCH & EXPORT
  // -------------------------------------------------------------
  const fetchHistory = React.useCallback(async () => {
    setLoadingHistory(true);
    try {
      const params: Record<string, any> = {
        page: historyPage,
        page_size: historyPageSize,
      };
      if (debouncedHistorySearch) params.search = debouncedHistorySearch;
      if (historyStatusFilter) params.status = historyStatusFilter;
      if (historyRoomFilter) params.room_id = historyRoomFilter;
      if (historyBlockFilter) params.block_id = historyBlockFilter;
      if (historyDateFrom) params.date_from = historyDateFrom;
      if (historyDateTo) params.date_to = historyDateTo;

      const res = await apiClient<PaginatedResponse<Booking>>(
        "/api/coordinator/history",
        { params }
      );
      setHistoryBookings(res.items || []);
      setHistoryTotal(res.total || 0);
    } catch (err: any) {
      showToast({
        title: "Error loading history",
        message: formatErrorMessage(err, "Failed to load booking history"),
        type: "error",
      });
    } finally {
      setLoadingHistory(false);
    }
  }, [
    historyPage,
    historyPageSize,
    debouncedHistorySearch,
    historyStatusFilter,
    historyRoomFilter,
    historyBlockFilter,
    historyDateFrom,
    historyDateTo,
  ]);

  React.useEffect(() => {
    if (activeTab === "history") {
      fetchHistory();
    }
  }, [activeTab, fetchHistory]);

  const handleExportCsv = () => {
    const searchParams = new URLSearchParams();
    if (historySearch.trim()) searchParams.append("search", historySearch.trim());
    if (historyStatusFilter) searchParams.append("status", historyStatusFilter);
    if (historyRoomFilter) searchParams.append("room_id", historyRoomFilter);
    if (historyBlockFilter) searchParams.append("block_id", historyBlockFilter);
    if (historyDateFrom) searchParams.append("date_from", historyDateFrom);
    if (historyDateTo) searchParams.append("date_to", historyDateTo);

    window.open(`/api/coordinator/bookings/export-csv?${searchParams.toString()}`, "_blank");
  };

  // -------------------------------------------------------------
  // TAB 5: TIMETABLE GRID FETCH
  // -------------------------------------------------------------
  const fetchTimetable = React.useCallback(async () => {
    setLoadingTimetable(true);
    try {
      const params: Record<string, any> = { date: timetableDate };
      if (timetableBlockFilter) params.block_id = Number(timetableBlockFilter);

      const res = await apiClient<any>("/api/coordinator/timetable", { params });
      setTimetableData(res);
    } catch (err: any) {
      showToast({
        title: "Error loading timetable",
        message: formatErrorMessage(err, "Failed to load timetable"),
        type: "error",
      });
    } finally {
      setLoadingTimetable(false);
    }
  }, [timetableDate, timetableBlockFilter]);

  React.useEffect(() => {
    if (activeTab === "timetable") {
      fetchTimetable();
    }
  }, [activeTab, fetchTimetable]);

  // Helpers
  const getRoom = (id: number) => rooms.find((r) => r.id === id);
  const getSlot = (id: number) => timeSlots.find((s) => s.id === id);
  const getDept = (id: number) => departments.find((d) => d.id === id);

  return (
    <DashboardShell
      role="COORDINATOR"
      userName={currentUser?.name || "Block Coordinator"}
      userEmail={currentUser?.email || "coordinator@college.edu"}
      notificationCount={pendingCount}
      notificationLabel="pending requests"
    >
      <div className="space-y-6 pb-16">
        {/* Top Header & Real-time Notification Banner */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-[var(--foreground)]">
                Block Coordinator Console
              </h1>
              {pendingCount > 0 && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-500/10 border border-amber-500/30 text-amber-700 dark:text-amber-300 animate-pulse">
                  <Clock className="w-3.5 h-3.5" />
                  {pendingCount} Pending Requests
                </span>
              )}
            </div>
            <p className="text-sm text-[var(--muted-foreground)] mt-0.5">
              Review assigned block reservations, oversee physical venues, prevent booking conflicts, and execute automatic room relocations.
            </p>
          </div>

          {/* Quick Refresh */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                pollPendingCount();
                if (activeTab === "pending") fetchPendingBookings();
                if (activeTab === "overview") fetchOverview();
                if (activeTab === "block-room") fetchBlockPreview();
                if (activeTab === "history") fetchHistory();
                if (activeTab === "timetable") fetchTimetable();
                showToast({ title: "Refreshed", message: "Data reloaded successfully", type: "info" });
              }}
              className="gap-2"
            >
              <RotateCw className="w-3.5 h-3.5" />
              Refresh
            </Button>
          </div>
        </div>


        {/* ========================================================================= */}
        {/* TAB 0: ALLOCATION INSIGHTS & SMART OPTIMIZER */}
        {/* ========================================================================= */}
        {activeTab === "allocation" && (
          <AllocationInsightsView
            role="COORDINATOR"
            userName={currentUser?.name || "Block Coordinator"}
            userEmail={currentUser?.email || "coordinator@git.edu"}
          />
        )}

        {/* ========================================================================= */}
        {/* TAB 1: PENDING REQUESTS INBOX (WITH BULK APPROVE & REASON REQUIRED REJECT) */}
        {/* ========================================================================= */}
        {activeTab === "pending" && (
          <div className="space-y-4">
            {/* Toolbar */}
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3 flex-1 max-w-md">
                <Input
                  placeholder="Search reference, student name, purpose..."
                  icon={<Search className="w-4 h-4" />}
                  value={pendingSearch}
                  onChange={(e) => setPendingSearch(e.target.value)}
                />
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSelectAllPending}
                  disabled={pendingBookings.length === 0}
                  className="gap-2"
                >
                  {selectedPendingIds.length === pendingBookings.length && pendingBookings.length > 0 ? (
                    <>
                      <CheckSquare className="w-4 h-4 text-sky-600" />
                      Deselect All
                    </>
                  ) : (
                    <>
                      <Square className="w-4 h-4" />
                      Select All
                    </>
                  )}
                </Button>

                <Button
                  size="sm"
                  onClick={() => setBulkConfirmOpen(true)}
                  disabled={selectedPendingIds.length === 0}
                  className="gap-2 bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  Bulk Approve ({selectedPendingIds.length})
                </Button>
              </div>
            </div>

            {/* Pending Requests Table */}
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-[var(--foreground)]">
                  <thead className="border-b border-[var(--border)] bg-slate-50/75 dark:bg-slate-900/40 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                    <tr>
                      <th className="w-12 px-4 py-3.5 text-center">
                        <input
                          type="checkbox"
                          checked={selectedPendingIds.length === pendingBookings.length && pendingBookings.length > 0}
                          onChange={handleSelectAllPending}
                          className="rounded border-[var(--border)] text-sky-600 focus:ring-sky-500"
                        />
                      </th>
                      <th className="px-4 py-3.5">Reference</th>
                      <th className="px-4 py-3.5">Requester</th>
                      <th className="px-4 py-3.5">Venue & Floor</th>
                      <th className="px-4 py-3.5">Schedule Slot</th>
                      <th className="px-4 py-3.5">Purpose</th>
                      <th className="px-4 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {loadingPending ? (
                      Array.from({ length: 4 }).map((_, i) => (
                        <tr key={i}>
                          <td colSpan={7} className="px-5 py-4">
                            <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
                          </td>
                        </tr>
                      ))
                    ) : pendingBookings.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="p-8">
                          <EmptyState
                            title="No pending requests"
                            description="All room booking requests in your assigned blocks have been verified and processed."
                          />
                        </td>
                      </tr>
                    ) : (
                      pendingBookings.map((b) => {
                        const isSelected = selectedPendingIds.includes(b.id);
                        const room = getRoom(b.room_id);
                        const slot = getSlot(b.slot_id);

                        return (
                          <tr
                            key={b.id}
                            className={`transition-colors hover:bg-slate-50/50 dark:hover:bg-slate-900/30 ${
                              isSelected ? "bg-sky-50/40 dark:bg-sky-950/20" : ""
                            }`}
                          >
                            <td className="w-12 px-4 py-3.5 text-center">
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => handleToggleSelectPending(b.id)}
                                className="rounded border-[var(--border)] text-sky-600 focus:ring-sky-500"
                              />
                            </td>
                            <td className="px-4 py-3.5">
                              <span className="font-mono text-xs font-bold text-sky-600 dark:text-sky-400">
                                {b.reference}
                              </span>
                              <span className="text-[11px] text-[var(--muted-foreground)] block">
                                {new Date(b.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}
                              </span>
                            </td>
                            <td className="px-4 py-3.5">
                              <div className="font-semibold text-[var(--foreground)]">{b.name}</div>
                              <div className="text-xs text-[var(--muted-foreground)]">
                                {b.roll_no ? `${b.roll_no} • ` : ""}
                                <span className="capitalize">{b.requester_type.toLowerCase()}</span>
                              </div>
                            </td>
                            <td className="px-4 py-3.5">
                              <span className="font-bold text-[var(--foreground)]">
                                {room?.name || `#${b.room_id}`}
                              </span>
                              <span className="text-xs text-[var(--muted-foreground)] block">
                                Floor {room?.floor ?? "—"} • {room?.capacity ?? "—"} seats
                              </span>
                            </td>
                            <td className="px-4 py-3.5 text-xs">
                              <span className="font-semibold text-[var(--foreground)] block">{b.date}</span>
                              <span className="text-sky-600 dark:text-sky-400">
                                {slot ? `${slot.label} (${slot.start_time.slice(0, 5)})` : `#${b.slot_id}`}
                              </span>
                            </td>
                            <td className="px-4 py-3.5 text-xs max-w-xs truncate text-[var(--foreground)]">
                              {b.purpose}
                            </td>
                            <td className="px-4 py-3.5 text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-8 px-2 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                                  onClick={() => {
                                    setSelectedBooking(b);
                                    setDrawerOpen(true);
                                  }}
                                >
                                  Details
                                </Button>
                                <Button
                                  size="sm"
                                  className="h-8 px-2.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                                  onClick={() => handleApproveSingle(b.id)}
                                >
                                  Approve
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="h-8 px-2.5 text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/40 border-rose-200 dark:border-rose-900"
                                  onClick={() => openRejectModal(b.id)}
                                >
                                  Reject
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

        {/* ========================================================================= */}
        {/* TAB 2: ALL-BLOCKS OVERVIEW (BOOKED VS REMAINING ROOMS + PROGRESS BARS) */}
        {/* ========================================================================= */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* Filter Toolbar */}
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <div>
                  <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                    Target Date
                  </label>
                  <Input
                    type="date"
                    value={overviewDate}
                    onChange={(e) => setOverviewDate(e.target.value)}
                    className="w-44 text-xs font-medium"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                    Time Slot / Period
                  </label>
                  <div className="w-52">
                    <Select
                      options={[
                        { value: "", label: "Entire Day (Any Slot)" },
                        ...timeSlots.map((s) => ({ value: String(s.id), label: `${s.label} (${s.start_time.slice(0, 5)})` })),
                      ]}
                      value={overviewSlotId}
                      onChange={(e) => setOverviewSlotId(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-end">
                <Button size="sm" onClick={fetchOverview} isLoading={loadingOverview} className="gap-2">
                  <RotateCw className="w-3.5 h-3.5" />
                  Evaluate All Blocks
                </Button>
              </div>
            </div>

            {/* Campus Summary Cards */}
            {overviewData && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
                  <span className="text-xs text-[var(--muted-foreground)] block">Total Campus Rooms</span>
                  <span className="text-xl font-extrabold text-[var(--foreground)]">{overviewData.total_rooms}</span>
                </div>
                <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
                  <span className="text-xs text-[var(--muted-foreground)] block">Booked / In Use</span>
                  <span className="text-xl font-extrabold text-sky-600 dark:text-sky-400">
                    {overviewData.booked_rooms_count}
                  </span>
                </div>
                <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
                  <span className="text-xs text-[var(--muted-foreground)] block">Available & Free</span>
                  <span className="text-xl font-extrabold text-emerald-600 dark:text-emerald-400">
                    {overviewData.free_rooms_count}
                  </span>
                </div>
                <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--card)]">
                  <span className="text-xs text-[var(--muted-foreground)] block">Maintenance / Exams</span>
                  <span className="text-xl font-extrabold text-amber-600 dark:text-amber-400">
                    {overviewData.other_rooms_count}
                  </span>
                </div>
              </div>
            )}

            {/* Currently Blocked in Assigned Blocks Strip */}
            {activeBlockedItems.length > 0 ? (
              <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 dark:bg-rose-950/10 p-4 shadow-sm">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-rose-500" />
                    <h3 className="text-xs font-bold text-[var(--foreground)] uppercase tracking-wider">
                      Currently Blocked in Your Blocks ({activeBlockedItems.length})
                    </h3>
                  </div>
                  <button
                    onClick={() => {
                      router.push("/coordinator/block-room?tab=blocked");
                    }}
                    className="text-xs font-semibold text-rose-600 dark:text-rose-400 hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    <span>Manage Blocked Rooms</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {activeBlockedItems.map((item) => (
                    <div
                      key={item.id}
                      className="px-3 py-1.5 rounded-xl border border-[var(--border)] bg-[var(--card)] text-xs flex items-center gap-2 shadow-xs"
                    >
                      <span className="font-bold text-[var(--foreground)]">{item.room.name}</span>
                      <span className="text-[11px] text-[var(--muted-foreground)]">({item.room.block})</span>
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${
                          item.reason === "MAINTENANCE"
                            ? "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30"
                            : "bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/30"
                        }`}
                      >
                        {item.reason}
                      </span>
                      <span className="text-[11px] text-[var(--muted-foreground)]">{item.slot_label}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)]/50 p-3.5 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  <span>All rooms in your assigned blocks are currently active and clear of blockouts.</span>
                </div>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                  0 Blocked
                </span>
              </div>
            )}

            {/* Block Breakdown Cards with Progress Bars */}
            <div className="space-y-5">
              {loadingOverview ? (
                <div className="p-12 text-center">
                  <div className="h-8 w-8 border-2 border-sky-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                  <p className="text-xs text-[var(--muted-foreground)]">Analyzing block utilization...</p>
                </div>
              ) : groupedBlocks.length === 0 ? (
                <EmptyState title="No blocks found" description="No physical blocks registered in catalog." />
              ) : (
                groupedBlocks.map((bGroup) => {
                  const total = bGroup.rooms.length;
                  const booked = bGroup.rooms.filter((r) => r.is_booked).length;
                  const free = bGroup.rooms.filter((r) => r.status === "FREE").length;
                  const other = total - booked - free;

                  const bookedPct = total > 0 ? Math.round((booked / total) * 100) : 0;
                  const freePct = total > 0 ? Math.round((free / total) * 100) : 0;
                  const otherPct = total > 0 ? 100 - bookedPct - freePct : 0;

                  return (
                    <div
                      key={bGroup.block_id}
                      className={`rounded-2xl border p-5 bg-[var(--card)] shadow-sm transition-all ${
                        bGroup.is_my_block
                          ? "border-sky-500/40 dark:border-sky-500/30 ring-1 ring-sky-500/20"
                          : "border-[var(--border)]"
                      }`}
                    >
                      {/* Block Header */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-xl ${bGroup.is_my_block ? "bg-sky-500/10 text-sky-600" : "bg-slate-100 dark:bg-slate-800 text-[var(--muted-foreground)]"}`}>
                            <Building2 className="w-5 h-5" />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <h3 className="text-base font-bold text-[var(--foreground)]">{bGroup.block_name}</h3>
                              {bGroup.is_my_block ? (
                                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-500/20">
                                  My Assigned Block
                                </span>
                              ) : (
                                <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 text-[var(--muted-foreground)] border border-[var(--border)]">
                                  <Lock className="w-3 h-3" />
                                  Read-Only (Other Block)
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-[var(--muted-foreground)]">
                              {total} total room(s) • {booked} booked • {free} free
                            </p>
                          </div>
                        </div>

                        {/* Quick Utilization metric */}
                        <div className="text-right">
                          <span className="text-sm font-extrabold text-[var(--foreground)]">
                            {bookedPct}% Booked
                          </span>
                          <span className="text-[11px] text-[var(--muted-foreground)] block">
                            {freePct}% Remaining
                          </span>
                        </div>
                      </div>

                      {/* Progress Bar (Booked vs Free vs Other) */}
                      <div className="space-y-1.5 mb-5">
                        <div className="h-3 w-full rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden flex shadow-inner">
                          {bookedPct > 0 && (
                            <div
                              style={{ width: `${bookedPct}%` }}
                              className="bg-sky-500 h-full transition-all duration-500"
                              title={`${booked} Booked (${bookedPct}%)`}
                            />
                          )}
                          {otherPct > 0 && (
                            <div
                              style={{ width: `${otherPct}%` }}
                              className="bg-amber-500 h-full transition-all duration-500"
                              title={`${other} Blocked/Exam (${otherPct}%)`}
                            />
                          )}
                          {freePct > 0 && (
                            <div
                              style={{ width: `${freePct}%` }}
                              className="bg-emerald-500 h-full transition-all duration-500"
                              title={`${free} Free (${freePct}%)`}
                            />
                          )}
                        </div>
                        <div className="flex items-center justify-between text-[11px] text-[var(--muted-foreground)]">
                          <div className="flex items-center gap-3">
                            <span className="flex items-center gap-1">
                              <span className="w-2 h-2 rounded-full bg-sky-500 inline-block" />
                              Booked ({booked})
                            </span>
                            <span className="flex items-center gap-1">
                              <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
                              Remaining Free ({free})
                            </span>
                            {other > 0 && (
                              <span className="flex items-center gap-1">
                                <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
                                Blocked/Class ({other})
                              </span>
                            )}
                          </div>
                          <span>Total: {total}</span>
                        </div>
                      </div>

                      {/* Room Badges Grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2">
                        {bGroup.rooms.map((room) => {
                          let bg = "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20";
                          let label = "Free";
                          if (room.status === "BOOKED") {
                            bg = "bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/20";
                            label = "Booked";
                          } else if (room.status === "MAINTENANCE") {
                            bg = "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20";
                            label = "Maint";
                          } else if (room.status === "EXAM") {
                            bg = "bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20";
                            label = "Exam";
                          } else if (room.status === "CLASS") {
                            bg = "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20";
                            label = "Class";
                          }

                          return (
                            <div
                              key={room.room_id}
                              className={`p-2.5 rounded-xl border text-xs flex flex-col justify-between ${bg}`}
                              title={room.purpose ? `Purpose: ${room.purpose}` : undefined}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-bold truncate">{room.room_name}</span>
                                <span className="text-[10px] font-extrabold uppercase px-1 rounded bg-black/5 dark:bg-white/10">
                                  {label}
                                </span>
                              </div>
                              <span className="text-[10px] opacity-75 mt-1">
                                {room.capacity} seats • {room.room_type}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: BLOCK A ROOM (WITH REAL-TIME SUGGESTED RELOCATIONS ENGINE PREVIEW) */}
        {/* ========================================================================= */}
        {activeTab === "block-room" && (
          <div className="space-y-6">
            {/* Subtab Switcher */}
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleBlockRoomSubTabChange("block")}
                  className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer ${
                    blockRoomSubTab === "block"
                      ? "bg-sky-600 text-white shadow-sm"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-slate-100 dark:hover:bg-slate-800"
                  }`}
                >
                  <Ban className="w-3.5 h-3.5" />
                  <span>Block a Room</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleBlockRoomSubTabChange("list")}
                  className={`px-4 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-2 cursor-pointer ${
                    blockRoomSubTab === "list"
                      ? "bg-sky-600 text-white shadow-sm"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-slate-100 dark:hover:bg-slate-800"
                  }`}
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>Blocked Rooms</span>
                  {blockedRoomsCounts.currently_blocked > 0 && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] bg-rose-500 text-white font-extrabold ml-1">
                      {blockedRoomsCounts.currently_blocked}
                    </span>
                  )}
                </button>
              </div>
            </div>

            {blockRoomSubTab === "list" ? (
              <BlockedRoomsView
                mode="coordinator"
                assignedBlocks={blocks}
                onCountChange={handleBlockedRoomsCountChange}
              />
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Form Config Panel */}
                <div className="lg:col-span-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm space-y-4">
                  <div>
                    <h2 className="text-base font-bold text-[var(--foreground)]">
                      Configure Venue Blockout
                    </h2>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Schedule maintenance or institutional exams on rooms in your assigned blocks. The allocation engine will detect affected bookings and propose relocations.
                  </p>
                </div>

                <div className="space-y-3.5">
                  {/* Block Selector */}
                  {blocks.length === 0 ? (
                    <div className="p-3.5 rounded-xl border border-amber-500/20 bg-amber-500/10 text-amber-800 dark:text-amber-200 text-xs font-semibold flex items-center gap-2.5">
                      <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600 dark:text-amber-400" />
                      <span>No block assigned to you yet, contact the admin</span>
                    </div>
                  ) : (
                    <div>
                      <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                        Physical Block *
                      </label>
                      <Select
                        options={blocks.map((b) => ({
                          value: String(b.id),
                          label: b.name,
                        }))}
                        value={blockSelectedBlockId}
                        onChange={(e) => setBlockSelectedBlockId(e.target.value)}
                      />
                    </div>
                  )}

                  {/* Room Search Box */}
                  {blocks.length > 0 && (
                    <div>
                      <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                        Search Rooms in Block
                      </label>
                      <Input
                        placeholder="Search by name, floor, capacity, type..."
                        icon={<Search className="w-4 h-4" />}
                        value={roomSearch}
                        onChange={(e) => setRoomSearch(e.target.value)}
                      />
                    </div>
                  )}

                  {/* Room Selector with States */}
                  {blocks.length > 0 && (
                    <div>
                      <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                        Choose Room to Block *
                      </label>

                      {loadingRooms ? (
                        <div className="p-3.5 rounded-xl border border-[var(--border)] bg-slate-50/50 dark:bg-slate-900/40 text-xs text-[var(--muted-foreground)] flex items-center justify-center gap-2">
                          <RotateCw className="w-4 h-4 animate-spin text-sky-600" />
                          <span>Loading rooms for this block...</span>
                        </div>
                      ) : roomsError ? (
                        <div className="p-3 rounded-xl border border-rose-500/20 bg-rose-500/10 text-rose-600 dark:text-rose-400 text-xs font-medium flex items-center gap-2">
                          <XCircle className="w-4 h-4 shrink-0" />
                          <span>{roomsError}</span>
                        </div>
                      ) : filteredRooms.length === 0 ? (
                        <div className="p-5 rounded-xl border border-dashed border-[var(--border)] text-center text-xs text-[var(--muted-foreground)]">
                          {roomSearch ? `No rooms match "${roomSearch}"` : "No rooms exist in this block."}
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <Select
                            options={filteredRooms.map((r) => {
                              const activeBlockReason = activeBlockedRoomsMap.get(r.id);
                              let tag = "";
                              if (activeBlockReason) {
                                tag = ` [BLOCKED: ${activeBlockReason}]`;
                              } else if (r.status === "MAINTENANCE") {
                                tag = " [MAINTENANCE]";
                              }
                              return {
                                value: String(r.id),
                                label: `${r.name} — Floor ${r.floor}, ${r.capacity} seats, ${r.room_type}${tag}`,
                              };
                            })}
                            value={blockRoomId}
                            onChange={(e) => setBlockRoomId(e.target.value)}
                          />

                          {selectedBlockRoom && (
                            <div className="p-3 rounded-xl border border-[var(--border)] bg-slate-50/50 dark:bg-slate-900/40 text-xs flex items-center justify-between">
                              <div className="space-y-0.5">
                                <div className="font-bold text-[var(--foreground)] flex items-center gap-2">
                                  <span>{selectedBlockRoom.name}</span>
                                  <span className="text-[11px] font-normal text-[var(--muted-foreground)]">
                                    Floor {selectedBlockRoom.floor} • {selectedBlockRoom.capacity} seats • {selectedBlockRoom.room_type}
                                  </span>
                                </div>
                                {selectedBlockRoom.maintenance_note && selectedBlockRoom.status === "MAINTENANCE" && (
                                  <p className="text-[11px] text-amber-700 dark:text-amber-300 italic">
                                    Note: {selectedBlockRoom.maintenance_note}
                                  </p>
                                )}
                              </div>
                              <div className="flex items-center gap-1.5">
                                {activeBlockedRoomsMap.has(selectedBlockRoom.id) && (
                                  <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-rose-500/10 text-rose-700 dark:text-rose-400 border border-rose-500/20 inline-flex items-center gap-1">
                                    <ShieldAlert className="w-3.5 h-3.5" />
                                    BLOCKED: {activeBlockedRoomsMap.get(selectedBlockRoom.id)}
                                  </span>
                                )}
                                {selectedBlockRoom.status === "MAINTENANCE" ? (
                                  <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20 inline-flex items-center gap-1">
                                    <AlertTriangle className="w-3.5 h-3.5" />
                                    MAINTENANCE
                                  </span>
                                ) : (
                                  <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 inline-flex items-center gap-1">
                                    <CheckCircle2 className="w-3.5 h-3.5" />
                                    ACTIVE
                                  </span>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                        Date From *
                      </label>
                      <Input
                        type="date"
                        value={blockDateFrom}
                        onChange={(e) => setBlockDateFrom(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                        Date To *
                      </label>
                      <Input
                        type="date"
                        value={blockDateTo}
                        onChange={(e) => setBlockDateTo(e.target.value)}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                      Reason Category *
                    </label>
                    <Select
                      options={[
                        { value: "MAINTENANCE", label: "Facility Maintenance / Repairs" },
                        { value: "EXAM", label: "Institutional Assessment / Examination" },
                        { value: "OTHER", label: "Special Institutional Event" },
                      ]}
                      value={blockReason}
                      onChange={(e) => setBlockReason(e.target.value)}
                    />
                  </div>

                  {/* Multi-select Period Chips */}
                  <div>
                    <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                      Target Periods (Leave empty for All Periods)
                    </label>
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {timeSlots.map((s) => {
                        const isSelected = blockSelectedSlots.includes(s.id);
                        return (
                          <button
                            key={s.id}
                            type="button"
                            onClick={() => {
                              setBlockSelectedSlots((prev) =>
                                prev.includes(s.id)
                                  ? prev.filter((id) => id !== s.id)
                                  : [...prev, s.id]
                              );
                            }}
                            className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all border ${
                              isSelected
                                ? "bg-sky-600 text-white border-sky-600 shadow-sm"
                                : "bg-slate-100 dark:bg-slate-800 text-[var(--muted-foreground)] border-[var(--border)] hover:text-[var(--foreground)]"
                            }`}
                          >
                            {s.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div>
                    <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                      Optional Explanatory Note
                    </label>
                    <Input
                      placeholder="e.g. Projector replacement and A/C servicing..."
                      value={blockNote}
                      onChange={(e) => setBlockNote(e.target.value)}
                    />
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="checkbox"
                      id="markExamHall"
                      checked={blockMarkExamHall}
                      onChange={(e) => setBlockMarkExamHall(e.target.checked)}
                      className="rounded border-[var(--border)] text-sky-600 focus:ring-sky-500"
                    />
                    <label htmlFor="markExamHall" className="text-xs font-medium text-[var(--foreground)]">
                      Temporarily designate room type as EXAM_HALL
                    </label>
                  </div>
                </div>

                <div className="pt-2 border-t border-[var(--border)]">
                  <Button
                    size="sm"
                    onClick={fetchBlockPreview}
                    isLoading={loadingPreview}
                    className="w-full gap-2"
                  >
                    <RefreshCw className="w-4 h-4" />
                    Re-evaluate Conflict Impact
                  </Button>
                </div>
              </div>

              {/* Impact & Reallocation Preview Panel */}
              <div className="lg:col-span-7 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm flex flex-col justify-between space-y-4">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-base font-bold text-[var(--foreground)]">
                        Allocation Engine Relocation Preview
                      </h2>
                      <p className="text-xs text-[var(--muted-foreground)]">
                        Intelligent alternative room suggestions computed using capacity match and facility requirements.
                      </p>
                    </div>
                    {previewData && (
                      <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-500/20">
                        {previewData.total_affected} Affected Bookings
                      </span>
                    )}
                  </div>

                  {/* Impact Summary Metrics */}
                  {previewData && (
                    <div className="grid grid-cols-3 gap-3">
                      <div className="p-3 rounded-xl border border-[var(--border)] bg-slate-50/50 dark:bg-slate-900/30">
                        <span className="text-[11px] text-[var(--muted-foreground)] block">Affected Bookings</span>
                        <span className="text-lg font-extrabold text-[var(--foreground)]">
                          {previewData.total_affected}
                        </span>
                      </div>
                      <div className="p-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5">
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 block">Can Relocate</span>
                        <span className="text-lg font-extrabold text-emerald-700 dark:text-emerald-300">
                          {previewData.can_relocate_count}
                        </span>
                      </div>
                      <div className="p-3 rounded-xl border border-amber-500/20 bg-amber-500/5">
                        <span className="text-[11px] text-amber-600 dark:text-amber-400 block">Unresolved</span>
                        <span className="text-lg font-extrabold text-amber-700 dark:text-amber-300">
                          {previewData.cannot_relocate_count}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Affected Bookings List */}
                  {loadingPreview ? (
                    <div className="p-10 text-center">
                      <div className="h-7 w-7 border-2 border-sky-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                      <p className="text-xs text-[var(--muted-foreground)]">Evaluating optimal room relocations...</p>
                    </div>
                  ) : !previewData || previewData.affected_bookings.length === 0 ? (
                    <div className="p-8 rounded-xl border border-dashed border-[var(--border)] text-center">
                      <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                      <h3 className="text-sm font-bold text-[var(--foreground)]">No Conflicting Bookings</h3>
                      <p className="text-xs text-[var(--muted-foreground)] max-w-sm mx-auto mt-1">
                        There are no active or approved reservations during this time window. You can safely block this room.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
                      {previewData.affected_bookings.map((item) => (
                        <div
                          key={item.booking_id}
                          className="p-3.5 rounded-xl border border-[var(--border)] bg-slate-50/50 dark:bg-slate-900/40 text-xs space-y-2"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-mono font-bold text-sky-600 dark:text-sky-400">
                              {item.reference}
                            </span>
                            <span className="text-[11px] text-[var(--muted-foreground)]">
                              {item.date} • {item.slot_label}
                            </span>
                          </div>

                          <div className="flex items-center justify-between text-xs">
                            <span className="font-semibold text-[var(--foreground)]">
                              {item.requester_name} ({item.expected_strength} attendees)
                            </span>
                            <span className="text-[var(--muted-foreground)] truncate max-w-[200px]">
                              {item.purpose}
                            </span>
                          </div>

                          {/* Relocation Proposed Arrow */}
                          <div className="pt-2 border-t border-[var(--border)] flex items-center justify-between">
                            <span className="text-[11px] text-[var(--muted-foreground)]">Proposed Venue:</span>
                            {item.can_relocate ? (
                              <div className="flex items-center gap-1.5 font-bold text-emerald-600 dark:text-emerald-400">
                                <span className="line-through text-slate-400 font-normal">{item.current_room_name}</span>
                                <ArrowRight className="w-3.5 h-3.5" />
                                <span>{item.suggested_room_name} ({item.suggested_block_name})</span>
                              </div>
                            ) : (
                              <span className="font-bold text-rose-500 flex items-center gap-1">
                                <AlertTriangle className="w-3.5 h-3.5" />
                                No Matching Free Room Available
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {previewError && (
                    <div className="p-3.5 rounded-xl border border-rose-500/20 bg-rose-500/10 text-rose-600 dark:text-rose-400 text-xs font-medium flex items-center gap-2">
                      <XCircle className="w-4 h-4 shrink-0" />
                      <span>{previewError}</span>
                    </div>
                  )}
                </div>

                {/* Confirm Relocation Action Button */}
                <div className="pt-3 border-t border-[var(--border)]">
                  <Button
                    size="lg"
                    onClick={handleConfirmRoomBlockAndRelocate}
                    isLoading={isConfirmingBlock}
                    disabled={blocks.length === 0 || !blockRoomId || loadingRooms}
                    className="w-full gap-2 bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-700 hover:to-indigo-700 text-white font-bold"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    Confirm Relocation & Block Room
                  </Button>
                </div>
              </div>
            </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: HISTORY TABLE (SAME ROBUST SPEC & FILTERS AS ADMIN) */}
        {/* ========================================================================= */}
        {activeTab === "history" && (
          <div className="space-y-4">
            {/* Header & Export */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-bold text-[var(--foreground)]">
                  Block Booking Archive
                </h2>
                <p className="text-xs text-[var(--muted-foreground)]">
                  Audit trail of all confirmed, rejected, relocated, and completed reservations in your blocks.
                </p>
              </div>

              <div className="flex items-center gap-2">
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
                  placeholder="Search reference, student name, purpose..."
                  icon={<Search className="w-4 h-4" />}
                  value={historySearch}
                  onChange={(e) => {
                    setHistorySearch(e.target.value);
                    setHistoryPage(1);
                  }}
                />
                <Select
                  options={[
                    { value: "", label: "All Statuses" },
                    { value: "APPROVED", label: "Confirmed / Approved" },
                    { value: "COORDINATOR_APPROVED", label: "Coordinator Approved" },
                    { value: "REJECTED", label: "Rejected" },
                    { value: "RELOCATED", label: "Relocated" },
                    { value: "CANCELLED", label: "Cancelled" },
                  ]}
                  value={historyStatusFilter}
                  onChange={(e) => {
                    setHistoryStatusFilter(e.target.value);
                    setHistoryPage(1);
                  }}
                />
                <Select
                  options={[
                    { value: "", label: "All Rooms" },
                    ...rooms.map((r) => ({ value: String(r.id), label: r.name })),
                  ]}
                  value={historyRoomFilter}
                  onChange={(e) => {
                    setHistoryRoomFilter(e.target.value);
                    setHistoryPage(1);
                  }}
                />
                <Select
                  options={[
                    { value: "", label: "All Blocks" },
                    ...blocks.map((b) => ({ value: String(b.id), label: b.name })),
                  ]}
                  value={historyBlockFilter}
                  onChange={(e) => {
                    setHistoryBlockFilter(e.target.value);
                    setHistoryPage(1);
                  }}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-[var(--border)]">
                <Input
                  type="date"
                  placeholder="Date From"
                  value={historyDateFrom}
                  onChange={(e) => {
                    setHistoryDateFrom(e.target.value);
                    setHistoryPage(1);
                  }}
                />
                <Input
                  type="date"
                  placeholder="Date To"
                  value={historyDateTo}
                  onChange={(e) => {
                    setHistoryDateTo(e.target.value);
                    setHistoryPage(1);
                  }}
                />
              </div>
            </div>

            {/* History Table */}
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
                    {loadingHistory ? (
                      Array.from({ length: 5 }).map((_, i) => (
                        <tr key={i}>
                          <td colSpan={7} className="px-5 py-4">
                            <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
                          </td>
                        </tr>
                      ))
                    ) : historyBookings.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="p-8">
                          <EmptyState
                            title="No booking history found"
                            description="Adjust your search filters or date range to inspect historical room allocations."
                          />
                        </td>
                      </tr>
                    ) : (
                      historyBookings.map((b) => {
                        const room = getRoom(b.room_id);
                        const slot = getSlot(b.slot_id);

                        return (
                          <tr
                            key={b.id}
                            onClick={() => {
                              setSelectedBooking(b);
                              setDrawerOpen(true);
                            }}
                            className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30 transition-colors cursor-pointer"
                          >
                            <td className="px-5 py-3.5">
                              <span className="font-mono text-xs font-bold text-sky-600 dark:text-sky-400">
                                {b.reference}
                              </span>
                              <span className="text-[11px] text-[var(--muted-foreground)] block">
                                {new Date(b.created_at).toLocaleDateString([], { month: "short", day: "numeric" })}
                              </span>
                            </td>
                            <td className="px-5 py-3.5">
                              <div className="font-semibold text-[var(--foreground)]">{b.name}</div>
                              <div className="text-xs text-[var(--muted-foreground)] flex items-center gap-1.5">
                                <span className="capitalize">{b.requester_type.toLowerCase()}</span>
                                {b.roll_no && <span>• {b.roll_no}</span>}
                              </div>
                            </td>
                            <td className="px-5 py-3.5">
                              <span className="font-bold text-[var(--foreground)]">
                                {room?.name || `#${b.room_id}`}
                              </span>
                              <span className="text-xs text-[var(--muted-foreground)] block">{room?.room_type}</span>
                            </td>
                            <td className="px-5 py-3.5 text-xs">
                              <span className="font-semibold text-[var(--foreground)] block">{b.date}</span>
                              <span className="text-[var(--muted-foreground)]">
                                {slot ? `${slot.label} (${slot.start_time.slice(0, 5)})` : `#${b.slot_id}`}
                              </span>
                            </td>
                            <td className="px-5 py-3.5">
                              <StatusBadge
                                status={getStatusBadgeVariant(b.status)}
                                label={b.status.replace(/_/g, " ")}
                              />
                            </td>
                            <td className="px-5 py-3.5 text-xs text-[var(--muted-foreground)] max-w-xs truncate">
                              {b.decision_note || "—"}
                            </td>
                            <td className="px-5 py-3.5 text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 text-xs text-sky-600 hover:text-sky-700"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedBooking(b);
                                  setDrawerOpen(true);
                                }}
                              >
                                Dossier
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
              {historyTotal > historyPageSize && (
                <div className="p-4 border-t border-[var(--border)] flex items-center justify-between text-xs text-[var(--muted-foreground)]">
                  <span>
                    Showing {(historyPage - 1) * historyPageSize + 1} to{" "}
                    {Math.min(historyPage * historyPageSize, historyTotal)} of {historyTotal} records
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={historyPage <= 1}
                      onClick={() => setHistoryPage((p) => p - 1)}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={historyPage * historyPageSize >= historyTotal}
                      onClick={() => setHistoryPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 5: TIMETABLE VIEW (ROOM X SLOT MATRIX FOR DATE) */}
        {/* ========================================================================= */}
        {activeTab === "timetable" && (
          <div className="space-y-4">
            {/* Filter Toolbar */}
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <div>
                  <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                    Select Date
                  </label>
                  <Input
                    type="date"
                    value={timetableDate}
                    onChange={(e) => setTimetableDate(e.target.value)}
                    className="w-44 text-xs font-medium"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
                    Building Block Filter
                  </label>
                  <div className="w-52">
                    <Select
                      options={[
                        { value: "", label: "My Assigned Blocks" },
                        ...blocks.map((b) => ({ value: String(b.id), label: b.name })),
                      ]}
                      value={timetableBlockFilter}
                      onChange={(e) => setTimetableBlockFilter(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-end">
                <Button size="sm" onClick={fetchTimetable} isLoading={loadingTimetable} className="gap-2">
                  <RotateCw className="w-3.5 h-3.5" />
                  Load Timetable
                </Button>
              </div>
            </div>

            {/* Timetable Matrix */}
            {loadingTimetable ? (
              <div className="p-12 text-center">
                <div className="h-8 w-8 border-2 border-sky-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
                <p className="text-xs text-[var(--muted-foreground)]">Loading room matrix for {timetableDate}...</p>
              </div>
            ) : timetableData?.matrix ? (
              <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-[var(--foreground)]">
                    <thead className="border-b border-[var(--border)] bg-slate-50/75 dark:bg-slate-900/40 text-[11px] font-semibold text-[var(--muted-foreground)] uppercase">
                      <tr>
                        <th className="px-4 py-3 sticky left-0 bg-[var(--card)] z-10">Room</th>
                        {timetableData.slots?.map((s: any) => (
                          <th key={s.id} className="px-3 py-3 text-center min-w-[130px]">
                            <div>{s.label}</div>
                            <span className="font-mono text-[10px] opacity-60">
                              {s.start_time.slice(0, 5)} - {s.end_time.slice(0, 5)}
                            </span>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {timetableData.matrix?.map((row: any) => (
                        <tr key={row.room_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30">
                          <td className="px-4 py-3 font-bold sticky left-0 bg-[var(--card)] z-10 border-r border-[var(--border)]">
                            <div>{row.room_name}</div>
                            <span className="text-[10px] text-[var(--muted-foreground)] font-normal">
                              {row.block_name} • {row.capacity} seats
                            </span>
                          </td>
                          {row.slots?.map((cell: any) => {
                            let cellBg = "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20";
                            let cellLabel = "Free";
                            if (cell.status === "BOOKED") {
                              cellBg = "bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/20";
                              cellLabel = "Booked";
                            } else if (cell.status === "CLASS") {
                              cellBg = "bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-500/20";
                              cellLabel = "Class";
                            } else if (cell.status === "MAINTENANCE") {
                              cellBg = "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20";
                              cellLabel = "Maintenance";
                            } else if (cell.status === "EXAM") {
                              cellBg = "bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20";
                              cellLabel = "Exam";
                            }

                            return (
                              <td key={cell.slot_id} className="px-2 py-2 text-center">
                                <div
                                  className={`p-2 rounded-xl border text-[11px] font-semibold truncate ${cellBg}`}
                                  title={cell.details || cellLabel}
                                >
                                  <div>{cellLabel}</div>
                                  {cell.details && (
                                    <span className="text-[10px] opacity-75 block truncate font-normal">
                                      {cell.details}
                                    </span>
                                  )}
                                </div>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <EmptyState title="No timetable data" description="Select a date to query room availability." />
            )}
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* DETAILS SLIDE-OVER DRAWER (SAME COMPONENT DOSSIER AS ADMIN) */}
      {/* ========================================================================= */}
      {drawerOpen && selectedBooking && (
        <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm transition-opacity"
            onClick={() => setDrawerOpen(false)}
          />

          <div className="relative z-10 w-full max-w-lg bg-[var(--card)] border-l border-[var(--border)] shadow-2xl h-full flex flex-col p-6 overflow-y-auto">
            {/* Drawer Header */}
            <div className="flex items-center justify-between pb-4 border-b border-[var(--border)]">
              <div>
                <span className="font-mono text-xs font-bold text-sky-600 dark:text-sky-400">
                  {selectedBooking.reference}
                </span>
                <h2 className="text-lg font-bold text-[var(--foreground)] mt-0.5">
                  Booking Dossier Details
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
            <div className="space-y-5 py-5 flex-1 text-xs">
              {/* Status Box */}
              <div className="p-4 rounded-xl border border-[var(--border)] bg-slate-50 dark:bg-slate-900/50 flex items-center justify-between">
                <div>
                  <span className="text-[11px] text-[var(--muted-foreground)] block">Approval State</span>
                  <span className="font-bold text-sm text-[var(--foreground)]">
                    {selectedBooking.status.replace(/_/g, " ")}
                  </span>
                </div>
                <StatusBadge
                  status={getStatusBadgeVariant(selectedBooking.status)}
                  label={selectedBooking.status}
                />
              </div>

              {/* Requester Profile */}
              <div className="space-y-2">
                <h3 className="font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                  Requester Information
                </h3>
                <div className="p-3.5 rounded-xl border border-[var(--border)] space-y-1.5">
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
                    <span className="text-[var(--muted-foreground)]">Role / Type:</span>
                    <span className="font-medium text-[var(--foreground)]">{selectedBooking.requester_type}</span>
                  </div>
                  {selectedBooking.roll_no && (
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">ID / Roll No:</span>
                      <span className="font-medium text-[var(--foreground)]">{selectedBooking.roll_no}</span>
                    </div>
                  )}
                  {selectedBooking.class_name && (
                    <div className="flex justify-between">
                      <span className="text-[var(--muted-foreground)]">Class:</span>
                      <span className="font-medium text-[var(--foreground)]">{selectedBooking.class_name}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Department:</span>
                    <span className="font-medium text-[var(--foreground)]">
                      {getDept(selectedBooking.department_id)?.name || `#${selectedBooking.department_id}`}
                    </span>
                  </div>
                </div>
              </div>

              {/* Room Reservation Info */}
              <div className="space-y-2">
                <h3 className="font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                  Allocated Room & Schedule
                </h3>
                <div className="p-3.5 rounded-xl border border-[var(--border)] space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">Room:</span>
                    <span className="font-bold text-[var(--foreground)]">
                      {getRoom(selectedBooking.room_id)?.name}
                    </span>
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
                    <span className="text-[var(--muted-foreground)]">Expected Attendance:</span>
                    <span className="font-semibold text-[var(--foreground)]">
                      {selectedBooking.expected_strength} persons
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--muted-foreground)]">HOD Approval Required:</span>
                    <span className="font-semibold text-[var(--foreground)]">
                      {selectedBooking.requires_hod_approval ? "Yes" : "No"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Purpose & Notes */}
              <div className="space-y-1.5">
                <span className="font-bold uppercase tracking-wider text-[var(--muted-foreground)] block">
                  Event Purpose
                </span>
                <p className="p-3 rounded-xl border border-[var(--border)] bg-slate-50 dark:bg-slate-900/40 text-[var(--foreground)]">
                  {selectedBooking.purpose}
                </p>
              </div>

              {selectedBooking.decision_note && (
                <div className="space-y-1.5">
                  <span className="font-bold uppercase tracking-wider text-[var(--muted-foreground)] block">
                    Decision Note
                  </span>
                  <p className="p-3 rounded-xl border border-amber-500/20 bg-amber-500/5 text-amber-900 dark:text-amber-200">
                    {selectedBooking.decision_note}
                  </p>
                </div>
              )}
            </div>

            {/* Drawer Footer Actions if Pending */}
            {selectedBooking.status === "PENDING" && (
              <div className="pt-4 border-t border-[var(--border)] flex items-center gap-2">
                <Button
                  size="sm"
                  className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                  onClick={() => handleApproveSingle(selectedBooking.id)}
                >
                  Approve Request
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 text-rose-600 border-rose-200 dark:border-rose-900 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                  onClick={() => openRejectModal(selectedBooking.id)}
                >
                  Reject Request
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* REJECT MODAL (MANDATORY REASON VALIDATION) */}
      {/* ========================================================================= */}
      <Modal
        isOpen={rejectModalOpen}
        onClose={() => setRejectModalOpen(false)}
        title="Reject Booking Request"
        description="A clear explanatory reason is mandatory and will be emailed to the requester."
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-[var(--muted-foreground)] block mb-1">
              Rejection Reason *
            </label>
            <textarea
              rows={3}
              placeholder="e.g. Venue reserved for institutional accreditation inspection or room capacity mismatch..."
              value={rejectionReason}
              onChange={(e) => {
                setRejectionReason(e.target.value);
                if (rejectionError) setRejectionError("");
              }}
              className="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] p-3 text-xs text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-rose-500"
            />
            {rejectionError && (
              <p className="text-xs text-rose-500 mt-1 font-semibold">{rejectionError}</p>
            )}
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border)]">
            <Button variant="outline" size="sm" onClick={() => setRejectModalOpen(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              isLoading={isRejecting}
              className="bg-rose-600 hover:bg-rose-700 text-white"
              onClick={handleConfirmReject}
            >
              Confirm Rejection
            </Button>
          </div>
        </div>
      </Modal>

      {/* ========================================================================= */}
      {/* BULK APPROVE CONFIRM DIALOG */}
      {/* ========================================================================= */}
      <ConfirmDialog
        isOpen={bulkConfirmOpen}
        onClose={() => setBulkConfirmOpen(false)}
        title={`Approve ${selectedPendingIds.length} Selected Requests?`}
        message="This will confirm room assignments and send confirmation emails to all selected students/faculty."
        confirmText="Approve All Selected"
        variant="info"
        isLoading={isBulkApproving}
        onConfirm={handleBulkApprove}
      />

    </DashboardShell>
  );
}

export default function CoordinatorDashboardPage() {
  return (
    <React.Suspense
      fallback={
        <div className="min-h-screen bg-[var(--background)] flex items-center justify-center p-8">
          <div className="flex items-center gap-3 text-sm text-[var(--muted-foreground)]">
            <div className="h-5 w-5 border-2 border-sky-500 border-t-transparent rounded-full animate-spin" />
            <span>Loading coordinator dashboard...</span>
          </div>
        </div>
      }
    >
      <CoordinatorDashboardContent />
    </React.Suspense>
  );
}

