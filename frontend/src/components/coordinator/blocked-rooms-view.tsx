"use client";

import * as React from "react";
import {
  ShieldAlert,
  CalendarClock,
  Wrench,
  Search,
  RotateCw,
  Unlock,
  AlertTriangle,
  Layers,
  Filter,
  CheckCircle2,
  Calendar,
  Building2,
  Trash2,
} from "lucide-react";
import { StatCard } from "@/components/ui/stat-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { showToast } from "@/components/ui/toast";
import { Skeleton } from "@/components/ui/skeleton";
import {
  BlockedRoomItem,
  BlockedRoomsResponse,
  BlockedRoomsSummaryCounts,
  Block,
  CoordinatorRoom,
} from "@/lib/admin-types";
import { apiClient } from "@/lib/api-client";

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

interface BlockedRoomsViewProps {
  mode?: "coordinator" | "admin";
  assignedBlocks?: Block[];
  onCountChange?: (counts: BlockedRoomsSummaryCounts) => void;
}

export function BlockedRoomsView({
  mode = "coordinator",
  assignedBlocks = [],
  onCountChange,
}: BlockedRoomsViewProps) {
  const [data, setData] = React.useState<BlockedRoomsResponse | null>(null);
  const [isInitialLoading, setIsInitialLoading] = React.useState(true);
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const [error, setError] = React.useState<string>("");

  // Keep a stable ref to onCountChange and data to prevent infinite re-render loops
  const onCountChangeRef = React.useRef(onCountChange);
  React.useEffect(() => {
    onCountChangeRef.current = onCountChange;
  }, [onCountChange]);

  const dataRef = React.useRef<BlockedRoomsResponse | null>(data);
  React.useEffect(() => {
    dataRef.current = data;
  }, [data]);

  const prevSummaryRef = React.useRef<string>("");
  const abortControllerRef = React.useRef<AbortController | null>(null);

  // Filters
  const [blockFilter, setBlockFilter] = React.useState<string>("");
  const [roomFilter, setRoomFilter] = React.useState<string>("");
  const [reasonFilter, setReasonFilter] = React.useState<string>("");
  const [statusFilter, setStatusFilter] = React.useState<string>("all");
  const [dateFrom, setDateFrom] = React.useState<string>("");
  const [dateTo, setDateTo] = React.useState<string>("");
  const [search, setSearch] = React.useState<string>("");
  const [debouncedSearch, setDebouncedSearch] = React.useState<string>("");
  const [page, setPage] = React.useState(1);
  const pageSize = 20;

  // Debounce search input by 300ms
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search.trim());
      setPage(1);
      setSelectedIds([]);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Stable string of assigned block IDs
  const assignedBlockIds = React.useMemo(
    () => (assignedBlocks || []).map((b) => b.id).join(","),
    [assignedBlocks]
  );

  // Metadata for filter dropdowns
  const [availableBlocks, setAvailableBlocks] = React.useState<Block[]>(assignedBlocks);
  const [availableRooms, setAvailableRooms] = React.useState<CoordinatorRoom[]>([]);

  // Selection for bulk release
  const [selectedIds, setSelectedIds] = React.useState<number[]>([]);

  // Dialog State
  const [singleReleaseTarget, setSingleReleaseTarget] = React.useState<BlockedRoomItem | null>(null);
  const [bulkReleaseConfirmOpen, setBulkReleaseConfirmOpen] = React.useState(false);
  const [isReleasing, setIsReleasing] = React.useState(false);

  // Fetch blocks if not provided
  React.useEffect(() => {
    if (assignedBlocks && assignedBlocks.length > 0) {
      setAvailableBlocks(assignedBlocks);
      return;
    }
    const fetchBlocks = async () => {
      try {
        const endpoint = mode === "admin" ? "/api/admin/blocks?page_size=100" : "/api/coordinator/blocks";
        const res = await apiClient<any>(endpoint);
        setAvailableBlocks(res.items || []);
      } catch (e) {
        console.error("Failed to load blocks for filter:", e);
      }
    };
    fetchBlocks();
  }, [assignedBlockIds, mode]);

  // Fetch rooms for chosen block
  React.useEffect(() => {
    const fetchRooms = async () => {
      try {
        const url = blockFilter
          ? `/api/coordinator/rooms?block_id=${blockFilter}`
          : "/api/coordinator/rooms";
        const res = await apiClient<any>(url);
        setAvailableRooms(res.items || []);
      } catch {
        setAvailableRooms([]);
      }
    };
    fetchRooms();
  }, [blockFilter]);

  // Memoize query params with primitive dependencies
  const queryString = React.useMemo(() => {
    const params = new URLSearchParams();
    if (statusFilter && statusFilter !== "all") params.set("status", statusFilter);
    if (blockFilter) params.set("block_id", blockFilter);
    if (roomFilter) params.set("room_id", roomFilter);
    if (reasonFilter) params.set("reason", reasonFilter);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (debouncedSearch) params.set("search", debouncedSearch);
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    return params.toString();
  }, [statusFilter, blockFilter, roomFilter, reasonFilter, dateFrom, dateTo, debouncedSearch, page, pageSize]);

  // Main fetch function with AbortController and silent mode support
  const fetchBlockedRooms = React.useCallback(
    async (options?: { silent?: boolean; force?: boolean }) => {
      const isSilent = options?.silent ?? false;

      // Abort previous in-flight request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      if (!isSilent) {
        if (!dataRef.current) {
          setIsInitialLoading(true);
        } else {
          setIsRefreshing(true);
        }
        setError("");
      }

      try {
        const query = queryString ? `?${queryString}` : "";
        const res = await apiClient<BlockedRoomsResponse>(`/api/coordinator/room-blocks${query}`, {
          signal: controller.signal,
        });

        // Stale-while-revalidate: update data if changed
        setData((prev) => {
          if (isSilent && prev) {
            const isIdentical = JSON.stringify(prev) === JSON.stringify(res);
            return isIdentical ? prev : res;
          }
          return res;
        });

        // Silent notification of counts: notify only if counts actually changed
        const summaryStr = JSON.stringify(res.summary || {});
        if (summaryStr !== prevSummaryRef.current) {
          prevSummaryRef.current = summaryStr;
          if (onCountChangeRef.current && res.summary) {
            onCountChangeRef.current(res.summary);
          }
        }
      } catch (err: any) {
        if (err?.name === "AbortError" || (err?.message && err.message.includes("aborted"))) {
          return;
        }
        const msg = formatErrorMessage(err, "Failed to load blocked rooms.");
        setError(msg);
        if (!isSilent) {
          showToast({
            type: "error",
            title: "Error Loading Blocked Rooms",
            message: msg,
          });
        }
      } finally {
        setIsInitialLoading(false);
        setIsRefreshing(false);
      }
    },
    [queryString]
  );

  // Fetch only on mount and when query params actually change
  React.useEffect(() => {
    fetchBlockedRooms();
  }, [fetchBlockedRooms]);

  // Silent background polling: every 30s, paused when tab is hidden
  React.useEffect(() => {
    const interval = setInterval(() => {
      if (typeof document !== "undefined" && document.hidden) return;
      fetchBlockedRooms({ silent: true });
    }, 30000);

    return () => clearInterval(interval);
  }, [fetchBlockedRooms]);

  // Abort on unmount
  React.useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // Reset page when filters change
  const handleFilterChange = (setter: (v: string) => void, val: string) => {
    setter(val);
    setPage(1);
    setSelectedIds([]);
  };

  const handleResetFilters = () => {
    setBlockFilter("");
    setRoomFilter("");
    setReasonFilter("");
    setStatusFilter("all");
    setDateFrom("");
    setDateTo("");
    setSearch("");
    setDebouncedSearch("");
    setPage(1);
    setSelectedIds([]);
  };

  // Releasable items check
  const isReleasable = (item: BlockedRoomItem) => {
    if (item.is_released) return false;
    if (item.status === "PAST") return false;
    return true;
  };

  // Toggle selection
  const handleToggleSelect = (item: BlockedRoomItem) => {
    if (!isReleasable(item)) return;
    setSelectedIds((prev) =>
      prev.includes(item.id) ? prev.filter((id) => id !== item.id) : [...prev, item.id]
    );
  };

  const releasableItems = (data?.items || []).filter(isReleasable);
  const allReleasableSelected =
    releasableItems.length > 0 &&
    releasableItems.every((item) => selectedIds.includes(item.id));

  const handleToggleSelectAll = () => {
    if (allReleasableSelected) {
      setSelectedIds([]);
    } else {
      setSelectedIds(releasableItems.map((item) => item.id));
    }
  };

  // Single release handler
  const handleConfirmSingleRelease = async () => {
    if (!singleReleaseTarget) return;
    setIsReleasing(true);
    try {
      if (singleReleaseTarget.is_indefinite) {
        await apiClient(
          `/api/coordinator/rooms/${singleReleaseTarget.room_id}/release-maintenance`,
          { method: "POST" }
        );
      } else {
        await apiClient(
          `/api/coordinator/room-blocks/${singleReleaseTarget.id}/release`,
          { method: "POST" }
        );
      }
      showToast({
        type: "success",
        title: "Room Released",
        message: `Room ${singleReleaseTarget.room.name} is now free and available for booking!`,
      });
      setSingleReleaseTarget(null);
      setSelectedIds((prev) => prev.filter((id) => id !== singleReleaseTarget.id));
      await fetchBlockedRooms({ force: true });
    } catch (err: any) {
      const msg = formatErrorMessage(err, "Failed to release room.");
      showToast({
        type: "error",
        title: "Release Failed",
        message: msg,
      });
    } finally {
      setIsReleasing(false);
    }
  };

  // Bulk release handler
  const handleConfirmBulkRelease = async () => {
    if (selectedIds.length === 0) return;
    setIsReleasing(true);
    try {
      // Split indefinite vs standard block IDs
      const indefiniteIds = selectedIds.filter((id) => id < 0);
      const regularBlockIds = selectedIds.filter((id) => id > 0);

      let totalSuccess = 0;

      // 1. Release regular room blocks
      if (regularBlockIds.length > 0) {
        const res = await apiClient<any>("/api/coordinator/room-blocks/release-bulk", {
          method: "POST",
          body: JSON.stringify({ ids: regularBlockIds }),
        });
        totalSuccess += res.released_count || regularBlockIds.length;
      }

      // 2. Release indefinite maintenance rooms
      for (const negId of indefiniteIds) {
        const roomId = Math.abs(negId);
        try {
          await apiClient(`/api/coordinator/rooms/${roomId}/release-maintenance`, {
            method: "POST",
          });
          totalSuccess += 1;
        } catch (e) {
          console.error("Failed indefinite release for room:", roomId, e);
        }
      }

      showToast({
        type: "success",
        title: "Rooms Released",
        message: `Successfully released ${totalSuccess} room block(s).`,
      });
      setBulkReleaseConfirmOpen(false);
      setSelectedIds([]);
      await fetchBlockedRooms({ force: true });
    } catch (err: any) {
      const msg = formatErrorMessage(err, "Failed to bulk release rooms.");
      showToast({
        type: "error",
        title: "Bulk Release Failed",
        message: msg,
      });
    } finally {
      setIsReleasing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Summary Strip Top Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          title="Currently Blocked"
          value={data?.summary?.currently_blocked ?? 0}
          description="Active blocks today & indefinite maintenance"
          icon={<ShieldAlert className="w-5 h-5 text-rose-500" />}
          className="border-rose-500/20 bg-rose-500/5 dark:bg-rose-950/10"
        />
        <StatCard
          title="Upcoming Blocks"
          value={data?.summary?.upcoming_blocks ?? 0}
          description="Scheduled blackout periods in the future"
          icon={<CalendarClock className="w-5 h-5 text-sky-500" />}
          className="border-sky-500/20 bg-sky-500/5 dark:bg-sky-950/10"
        />
        <StatCard
          title="Rooms In Maintenance"
          value={data?.summary?.maintenance_rooms ?? 0}
          description="Under active repair or equipment upgrade"
          icon={<Wrench className="w-5 h-5 text-amber-500" />}
          className="border-amber-500/20 bg-amber-500/5 dark:bg-amber-950/10"
        />
      </div>

      {/* 2. Filter Bar */}
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm space-y-3.5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs font-bold text-[var(--foreground)]">
            <Filter className="w-3.5 h-3.5 text-sky-600 dark:text-sky-400" />
            <span>Filter Blocked Rooms</span>
          </div>

          <div className="flex items-center gap-2">
            {selectedIds.length > 0 && (
              <Button
                size="sm"
                variant="danger"
                onClick={() => setBulkReleaseConfirmOpen(true)}
                className="gap-2 text-xs font-semibold shadow-sm"
              >
                <Unlock className="w-3.5 h-3.5" />
                Release Selected ({selectedIds.length})
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={() => fetchBlockedRooms({ force: true })}
              isLoading={isRefreshing}
              className="gap-1.5 text-xs"
            >
              <RotateCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
              Refresh
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={handleResetFilters}
              className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            >
              Reset
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 pt-1">
          {/* Status Filter */}
          <div>
            <label className="text-[11px] font-semibold text-[var(--muted-foreground)] block mb-1">
              Status
            </label>
            <Select
              options={[
                { value: "all", label: "All Statuses" },
                { value: "active", label: "Active Today" },
                { value: "upcoming", label: "Upcoming" },
                { value: "past", label: "Past / Released" },
              ]}
              value={statusFilter}
              onChange={(e) => handleFilterChange(setStatusFilter, e.target.value)}
            />
          </div>

          {/* Block Filter */}
          <div>
            <label className="text-[11px] font-semibold text-[var(--muted-foreground)] block mb-1">
              Block
            </label>
            <Select
              options={[
                { value: "", label: "All Blocks" },
                ...availableBlocks.map((b) => ({ value: String(b.id), label: b.name })),
              ]}
              value={blockFilter}
              onChange={(e) => handleFilterChange(setBlockFilter, e.target.value)}
            />
          </div>

          {/* Room Filter */}
          <div>
            <label className="text-[11px] font-semibold text-[var(--muted-foreground)] block mb-1">
              Room
            </label>
            <Select
              options={[
                { value: "", label: "All Rooms" },
                ...availableRooms.map((r) => ({
                  value: String(r.id),
                  label: `${r.name} (${r.room_type})`,
                })),
              ]}
              value={roomFilter}
              onChange={(e) => handleFilterChange(setRoomFilter, e.target.value)}
            />
          </div>

          {/* Reason Filter */}
          <div>
            <label className="text-[11px] font-semibold text-[var(--muted-foreground)] block mb-1">
              Reason
            </label>
            <Select
              options={[
                { value: "", label: "All Reasons" },
                { value: "MAINTENANCE", label: "Maintenance" },
                { value: "EXAM", label: "Exam Hall" },
                { value: "OTHER", label: "Other" },
              ]}
              value={reasonFilter}
              onChange={(e) => handleFilterChange(setReasonFilter, e.target.value)}
            />
          </div>

          {/* Date From */}
          <div>
            <label className="text-[11px] font-semibold text-[var(--muted-foreground)] block mb-1">
              Date From
            </label>
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => handleFilterChange(setDateFrom, e.target.value)}
              className="text-xs"
            />
          </div>

          {/* Date To */}
          <div>
            <label className="text-[11px] font-semibold text-[var(--muted-foreground)] block mb-1">
              Date To
            </label>
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => handleFilterChange(setDateTo, e.target.value)}
              className="text-xs"
            />
          </div>
        </div>

        {/* Search Input */}
        <div className="pt-1">
          <Input
            placeholder="Search by room number, notes, reason..."
            icon={<Search className="w-4 h-4" />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* 3. Error Banner */}
      {error && (
        <div className="p-4 rounded-xl border border-rose-500/20 bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs font-semibold flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600 dark:text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* 4. Table Container */}
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-sm overflow-hidden min-h-[480px] flex flex-col justify-between">
        {!data && isInitialLoading ? (
          <div className="p-6 space-y-4 flex-1">
            <div className="h-6 w-48 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
            <div className="space-y-3">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-12 w-full bg-slate-100 dark:bg-slate-900 rounded-lg animate-pulse" />
              ))}
            </div>
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="p-10 flex-1 flex items-center justify-center">
            <EmptyState
              title="No blocked rooms"
              description={
                statusFilter !== "all" || search || blockFilter || reasonFilter
                  ? "No room blocks match your selected filters. Try broadening your criteria."
                  : "There are currently no rooms blocked for maintenance or exams in your blocks."
              }
              icon={<ShieldAlert className="w-8 h-8 text-[var(--muted-foreground)]" />}
              action={
                statusFilter !== "all" || search || blockFilter
                  ? {
                      label: "Clear Filters",
                      onClick: handleResetFilters,
                    }
                  : undefined
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[var(--border)] bg-slate-50/70 dark:bg-slate-900/50 text-[var(--muted-foreground)] font-semibold uppercase tracking-wider text-[11px]">
                  <th className="py-3.5 px-4 w-10">
                    <input
                      type="checkbox"
                      aria-label="Select all releasable room blocks"
                      checked={allReleasableSelected}
                      onChange={handleToggleSelectAll}
                      disabled={releasableItems.length === 0}
                      className="rounded border-[var(--border)] text-sky-600 focus:ring-sky-500 cursor-pointer"
                    />
                  </th>
                  <th className="py-3.5 px-4">Room</th>
                  <th className="py-3.5 px-4">Block / Floor</th>
                  <th className="py-3.5 px-4">Date(s)</th>
                  <th className="py-3.5 px-4">Periods</th>
                  <th className="py-3.5 px-4">Reason</th>
                  <th className="py-3.5 px-4">Note</th>
                  <th className="py-3.5 px-4">Blocked By</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {data.items.map((item) => {
                  const releasable = isReleasable(item);
                  const isSelected = selectedIds.includes(item.id);

                  // Reason Badge Styling: Maintenance = amber, Exam = purple, Other = slate
                  const isMaint = item.reason.toUpperCase() === "MAINTENANCE";
                  const isExam = item.reason.toUpperCase() === "EXAM";
                  const reasonBadgeClass = isMaint
                    ? "bg-amber-500/15 text-amber-800 dark:text-amber-300 border-amber-500/30"
                    : isExam
                    ? "bg-purple-500/15 text-purple-800 dark:text-purple-300 border-purple-500/30"
                    : "bg-slate-500/15 text-slate-800 dark:text-slate-300 border-slate-500/30";

                  // Status Badge Styling
                  let statusBadgeClass = "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-300";
                  let statusLabel = item.status;
                  if (item.status === "ACTIVE") {
                    statusBadgeClass =
                      "bg-emerald-500/15 text-emerald-800 dark:text-emerald-300 border-emerald-500/30 font-bold";
                    statusLabel = "Active Today";
                  } else if (item.status === "UPCOMING") {
                    statusBadgeClass =
                      "bg-sky-500/15 text-sky-800 dark:text-sky-300 border-sky-500/30";
                    statusLabel = "Upcoming";
                  } else if (item.status === "RELEASED") {
                    statusBadgeClass =
                      "bg-slate-200/60 text-slate-500 dark:bg-slate-800/60 dark:text-slate-400 border-slate-300 line-through";
                    statusLabel = "Released";
                  } else if (item.status === "PAST") {
                    statusBadgeClass =
                      "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 border-slate-300";
                    statusLabel = "Past";
                  }

                  return (
                    <tr
                      key={item.id}
                      className={`hover:bg-slate-50/60 dark:hover:bg-slate-900/30 transition-colors ${
                        isSelected ? "bg-sky-50/50 dark:bg-sky-950/20" : ""
                      }`}
                    >
                      {/* Multi-select Checkbox */}
                      <td className="py-3 px-4">
                        <input
                          type="checkbox"
                          aria-label={`Select room block for ${item.room.name}`}
                          checked={isSelected}
                          onChange={() => handleToggleSelect(item)}
                          disabled={!releasable}
                          className="rounded border-[var(--border)] text-sky-600 focus:ring-sky-500 cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                        />
                      </td>

                      {/* Room */}
                      <td className="py-3 px-4">
                        <div className="font-bold text-[var(--foreground)]">
                          {item.room.name}
                        </div>
                        <div className="text-[11px] text-[var(--muted-foreground)]">
                          {item.room.capacity} seats • {item.room.room_type}
                        </div>
                      </td>

                      {/* Block / Floor */}
                      <td className="py-3 px-4">
                        <div className="font-medium text-[var(--foreground)]">
                          {item.room.block}
                        </div>
                        <div className="text-[11px] text-[var(--muted-foreground)]">
                          Floor {item.room.floor}
                        </div>
                      </td>

                      {/* Date(s) */}
                      <td className="py-3 px-4">
                        {item.is_indefinite ? (
                          <span className="inline-flex items-center gap-1.5 font-semibold text-amber-700 dark:text-amber-400">
                            <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-ping" />
                            Indefinite
                          </span>
                        ) : (
                          <div className="font-medium text-[var(--foreground)] flex items-center gap-1.5">
                            <Calendar className="w-3.5 h-3.5 text-[var(--muted-foreground)]" />
                            <span>{item.date}</span>
                          </div>
                        )}
                      </td>

                      {/* Periods */}
                      <td className="py-3 px-4">
                        <span className="inline-block px-2 py-0.5 rounded-md text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-[var(--foreground)]">
                          {item.slot_label}
                        </span>
                      </td>

                      {/* Reason Badge */}
                      <td className="py-3 px-4">
                        <span
                          className={`inline-block px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border ${reasonBadgeClass}`}
                        >
                          {item.reason}
                        </span>
                      </td>

                      {/* Note */}
                      <td className="py-3 px-4 max-w-xs">
                        <p className="truncate text-[var(--muted-foreground)]" title={item.note || ""}>
                          {item.note || "—"}
                        </p>
                      </td>

                      {/* Blocked By */}
                      <td className="py-3 px-4 text-[var(--muted-foreground)] font-medium">
                        {item.created_by || "System"}
                      </td>

                      {/* Status */}
                      <td className="py-3 px-4">
                        <span
                          className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-semibold border ${statusBadgeClass}`}
                        >
                          {statusLabel}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-4 text-right">
                        {releasable ? (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setSingleReleaseTarget(item)}
                            className="text-xs h-7 gap-1.5 border-emerald-500/30 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-500/10 hover:border-emerald-500/50"
                          >
                            <Unlock className="w-3 h-3 text-emerald-600" />
                            Release
                          </Button>
                        ) : (
                          <span className="text-[11px] text-[var(--muted-foreground)] italic">
                            {item.is_released ? "Released" : "Passed"}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination controls */}
        {data && data.pages > 1 && (
          <div className="p-4 border-t border-[var(--border)] flex items-center justify-between text-xs text-[var(--muted-foreground)]">
            <span>
              Showing page {data.page} of {data.pages} ({data.total} total)
            </span>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={page >= data.pages}
                onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* 5. Single Release Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(singleReleaseTarget)}
        onClose={() => setSingleReleaseTarget(null)}
        onConfirm={handleConfirmSingleRelease}
        title="Release Room Block"
        message={
          singleReleaseTarget
            ? `Release ${singleReleaseTarget.room.name} (${
                singleReleaseTarget.is_indefinite
                  ? "Indefinite Maintenance"
                  : singleReleaseTarget.date
              }, ${singleReleaseTarget.reason})? It will become available for booking immediately.`
            : ""
        }
        confirmText="Release Room"
        cancelText="Cancel"
        variant="warning"
        isLoading={isReleasing}
      />

      {/* 6. Bulk Release Confirmation Dialog */}
      <ConfirmDialog
        isOpen={bulkReleaseConfirmOpen}
        onClose={() => setBulkReleaseConfirmOpen(false)}
        onConfirm={handleConfirmBulkRelease}
        title="Bulk Release Rooms"
        message={`Release ${selectedIds.length} selected room block(s)? They will become available for booking immediately.`}
        confirmText={`Release ${selectedIds.length} Rooms`}
        cancelText="Cancel"
        variant="warning"
        isLoading={isReleasing}
      />
    </div>
  );
}
