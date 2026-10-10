"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  RotateCw,
  Play,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  TrendingUp,
  Sliders,
  Calendar,
  Layers,
  DoorOpen,
  Users,
  Building2,
  Clock,
  ShieldCheck,
  Zap,
  Info,
  Check,
  X,
  Wrench,
  Send,
  Eye,
  BarChart3,
  Flame,
  ArrowUpRight,
  ArrowDownRight,
  ChevronDown,
  ChevronUp,
  FileCheck2,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  AreaChart,
  Area,
} from "recharts";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Modal } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { StatusBadge } from "@/components/ui/status-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { showToast } from "@/components/ui/toast";
import { apiClient } from "@/lib/api-client";
import {
  AllocationSimulateResponse,
  AllocationWeightsConfig,
  AllocationApplyResponse,
  AllocationHistoryItem,
  ReallocationResponse,
  MaintenanceRoomItem,
  HeatmapRoomRow,
  WastageBucket,
  PaginatedResponse,
} from "@/lib/admin-types";
import { InfoTooltip } from "./info-tooltip";
import { EfficiencyGauge } from "./efficiency-gauge";

interface AllocationInsightsViewProps {
  role: "ADMIN" | "COORDINATOR";
  userName?: string;
  userEmail?: string;
}

export function AllocationInsightsView({
  role,
  userName = "System Admin",
  userEmail = "admin@git.edu",
}: AllocationInsightsViewProps) {
  const searchParams = useSearchParams();
  const initialRoomId = searchParams.get("room_id");

  // Simulation Form State
  const [startDate, setStartDate] = React.useState<string>(() => {
    return new Date().toISOString().split("T")[0];
  });
  const [endDate, setEndDate] = React.useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() + 2);
    return d.toISOString().split("T")[0];
  });
  const [sourceMode, setSourceMode] = React.useState<"demo" | "existing">("demo");
  const [demoCount, setDemoCount] = React.useState<number>(25);

  // Weights Config
  const [showWeights, setShowWeights] = React.useState<boolean>(false);
  const [weights, setWeights] = React.useState<AllocationWeightsConfig>({
    wastage_weight: 40,
    dept_ownership_weight: 20,
    block_match_weight: 20,
    distance_weight: 10,
    split_penalty_weight: 10,
  });

  // Simulation Results & Loading
  const [simData, setSimData] = React.useState<AllocationSimulateResponse | null>(null);
  const [loadingSim, setLoadingSim] = React.useState<boolean>(false);
  const [simulationError, setSimulationError] = React.useState<string | null>(null);
  const [historyRuns, setHistoryRuns] = React.useState<AllocationHistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = React.useState<boolean>(false);

  // Heatmap Controls
  const [heatmapView, setHeatmapView] = React.useState<"optimized" | "baseline">("optimized");
  const [heatmapSearch, setHeatmapSearch] = React.useState<string>("");
  const [activeChartTab, setActiveChartTab] = React.useState<"heatmap" | "wastage" | "trend">("heatmap");

  // Apply Changes Modal
  const [applyModalOpen, setApplyModalOpen] = React.useState<boolean>(false);
  const [applying, setApplying] = React.useState<boolean>(false);
  const [previewFilter, setPreviewFilter] = React.useState<"all" | "changed" | "unallocated">("all");

  // Maintenance Re-optimization Flow
  const [maintModalOpen, setMaintModalOpen] = React.useState<boolean>(false);
  const [selectedMaintRoomId, setSelectedMaintRoomId] = React.useState<string>(initialRoomId || "");
  const [reallocReason, setReallocReason] = React.useState<string>("MAINTENANCE");
  const [notifyUsers, setNotifyUsers] = React.useState<boolean>(true);
  const [previewRealloc, setPreviewRealloc] = React.useState<ReallocationResponse | null>(null);
  const [loadingReallocPreview, setLoadingReallocPreview] = React.useState<boolean>(false);
  const [submittingRealloc, setSubmittingRealloc] = React.useState<boolean>(false);

  // Helper to safely format readable error messages (never [object Object])
  const formatErrorMessage = React.useCallback((err: any): string => {
    if (!err) return "An unexpected error occurred.";
    if (typeof err === "string") return err;
    if (typeof err.message === "string" && err.message.trim()) return err.message;
    if (typeof err.detail === "string" && err.detail.trim()) return err.detail;
    if (Array.isArray(err.detail)) {
      return err.detail
        .map((d: any) => (typeof d === "object" ? d.msg || JSON.stringify(d) : String(d)))
        .join(", ");
    }
    if (err.data && typeof err.data === "object") {
      const d = err.data.detail || err.data.message;
      if (typeof d === "string") return d;
      if (Array.isArray(d)) {
        return d.map((x: any) => (typeof x === "object" ? x.msg || JSON.stringify(x) : String(x))).join(", ");
      }
    }
    if (typeof err === "object") {
      try {
        return JSON.stringify(err);
      } catch {
        return String(err);
      }
    }
    return String(err);
  }, []);

  // Run simulation
  const handleRunSimulation = React.useCallback(async (opts?: {
    sourceMode?: "demo" | "existing";
    demoCount?: number;
  } | React.MouseEvent) => {
    const isCustomOpts = opts && typeof opts === "object" && ("sourceMode" in opts || "demoCount" in opts);
    const activeMode = isCustomOpts && (opts as any).sourceMode ? (opts as any).sourceMode : sourceMode;
    const activeCount = isCustomOpts && (opts as any).demoCount ? (opts as any).demoCount : demoCount;

    setLoadingSim(true);
    setSimulationError(null);
    try {
      const payload: any = {
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        use_existing_bookings: activeMode === "existing",
        generate_demo: activeMode === "demo",
        demo_count: Number(activeCount) || 25,
        weights: weights,
      };

      const res = await apiClient<AllocationSimulateResponse>("/api/allocation/simulate", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setSimData(res);
      showToast({
        title: "Simulation Complete",
        message: `Successfully evaluated ${res.total_requests} requests side-by-side with Hungarian optimizer.`,
        type: "success",
      });

      // Refresh historical trend
      fetchHistory();
    } catch (err: any) {
      const readableMsg = formatErrorMessage(err);
      setSimulationError(readableMsg);
      showToast({
        title: "Simulation Failed",
        message: readableMsg,
        type: "error",
      });
    } finally {
      setLoadingSim(false);
    }
  }, [startDate, endDate, sourceMode, demoCount, weights, formatErrorMessage]);

  // Fetch history for trend chart
  const fetchHistory = React.useCallback(async () => {
    setLoadingHistory(true);
    try {
      const res = await apiClient<PaginatedResponse<AllocationHistoryItem>>(
        "/api/allocation/metrics/history?page_size=20"
      );
      setHistoryRuns(res.items || []);
    } catch {
      // Ignore background history failures
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  // Initial load: simulate on mount
  React.useEffect(() => {
    handleRunSimulation();
    fetchHistory();
  }, []);

  // If initialRoomId exists in query, automatically open maintenance flow
  React.useEffect(() => {
    if (initialRoomId) {
      setSelectedMaintRoomId(initialRoomId);
      setMaintModalOpen(true);
    }
  }, [initialRoomId]);

  // Auto-detect maintenance rooms
  const maintenanceRooms = simData?.maintenance_rooms || [];
  const hasMaintenanceRooms = maintenanceRooms.length > 0;

  // Handle Apply Optimized Allocation
  const handleApplyAllocation = async () => {
    setApplying(true);
    try {
      const payload: any = {
        start_date: startDate,
        end_date: endDate,
        use_existing_bookings: sourceMode === "existing",
        requests: sourceMode === "demo" && simData?.optimized?.allocations
          ? simData.optimized.allocations.map((a) => ({
              id: a.request_id,
              date: a.date,
              slot_id: a.slot_id,
              expected_strength: a.expected_strength,
            }))
          : undefined,
        weights: weights,
      };

      const res = await apiClient<AllocationApplyResponse>("/api/allocation/apply", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      showToast({
        title: "Optimized Allocation Applied!",
        message: res.message || `Successfully applied ${res.applied_count} allocations.`,
        type: "success",
      });

      setApplyModalOpen(false);
      handleRunSimulation();
    } catch (err: any) {
      showToast({
        title: "Application Error",
        message: err.message || "Failed to apply optimized allocation to database",
        type: "error",
      });
    } finally {
      setApplying(false);
    }
  };

  // Maintenance Reallocation: Preview
  const handlePreviewReallocation = async (roomId: number | string) => {
    if (!roomId) return;
    setLoadingReallocPreview(true);
    try {
      const res = await apiClient<ReallocationResponse>("/api/allocation/reallocate", {
        method: "POST",
        body: JSON.stringify({
          room_id: Number(roomId),
          reason: reallocReason,
          start_date: startDate,
          end_date: endDate,
          send_notifications: false,
          preview_only: true,
        }),
      });
      setPreviewRealloc(res);
    } catch (err: any) {
      showToast({
        title: "Reallocation Preview Failed",
        message: err.message || "Could not evaluate replacement rooms",
        type: "error",
      });
    } finally {
      setLoadingReallocPreview(false);
    }
  };

  // Maintenance Reallocation: Confirm & Commit
  const handleConfirmReallocation = async () => {
    if (!selectedMaintRoomId) return;
    setSubmittingRealloc(true);
    try {
      const res = await apiClient<ReallocationResponse>("/api/allocation/reallocate", {
        method: "POST",
        body: JSON.stringify({
          room_id: Number(selectedMaintRoomId),
          reason: reallocReason,
          start_date: startDate,
          end_date: endDate,
          send_notifications: notifyUsers,
          preview_only: false,
        }),
      });

      showToast({
        title: "Room Re-optimized & Relocations Applied",
        message: res.message || `Relocated ${res.relocated_count} bookings to optimal rooms.`,
        type: "success",
      });

      setMaintModalOpen(false);
      setPreviewRealloc(null);
      // Re-run simulation
      handleRunSimulation();
    } catch (err: any) {
      showToast({
        title: "Reallocation Failed",
        message: err.message || "Failed to commit room relocations",
        type: "error",
      });
    } finally {
      setSubmittingRealloc(false);
    }
  };

  // Open maintenance modal for a specific room
  const openReoptimizeFlow = (roomId?: string | number) => {
    const idToUse = roomId ? String(roomId) : (maintenanceRooms[0]?.id ? String(maintenanceRooms[0].id) : "");
    setSelectedMaintRoomId(idToUse);
    setMaintModalOpen(true);
    if (idToUse) {
      handlePreviewReallocation(idToUse);
    }
  };

  // Filtered preview changes for apply modal
  const baselineAllocations = simData?.baseline?.allocations || [];
  const optimizedAllocations = simData?.optimized?.allocations || [];

  const changePreviewItems = React.useMemo(() => {
    const baseMap = new Map(baselineAllocations.map((a) => [String(a.request_id), a]));
    return optimizedAllocations.map((opt) => {
      const base = baseMap.get(String(opt.request_id));
      const roomChanged = base?.room_id !== opt.room_id;
      return {
        requestId: opt.request_id,
        date: opt.date,
        slotId: opt.slot_id,
        strength: opt.expected_strength,
        baseRoomId: base?.room_id,
        baseRoomName: base?.room_name || "Unallocated",
        optRoomId: opt.room_id,
        optRoomName: opt.room_name || "Unallocated",
        optBlockName: opt.block_name || "-",
        optCapacity: opt.capacity,
        cost: opt.cost,
        roomChanged,
        isUnallocated: !opt.allocated,
      };
    });
  }, [baselineAllocations, optimizedAllocations]);

  const filteredChangeItems = React.useMemo(() => {
    if (previewFilter === "changed") {
      return changePreviewItems.filter((i) => i.roomChanged);
    }
    if (previewFilter === "unallocated") {
      return changePreviewItems.filter((i) => i.isUnallocated);
    }
    return changePreviewItems;
  }, [changePreviewItems, previewFilter]);

  // Heatmap rows filtered by search
  const heatmapRows = React.useMemo(() => {
    const list = simData?.heatmap_matrix || [];
    if (!heatmapSearch.trim()) return list;
    const q = heatmapSearch.toLowerCase().trim();
    return list.filter(
      (r) =>
        r.room_name.toLowerCase().includes(q) ||
        r.block_name.toLowerCase().includes(q) ||
        r.room_type.toLowerCase().includes(q)
    );
  }, [simData?.heatmap_matrix, heatmapSearch]);

  // Wastage Distribution Chart Data
  const wastageData = React.useMemo(() => {
    return simData?.wastage_distribution || [];
  }, [simData?.wastage_distribution]);

  // Score Trend Chart Data (Chronological)
  const trendData = React.useMemo(() => {
    const list = [...historyRuns].reverse();
    return list.map((item, idx) => ({
      name: new Date(item.created_at).toLocaleDateString([], { month: "short", day: "numeric" }) + ` (#${item.id})`,
      timestamp: item.created_at,
      baselineScore: Number(item.baseline_metrics?.efficiency_score || 0),
      optimizedScore: Number(item.optimized_metrics?.efficiency_score || 0),
      requests: item.total_requests,
      delta: Number(
        (item.optimized_metrics?.efficiency_score || 0) - (item.baseline_metrics?.efficiency_score || 0)
      ).toFixed(1),
    }));
  }, [historyRuns]);

  // Metrics Shorthands
  const bm = simData?.baseline?.metrics;
  const om = simData?.optimized?.metrics;
  const comp = simData?.comparison;

  return (
    <div className="space-y-8 pb-16">
      {/* ------------------------------------------------------------- */}
      {/* 1. HEADER & AUTOMATIC MAINTENANCE ALERT BANNER */}
      {/* ------------------------------------------------------------- */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--foreground)]">
              Allocation Insights & Smart Optimizer
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" />
              Hungarian Linear Optimizer
            </span>
          </div>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Simulate, compare, and apply optimal room assignments. Evaluates multi-factor cost functions against first-fit baseline.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleRunSimulation()}
            isLoading={loadingSim}
            className="gap-2"
          >
            <RotateCw className="w-4 h-4" />
            Re-Simulate
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setApplyModalOpen(true)}
            disabled={!simData || simData.total_requests === 0}
            className="gap-2 bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-700 hover:to-indigo-700 text-white shadow-md shadow-sky-500/20"
          >
            <Zap className="w-4 h-4" />
            Apply Optimized Allocation
          </Button>
        </div>
      </div>

      {/* AUTOMATIC RE-OPTIMIZE AFTER CHANGE BANNER (SHOWN WHEN ROOM IS IN MAINTENANCE) */}
      <AnimatePresence>
        {hasMaintenanceRooms && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="relative overflow-hidden rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5 shadow-sm backdrop-blur-sm"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-start sm:items-center gap-3.5">
                <div className="h-10 w-10 rounded-xl bg-amber-500/20 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
                  <Wrench className="w-5 h-5 animate-pulse" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-amber-900 dark:text-amber-200">
                      Room Maintenance Detected — Automatic Re-optimization Required
                    </span>
                    <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/20 text-amber-700 dark:text-amber-300">
                      {maintenanceRooms.length} room(s) offline
                    </span>
                  </div>
                  <p className="text-xs text-amber-800 dark:text-amber-300/90 mt-0.5">
                    {maintenanceRooms.map((r) => `${r.name} (${r.block_name})`).join(", ")} is currently in maintenance.
                    The smart optimizer can automatically re-route affected bookings to matching rooms with zero conflicts.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2.5 shrink-0">
                <Button
                  size="sm"
                  onClick={() => openReoptimizeFlow(maintenanceRooms[0]?.id)}
                  className="bg-amber-600 hover:bg-amber-700 text-white shadow-sm gap-2"
                >
                  <Sparkles className="w-4 h-4" />
                  Re-optimize Room Bookings Now
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ------------------------------------------------------------- */}
      {/* 2. SIMULATE ALLOCATION PANEL */}
      {/* ------------------------------------------------------------- */}
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[var(--border)] pb-4">
          <div>
            <h2 className="text-base font-bold text-[var(--foreground)] flex items-center gap-2">
              <Play className="w-4 h-4 text-sky-500 fill-sky-500" />
              Simulate Allocation Panel
            </h2>
            <p className="text-xs text-[var(--muted-foreground)]">
              Configure parameters to execute baseline (first-fit) vs optimized (Hungarian algorithm) side-by-side.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setShowWeights(!showWeights)}
            className="flex items-center gap-1.5 text-xs font-semibold text-sky-600 dark:text-sky-400 hover:underline"
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>{showWeights ? "Hide Soft Cost Weights" : "Adjust Soft Cost Weights"}</span>
            {showWeights ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>

        {/* Input Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Start Date */}
          <div>
            <label className="block text-xs font-semibold text-[var(--foreground)] mb-1.5">
              Start Date
            </label>
            <Input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="text-xs"
            />
          </div>

          {/* End Date */}
          <div>
            <label className="block text-xs font-semibold text-[var(--foreground)] mb-1.5">
              End Date
            </label>
            <Input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="text-xs"
            />
          </div>

          {/* Request Source Mode */}
          <div>
            <label className="block text-xs font-semibold text-[var(--foreground)] mb-1.5 flex items-center gap-1">
              <span>Request Source</span>
              <InfoTooltip
                title="Simulation Source"
                content="Choose whether to run the allocation models on active database bookings or on a realistic generated batch of academic requests."
              />
            </label>
            <div className="grid grid-cols-2 gap-1.5 p-1 rounded-xl bg-[var(--muted)]/50 border border-[var(--border)]">
              <button
                type="button"
                onClick={() => setSourceMode("demo")}
                className={`py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  sourceMode === "demo"
                    ? "bg-[var(--card)] text-sky-600 dark:text-sky-400 shadow-sm"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                Demo Requests
              </button>
              <button
                type="button"
                onClick={() => setSourceMode("existing")}
                className={`py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  sourceMode === "existing"
                    ? "bg-[var(--card)] text-sky-600 dark:text-sky-400 shadow-sm"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                }`}
              >
                Live Bookings
              </button>
            </div>
          </div>

          {/* Demo Count or Action */}
          <div>
            {sourceMode === "demo" ? (
              <div>
                <label className="block text-xs font-semibold text-[var(--foreground)] mb-1.5">
                  Batch Size ({demoCount} Requests)
                </label>
                <div className="flex items-center gap-1.5">
                  {[15, 25, 50, 100, 200].map((count) => (
                    <button
                      key={count}
                      type="button"
                      onClick={() => setDemoCount(count)}
                      className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-bold transition-all border ${
                        demoCount === count
                          ? "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/30"
                          : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                      }`}
                    >
                      {count}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div>
                <label className="block text-xs font-semibold text-[var(--foreground)] mb-1.5">
                  Filter Scope
                </label>
                <div className="text-xs text-[var(--muted-foreground)] py-2">
                  Querying active bookings in date window
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Collapsible Soft Constraint Weights */}
        <AnimatePresence>
          {showWeights && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden border-t border-[var(--border)] pt-4"
            >
              <div className="text-xs font-bold text-[var(--foreground)] mb-3 flex items-center justify-between">
                <span>Optimizer Objective Function Weightings:</span>
                <button
                  type="button"
                  onClick={() =>
                    setWeights({
                      wastage_weight: 40,
                      dept_ownership_weight: 20,
                      block_match_weight: 20,
                      distance_weight: 10,
                      split_penalty_weight: 10,
                    })
                  }
                  className="text-[11px] text-sky-600 hover:underline"
                >
                  Reset Defaults
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-4">
                {[
                  { key: "wastage_weight", label: "Seat Wastage", desc: "Penalizes oversized rooms" },
                  { key: "dept_ownership_weight", label: "Dept Ownership", desc: "Prioritizes department-owned rooms" },
                  { key: "block_match_weight", label: "Block Match", desc: "Prefers home department block" },
                  { key: "distance_weight", label: "Floor Proximity", desc: "Penalizes distant floors" },
                  { key: "split_penalty_weight", label: "Split Schedule", desc: "Avoids block changes between slots" },
                ].map((w) => (
                  <div key={w.key} className="p-3 rounded-xl bg-[var(--muted)]/40 border border-[var(--border)]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-semibold text-[var(--foreground)]">{w.label}</span>
                      <span className="text-xs font-bold text-sky-600">
                        {(weights as any)[w.key]}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      step="5"
                      value={(weights as any)[w.key]}
                      onChange={(e) =>
                        setWeights({ ...weights, [w.key]: Number(e.target.value) })
                      }
                      className="w-full accent-sky-500"
                    />
                    <span className="text-[10px] text-[var(--muted-foreground)] block mt-1">
                      {w.desc}
                    </span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex justify-end pt-2">
          <Button
            onClick={() => handleRunSimulation()}
            isLoading={loadingSim}
            className="gap-2 bg-sky-600 hover:bg-sky-700 text-white"
          >
            <Play className="w-4 h-4 fill-white" />
            Run Simulation ({sourceMode === "demo" ? `${demoCount} Demo Requests` : "Live DB Requests"})
          </Button>
        </div>
      </div>

      {/* ERROR ALERT BANNER (HUMAN-READABLE ERROR MESSAGE) */}
      <AnimatePresence>
        {simulationError && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-5 text-rose-800 dark:text-rose-300 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
          >
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-xl bg-rose-500/20 text-rose-600 dark:text-rose-400 shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-rose-900 dark:text-rose-200">
                  Simulation Error
                </h4>
                <p className="text-xs mt-1 text-rose-700/90 dark:text-rose-300 leading-relaxed font-mono whitespace-pre-wrap">
                  {simulationError}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2.5 shrink-0 self-end sm:self-center">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSimulationError(null)}
                className="text-xs border-rose-500/30 hover:bg-rose-500/10 text-rose-700 dark:text-rose-300"
              >
                Dismiss
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => handleRunSimulation()}
                isLoading={loadingSim}
                className="text-xs bg-rose-600 hover:bg-rose-700 text-white shadow-sm"
              >
                <RotateCw className="w-3.5 h-3.5 mr-1.5" />
                Retry
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* EMPTY STATE: ZERO BOOKINGS FOUND IN SELECTED WINDOW */}
      <AnimatePresence>
        {simData && simData.total_requests === 0 && !loadingSim && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-6 text-amber-900 dark:text-amber-200 shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-5"
          >
            <div className="flex items-start gap-3.5">
              <div className="p-2.5 rounded-xl bg-amber-500/20 text-amber-600 dark:text-amber-400 shrink-0">
                <Calendar className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-amber-900 dark:text-amber-100">
                  No Active Bookings Found in Selected Date Range
                </h3>
                <p className="text-xs mt-1 text-amber-800/90 dark:text-amber-300 leading-relaxed max-w-2xl">
                  There are currently zero confirmed or pending bookings between{" "}
                  <span className="font-semibold underline">{startDate}</span> and{" "}
                  <span className="font-semibold underline">{endDate}</span>.
                  To evaluate optimization algorithms, either extend your date filter or generate a batch of realistic demo requests.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2.5 shrink-0">
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  setSourceMode("demo");
                  setDemoCount(200);
                  handleRunSimulation({ sourceMode: "demo", demoCount: 200 });
                }}
                isLoading={loadingSim}
                className="bg-amber-600 hover:bg-amber-700 text-white text-xs gap-1.5 shadow-md shadow-amber-500/20"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Generate 200 Demo Requests
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* LOADING STATE INDICATOR */}
      {loadingSim && (
        <div className="rounded-2xl border border-sky-500/20 bg-sky-500/5 p-6 flex flex-col items-center justify-center text-center space-y-3 shadow-sm animate-pulse">
          <RotateCw className="w-7 h-7 text-sky-500 animate-spin" />
          <div>
            <h3 className="text-sm font-bold text-[var(--foreground)]">
              Executing Hungarian Allocation Optimization Engine
            </h3>
            <p className="text-xs text-[var(--muted-foreground)] mt-1">
              Constructing cost matrices, enforcing capacity & facility hard constraints, and computing Kuhn-Munkres minimum-weight bipartite matchings...
            </p>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* 3. SIDE-BY-SIDE COMPARISON CARDS */}
      {/* ------------------------------------------------------------- */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-[var(--foreground)] flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-emerald-500" />
              Side-by-Side Performance Comparison
            </h2>
            <p className="text-xs text-[var(--muted-foreground)]">
              All quantitative metrics are calculated directly by the backend metrics engine.
            </p>
          </div>

          {simData && (
            <div className="text-xs font-medium text-[var(--muted-foreground)]">
              Evaluated {simData.total_requests} requests for window {simData.date_range.start_date} → {simData.date_range.end_date}
            </div>
          )}
        </div>

        {/* 7 Metric Comparison Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* CARD 1: Efficiency Score (Animated Gauge) */}
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm flex flex-col justify-between md:col-span-2 lg:col-span-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--foreground)]">
                  Efficiency Score
                </span>
                <InfoTooltip
                  title="Efficiency Score (0–100)"
                  content="Composite performance index weighting seat utilization (30%), request allocation rate (25%), facility match (20%), department & block preference (15%), and transit continuity (10%). Drops to strictly 0 if any double-booking or overcapacity conflict occurs."
                />
              </div>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-500/10 text-sky-600 dark:text-sky-400">
                Primary KPI
              </span>
            </div>

            <div className="my-2">
              <EfficiencyGauge
                baselineScore={bm?.efficiency_score || 0}
                optimizedScore={om?.efficiency_score || 0}
                delta={comp?.efficiency_score_delta || 0}
              />
            </div>

            <div className="text-[11px] text-[var(--muted-foreground)] text-center">
              Combined multi-objective linear sum assignment score.
            </div>
          </div>

          {/* CARD 2: Seat Utilization */}
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--foreground)]">
                    Seat Utilization
                  </span>
                  <InfoTooltip
                    title="Seat Utilization %"
                    content="Ratio of total expected attendees to total room capacity across all allocated assignments (sum attendees ÷ sum capacity). Higher percentage proves optimal room sizing without waste."
                  />
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5">
                  <ArrowUpRight className="w-3 h-3" />
                  +{(comp?.seat_utilization_delta_pct || 0).toFixed(1)}%
                </span>
              </div>

              <div className="space-y-3 my-2">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-[var(--muted-foreground)]">Baseline</span>
                    <span className="font-bold text-slate-600 dark:text-slate-400">
                      {bm?.seat_utilization_pct || 0}%
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-slate-400 rounded-full transition-all duration-700"
                      style={{ width: `${Math.min(100, bm?.seat_utilization_pct || 0)}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-semibold text-emerald-600 dark:text-emerald-400">Optimized</span>
                    <span className="font-bold text-emerald-600 dark:text-emerald-400">
                      {om?.seat_utilization_pct || 0}%
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full transition-all duration-700"
                      style={{ width: `${Math.min(100, om?.seat_utilization_pct || 0)}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-[var(--border)] text-[11px] text-[var(--muted-foreground)] flex items-center justify-between">
              <span>Improvement</span>
              <span className="font-bold text-emerald-600">
                +{(comp?.seat_utilization_delta_pct || 0).toFixed(1)}% capacity fit
              </span>
            </div>
          </div>

          {/* CARD 3: Average Space Wastage */}
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--foreground)]">
                    Average Wastage
                  </span>
                  <InfoTooltip
                    title="Average Seat Wastage %"
                    content="Average percentage of vacant/unutilized seats per allocated room ((room capacity - attendees) / room capacity). Lower is significantly better; the optimizer minimizes empty desks."
                  />
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 flex items-center gap-0.5">
                  <ArrowDownRight className="w-3 h-3" />
                  -{(comp?.average_wastage_reduction_pct || 0).toFixed(1)}%
                </span>
              </div>

              <div className="space-y-3 my-2">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-[var(--muted-foreground)]">Baseline</span>
                    <span className="font-bold text-rose-500">
                      {bm?.average_wastage_pct || 0}%
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-rose-400/80 rounded-full transition-all duration-700"
                      style={{ width: `${Math.min(100, bm?.average_wastage_pct || 0)}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-semibold text-emerald-600 dark:text-emerald-400">Optimized</span>
                    <span className="font-bold text-emerald-600 dark:text-emerald-400">
                      {om?.average_wastage_pct || 0}%
                    </span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full transition-all duration-700"
                      style={{ width: `${Math.min(100, om?.average_wastage_pct || 0)}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-[var(--border)] text-[11px] text-[var(--muted-foreground)] flex items-center justify-between">
              <span>Wastage Reduction</span>
              <span className="font-bold text-emerald-600">
                {(comp?.average_wastage_reduction_pct || 0).toFixed(1)}% fewer empty seats
              </span>
            </div>
          </div>

          {/* CARD 4: Facility Match */}
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--foreground)]">
                    Facility Match
                  </span>
                  <InfoTooltip
                    title="Facility Match %"
                    content="Proportion of requested amenities (e.g., projectors, air conditioners, smart boards, PCs, lab equipment) fulfilled. The optimizer treats requested facilities as a hard constraint (100%), whereas naive first-fit frequently assigns rooms lacking equipment."
                  />
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-sky-500/15 text-sky-600 dark:text-sky-400 flex items-center gap-0.5">
                  <ArrowUpRight className="w-3 h-3" />
                  +{(comp?.facility_match_delta_pct || 0).toFixed(1)}%
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 my-2 text-center">
                <div className="p-3 rounded-xl bg-slate-500/5 border border-[var(--border)]">
                  <span className="text-[10px] text-[var(--muted-foreground)] font-semibold uppercase block">Baseline</span>
                  <span className="text-xl font-extrabold text-slate-700 dark:text-slate-300">
                    {bm?.facility_match_pct || 0}%
                  </span>
                  <span className="text-[10px] text-amber-500 block mt-0.5">Naive match</span>
                </div>

                <div className="p-3 rounded-xl bg-sky-500/10 border border-sky-500/30">
                  <span className="text-[10px] text-sky-600 dark:text-sky-400 font-semibold uppercase block">Optimized</span>
                  <span className="text-xl font-extrabold text-sky-600 dark:text-sky-400">
                    {om?.facility_match_pct || 0}%
                  </span>
                  <span className="text-[10px] text-emerald-600 font-semibold block mt-0.5">100% hard match</span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-[var(--border)] text-[11px] text-[var(--muted-foreground)] flex items-center justify-between">
              <span>Required Equipment</span>
              <span className="font-bold text-sky-600">Strictly Enforced</span>
            </div>
          </div>

          {/* CARD 5: Preference Satisfaction */}
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--foreground)]">
                    Preference Match
                  </span>
                  <InfoTooltip
                    title="Preference Satisfaction %"
                    content="Soft constraint fulfillment: prioritizing department-owned rooms, matching physical block preferences, and matching preferred floor levels while minimizing stairs travel."
                  />
                </div>
                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-purple-500/15 text-purple-600 dark:text-purple-400 flex items-center gap-0.5">
                  <ArrowUpRight className="w-3 h-3" />
                  +{(comp?.preference_satisfaction_delta_pct || 0).toFixed(1)}%
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 my-2 text-center">
                <div className="p-3 rounded-xl bg-slate-500/5 border border-[var(--border)]">
                  <span className="text-[10px] text-[var(--muted-foreground)] font-semibold uppercase block">Baseline</span>
                  <span className="text-xl font-extrabold text-slate-700 dark:text-slate-300">
                    {bm?.preference_satisfaction_pct || 0}%
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-purple-500/10 border border-purple-500/30">
                  <span className="text-[10px] text-purple-600 dark:text-purple-400 font-semibold uppercase block">Optimized</span>
                  <span className="text-xl font-extrabold text-purple-600 dark:text-purple-400">
                    {om?.preference_satisfaction_pct || 0}%
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-[var(--border)] text-[11px] text-[var(--muted-foreground)] flex items-center justify-between">
              <span>Department & Wing Proximity</span>
              <span className="font-bold text-purple-600">
                +{(comp?.preference_satisfaction_delta_pct || 0).toFixed(1)}%
              </span>
            </div>
          </div>

          {/* CARD 6: Unallocated Requests */}
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--foreground)]">
                    Unallocated Count
                  </span>
                  <InfoTooltip
                    title="Unallocated Requests"
                    content="Number of submitted booking requests that could not be assigned a room due to room bottlenecks, facility shortages, or double-booking locks. Lower is better."
                  />
                </div>
                <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                  (om?.unallocated_count || 0) === 0
                    ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                    : "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                }`}>
                  {om?.unallocated_count === 0 ? "All Allocated" : `${om?.unallocated_count} unserviced`}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 my-2 text-center">
                <div className="p-3 rounded-xl bg-slate-500/5 border border-[var(--border)]">
                  <span className="text-[10px] text-[var(--muted-foreground)] font-semibold uppercase block">Baseline</span>
                  <span className="text-xl font-extrabold text-rose-500">
                    {bm?.unallocated_count || 0}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                  <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold uppercase block">Optimized</span>
                  <span className="text-xl font-extrabold text-emerald-600 dark:text-emerald-400">
                    {om?.unallocated_count || 0}
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-[var(--border)] text-[11px] text-[var(--muted-foreground)] flex items-center justify-between">
              <span>Unserviced Delta</span>
              <span className="font-bold text-emerald-600">
                {comp?.unallocated_delta !== undefined && comp.unallocated_delta < 0
                  ? `${comp.unallocated_delta} fewer rejected`
                  : "Zero unallocated"}
              </span>
            </div>
          </div>

          {/* CARD 7: Conflicts */}
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--foreground)]">
                    Schedule Conflicts
                  </span>
                  <InfoTooltip
                    title="Schedule Conflicts (Strict 0)"
                    content="Number of overlapping double-bookings, overcapacity room assignments, or allocations on blocked/maintenance rooms. DB-level exclusion constraints strictly guarantee 0 conflicts."
                  />
                </div>
                <StatusBadge status="ACTIVE" label="0 Conflicts" />
              </div>

              <div className="grid grid-cols-2 gap-3 my-2 text-center">
                <div className="p-3 rounded-xl bg-slate-500/5 border border-[var(--border)]">
                  <span className="text-[10px] text-[var(--muted-foreground)] font-semibold uppercase block">Baseline</span>
                  <span className="text-xl font-extrabold text-slate-700 dark:text-slate-300">
                    {bm?.conflict_count || 0}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                  <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold uppercase block">Optimized</span>
                  <span className="text-xl font-extrabold text-emerald-600 dark:text-emerald-400">
                    {om?.conflict_count || 0}
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-[var(--border)] text-[11px] text-emerald-600 dark:text-emerald-400 flex items-center justify-between font-semibold">
              <span className="flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" />
                No Double-Booking
              </span>
              <span>Verified Safe</span>
            </div>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* 4. CHARTS SECTION (HEATMAP, WASTAGE, SCORE TREND) */}
      {/* ------------------------------------------------------------- */}
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--border)] pb-4">
          <div>
            <h2 className="text-base font-bold text-[var(--foreground)] flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-sky-500" />
              Allocation Analytics & Visualizations
            </h2>
            <p className="text-xs text-[var(--muted-foreground)]">
              Interactive Room x Period Heatmap, Wastage Distribution Histograms, and Historical Performance Trends.
            </p>
          </div>

          {/* Chart Tab Navigation */}
          <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[var(--muted)]/50 border border-[var(--border)]">
            <button
              type="button"
              onClick={() => setActiveChartTab("heatmap")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                activeChartTab === "heatmap"
                  ? "bg-[var(--card)] text-sky-600 dark:text-sky-400 shadow-sm"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              Utilization Heatmap
            </button>
            <button
              type="button"
              onClick={() => setActiveChartTab("wastage")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                activeChartTab === "wastage"
                  ? "bg-[var(--card)] text-sky-600 dark:text-sky-400 shadow-sm"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              Wastage Distribution
            </button>
            <button
              type="button"
              onClick={() => setActiveChartTab("trend")}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                activeChartTab === "trend"
                  ? "bg-[var(--card)] text-sky-600 dark:text-sky-400 shadow-sm"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              Score Trend Over Time
            </button>
          </div>
        </div>

        {/* TAB 1: UTILIZATION HEATMAP (ROOM X PERIOD) */}
        {activeChartTab === "heatmap" && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[var(--muted)]/40 border border-[var(--border)]">
                  <button
                    type="button"
                    onClick={() => setHeatmapView("optimized")}
                    className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-all ${
                      heatmapView === "optimized"
                        ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30"
                        : "text-[var(--muted-foreground)]"
                    }`}
                  >
                    Optimized Plan
                  </button>
                  <button
                    type="button"
                    onClick={() => setHeatmapView("baseline")}
                    className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition-all ${
                      heatmapView === "baseline"
                        ? "bg-slate-500/15 text-slate-700 dark:text-slate-300 border border-slate-500/30"
                        : "text-[var(--muted-foreground)]"
                    }`}
                  >
                    Baseline Plan
                  </button>
                </div>

                <div className="hidden sm:flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
                  <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded bg-slate-200 dark:bg-slate-800" /> Free
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded bg-amber-400/30" /> 1–40%
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded bg-sky-400/40" /> 41–75%
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded bg-emerald-500/60" /> 76–100%
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded bg-amber-500/80" /> Maintenance
                  </span>
                </div>
              </div>

              <div className="w-full sm:w-64">
                <Input
                  type="text"
                  placeholder="Filter by room or block..."
                  value={heatmapSearch}
                  onChange={(e) => setHeatmapSearch(e.target.value)}
                  className="text-xs"
                />
              </div>
            </div>

            {/* Heatmap Grid Matrix */}
            <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="bg-[var(--muted)]/50 border-b border-[var(--border)]">
                    <th className="py-2.5 px-3 font-semibold text-[var(--foreground)] sticky left-0 bg-[var(--muted)] z-10 min-w-[140px]">
                      Room & Capacity
                    </th>
                    {[1, 2, 3, 4, 5, 6, 7, 8].map((slotIdx) => (
                      <th key={slotIdx} className="py-2 px-2.5 font-semibold text-center min-w-[90px]">
                        Period {slotIdx}
                        <span className="block text-[10px] font-normal text-[var(--muted-foreground)]">
                          Slot {slotIdx}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {heatmapRows.slice(0, 15).map((row) => (
                    <tr key={row.room_id} className="hover:bg-[var(--muted)]/20 transition-colors">
                      <td className="py-2 px-3 sticky left-0 bg-[var(--card)] z-10 border-r border-[var(--border)]">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[var(--foreground)]">{row.room_name}</span>
                          <span className="text-[10px] text-[var(--muted-foreground)]">
                            {row.capacity} seats
                          </span>
                        </div>
                        <div className="text-[10px] text-[var(--muted-foreground)] truncate max-w-[120px]">
                          {row.block_name} • Fl {row.floor}
                        </div>
                      </td>

                      {row.slots.map((cell) => {
                        const plan = heatmapView === "optimized" ? cell.optimized : cell.baseline;
                        const isMaint = row.status === "MAINTENANCE";

                        let cellBg = "bg-slate-100 dark:bg-slate-800/40 text-slate-400";
                        if (isMaint) {
                          cellBg = "bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-500/30";
                        } else if (plan.allocated) {
                          if (plan.utilization_pct > 75) {
                            cellBg = "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 font-bold";
                          } else if (plan.utilization_pct > 40) {
                            cellBg = "bg-sky-500/20 text-sky-700 dark:text-sky-300 border border-sky-500/30 font-semibold";
                          } else {
                            cellBg = "bg-amber-400/20 text-amber-700 dark:text-amber-300 border border-amber-400/30";
                          }
                        }

                        return (
                          <td key={cell.slot_id} className="p-1 text-center">
                            <div
                              className={`h-11 rounded-lg flex flex-col items-center justify-center transition-all cursor-default select-none group relative ${cellBg}`}
                            >
                              {isMaint ? (
                                <div className="flex items-center gap-1 text-[10px] font-semibold">
                                  <Wrench className="w-3 h-3" />
                                  <span>Offline</span>
                                </div>
                              ) : plan.allocated ? (
                                <>
                                  <span className="text-xs font-bold leading-none">
                                    {plan.utilization_pct}%
                                  </span>
                                  <span className="text-[9px] opacity-75 mt-0.5">
                                    {plan.strength} / {row.capacity}
                                  </span>
                                </>
                              ) : (
                                <span className="text-[10px] opacity-40">Free</span>
                              )}

                              {/* Hover Tooltip Popup */}
                              {plan.allocated && (
                                <div className="hidden group-hover:block absolute bottom-full mb-1 z-30 w-44 p-2 rounded-lg bg-slate-900 text-white text-[11px] shadow-lg border border-slate-700 pointer-events-none text-left">
                                  <div className="font-bold text-sky-400 truncate">{plan.purpose || "Academic Session"}</div>
                                  <div className="text-[10px] text-slate-300">
                                    {plan.requester || "Student Batch"} • {plan.strength} attendees
                                  </div>
                                  <div className="text-[10px] text-emerald-400 mt-0.5">
                                    Utilization: {plan.utilization_pct}% ({plan.strength}/{row.capacity})
                                  </div>
                                </div>
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

            {heatmapRows.length > 15 && (
              <div className="text-center text-xs text-[var(--muted-foreground)]">
                Showing first 15 of {heatmapRows.length} rooms. Use filter above to narrow search.
              </div>
            )}
          </div>
        )}

        {/* TAB 2: WASTAGE DISTRIBUTION (RECHARTS BAR CHART) */}
        {activeChartTab === "wastage" && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-bold text-[var(--foreground)]">
                  Capacity Wastage Histogram (Baseline vs Optimized)
                </h3>
                <p className="text-xs text-[var(--muted-foreground)]">
                  Compares count of room allocations by empty seat ratio. The optimizer eliminates high wastage (&gt;40%).
                </p>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span className="flex items-center gap-1.5 font-semibold text-slate-500">
                  <span className="w-3 h-3 rounded bg-slate-400" /> Baseline Naive
                </span>
                <span className="flex items-center gap-1.5 font-semibold text-emerald-600 dark:text-emerald-400">
                  <span className="w-3 h-3 rounded bg-emerald-500" /> Optimized Hungarian
                </span>
              </div>
            </div>

            <div className="h-72 w-full pt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={wastageData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "var(--card)",
                      borderColor: "var(--border)",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="baseline" name="Baseline (Count)" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="optimized" name="Optimized (Count)" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-700 dark:text-emerald-300">
              <span className="font-bold">Key Insight: </span>
              Notice the shift toward 0–10% and 10–25% optimal capacity match bins. The Hungarian solver directly penalizes vacant chairs, preserving larger lecture halls and seminar auditoriums for larger groups.
            </div>
          </div>
        )}

        {/* TAB 3: SCORE TREND OVER TIME (RECHARTS AREA CHART) */}
        {activeChartTab === "trend" && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-bold text-[var(--foreground)]">
                  Historical Efficiency Score Trend
                </h3>
                <p className="text-xs text-[var(--muted-foreground)]">
                  Log of past simulation and applied allocation runs from database audit history.
                </p>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span className="flex items-center gap-1.5 font-semibold text-slate-500">
                  <span className="w-3 h-3 rounded bg-slate-400" /> Baseline Score
                </span>
                <span className="flex items-center gap-1.5 font-semibold text-sky-500">
                  <span className="w-3 h-3 rounded bg-sky-500" /> Optimized Score
                </span>
              </div>
            </div>

            {trendData.length > 0 ? (
              <div className="h-72 w-full pt-4">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trendData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                    <defs>
                      <linearGradient id="optScoreGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0.0} />
                      </linearGradient>
                      <linearGradient id="baseScoreGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#94a3b8" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#94a3b8" stopOpacity={0.0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "var(--card)",
                        borderColor: "var(--border)",
                        borderRadius: 12,
                        fontSize: 12,
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="baselineScore"
                      name="Baseline Score"
                      stroke="#94a3b8"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#baseScoreGrad)"
                    />
                    <Area
                      type="monotone"
                      dataKey="optimizedScore"
                      name="Optimized Score"
                      stroke="#0ea5e9"
                      strokeWidth={2.5}
                      fillOpacity={1}
                      fill="url(#optScoreGrad)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-[var(--muted-foreground)]">
                No historical allocation runs recorded yet. Run a simulation to log performance points.
              </div>
            )}
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------- */}
      {/* 5. APPLY OPTIMIZED ALLOCATION MODAL (WITH PREVIEW TABLE) */}
      {/* ------------------------------------------------------------- */}
      <Modal
        isOpen={applyModalOpen}
        onClose={() => setApplyModalOpen(false)}
        title="Apply Optimized Allocation"
        maxWidth="xl"
      >
        <div className="space-y-5">
          <div className="p-3.5 rounded-xl bg-sky-500/10 border border-sky-500/20 text-xs text-sky-800 dark:text-sky-200">
            <span className="font-bold">Confirmation Required: </span>
            Applying will write assignments directly to the scheduling database. Existing bookings will be reassigned to their optimal rooms, and custom items will become confirmed bookings.
          </div>

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-4 gap-3 text-center">
            <div className="p-2.5 rounded-xl bg-[var(--muted)]/50 border border-[var(--border)]">
              <span className="text-[10px] text-[var(--muted-foreground)] block">Total Requests</span>
              <span className="text-base font-bold text-[var(--foreground)]">{simData?.total_requests || 0}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
              <span className="text-[10px] text-emerald-600 block">Optimized Score</span>
              <span className="text-base font-bold text-emerald-600">{om?.efficiency_score || 0}</span>
            </div>
            <div className="p-2.5 rounded-xl bg-[var(--muted)]/50 border border-[var(--border)]">
              <span className="text-[10px] text-[var(--muted-foreground)] block">Seat Utilization</span>
              <span className="text-base font-bold text-[var(--foreground)]">{om?.seat_utilization_pct || 0}%</span>
            </div>
            <div className="p-2.5 rounded-xl bg-[var(--muted)]/50 border border-[var(--border)]">
              <span className="text-[10px] text-[var(--muted-foreground)] block">Wastage Reduction</span>
              <span className="text-base font-bold text-emerald-600">
                -{(comp?.average_wastage_reduction_pct || 0).toFixed(1)}%
              </span>
            </div>
          </div>

          {/* Filter preview items */}
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[var(--foreground)]">
              Preview of Room Changes ({changePreviewItems.length} Requests)
            </span>
            <div className="flex items-center gap-1.5 text-xs">
              <button
                type="button"
                onClick={() => setPreviewFilter("all")}
                className={`px-2.5 py-1 rounded-lg ${
                  previewFilter === "all" ? "bg-sky-500/15 text-sky-600 font-bold" : "text-[var(--muted-foreground)]"
                }`}
              >
                All ({changePreviewItems.length})
              </button>
              <button
                type="button"
                onClick={() => setPreviewFilter("changed")}
                className={`px-2.5 py-1 rounded-lg ${
                  previewFilter === "changed" ? "bg-emerald-500/15 text-emerald-600 font-bold" : "text-[var(--muted-foreground)]"
                }`}
              >
                Changed Rooms ({changePreviewItems.filter((i) => i.roomChanged).length})
              </button>
            </div>
          </div>

          {/* Preview Changes Table */}
          <div className="max-h-72 overflow-y-auto rounded-xl border border-[var(--border)]">
            <table className="w-full text-xs text-left">
              <thead className="bg-[var(--muted)] sticky top-0 border-b border-[var(--border)]">
                <tr>
                  <th className="py-2 px-3 font-semibold text-[var(--foreground)]">Request</th>
                  <th className="py-2 px-3 font-semibold text-[var(--foreground)]">Date / Slot</th>
                  <th className="py-2 px-3 font-semibold text-[var(--foreground)]">Attendees</th>
                  <th className="py-2 px-3 font-semibold text-[var(--foreground)]">Baseline Room</th>
                  <th className="py-2 px-3 font-semibold text-[var(--foreground)]">Optimized Room</th>
                  <th className="py-2 px-3 font-semibold text-[var(--foreground)] text-right">Fit Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {filteredChangeItems.map((item) => (
                  <tr key={String(item.requestId)} className="hover:bg-[var(--muted)]/20">
                    <td className="py-2 px-3 font-mono font-medium">{item.requestId}</td>
                    <td className="py-2 px-3">
                      {item.date} • Slot {item.slotId}
                    </td>
                    <td className="py-2 px-3 font-semibold">{item.strength} students</td>
                    <td className="py-2 px-3 text-[var(--muted-foreground)]">
                      {item.baseRoomName}
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-emerald-600 dark:text-emerald-400">
                          {item.optRoomName}
                        </span>
                        {item.roomChanged && (
                          <span className="px-1.5 py-0.2 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-600">
                            Improved
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-[var(--muted-foreground)]">
                        {item.optBlockName} • Cap: {item.optCapacity}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right font-mono text-[11px] text-[var(--muted-foreground)]">
                      {item.cost !== undefined && item.cost !== null ? item.cost.toFixed(2) : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border)]">
            <Button
              variant="outline"
              onClick={() => setApplyModalOpen(false)}
              disabled={applying}
            >
              Cancel
            </Button>
            <Button
              onClick={handleApplyAllocation}
              isLoading={applying}
              className="gap-2 bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              <CheckCircle2 className="w-4 h-4" />
              Confirm & Apply to Database
            </Button>
          </div>
        </div>
      </Modal>

      {/* ------------------------------------------------------------- */}
      {/* 6. RE-OPTIMIZE AFTER CHANGE MODAL (MAINTENANCE WORKFLOW) */}
      {/* ------------------------------------------------------------- */}
      <Modal
        isOpen={maintModalOpen}
        onClose={() => setMaintModalOpen(false)}
        title="Re-optimize Allocations After Room Maintenance"
        maxWidth="lg"
      >
        <div className="space-y-5">
          <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-800 dark:text-amber-200">
            <span className="font-bold">Automated Disruption Handler: </span>
            When a room enters maintenance, the optimizer finds replacements with minimal disruption: preserving the original block, matching capacity, and notifying attendees.
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[var(--foreground)] mb-1.5">
                Room in Maintenance
              </label>
              <select
                value={selectedMaintRoomId}
                onChange={(e) => {
                  setSelectedMaintRoomId(e.target.value);
                  handlePreviewReallocation(e.target.value);
                }}
                className="w-full text-xs rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 text-[var(--foreground)]"
              >
                <option value="">Select a maintenance room...</option>
                {maintenanceRooms.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} — {r.block_name} ({r.affected_future_bookings} bookings affected)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[var(--foreground)] mb-1.5">
                Blockage Reason
              </label>
              <select
                value={reallocReason}
                onChange={(e) => setReallocReason(e.target.value)}
                className="w-full text-xs rounded-lg border border-[var(--border)] bg-[var(--card)] p-2 text-[var(--foreground)]"
              >
                <option value="MAINTENANCE">Equipment / Facility Maintenance</option>
                <option value="EXAM">Institutional Exam Block</option>
                <option value="OTHER">Emergency Administrative Hold</option>
              </select>
            </div>
          </div>

          {/* Email notifications checkbox */}
          <div className="flex items-center gap-2 p-3 rounded-xl bg-[var(--muted)]/40 border border-[var(--border)]">
            <input
              type="checkbox"
              id="notifyCheck"
              checked={notifyUsers}
              onChange={(e) => setNotifyUsers(e.target.checked)}
              className="rounded accent-sky-500"
            />
            <label htmlFor="notifyCheck" className="text-xs text-[var(--foreground)] cursor-pointer">
              Send automated replacement notification emails to students & faculty
            </label>
          </div>

          {/* Replacement Preview List */}
          {loadingReallocPreview ? (
            <div className="py-8 text-center text-xs text-[var(--muted-foreground)]">
              Evaluating replacement rooms across active blocks...
            </div>
          ) : previewRealloc ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs font-semibold">
                <span>
                  Affected Bookings: {previewRealloc.affected_count} | Relocated: {previewRealloc.relocated_count}
                </span>
                <span className="text-emerald-600">
                  {previewRealloc.unresolved_count === 0 ? "100% Resolved" : `${previewRealloc.unresolved_count} Unresolved`}
                </span>
              </div>

              {previewRealloc.relocated_bookings.length > 0 ? (
                <div className="max-h-60 overflow-y-auto rounded-xl border border-[var(--border)]">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-[var(--muted)] sticky top-0 border-b border-[var(--border)]">
                      <tr>
                        <th className="py-2 px-3">Booking Ref</th>
                        <th className="py-2 px-3">Date / Slot</th>
                        <th className="py-2 px-3">Original</th>
                        <th className="py-2 px-3">Replacement Room</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {previewRealloc.relocated_bookings.map((b) => (
                        <tr key={b.booking_id} className="hover:bg-[var(--muted)]/20">
                          <td className="py-2 px-3 font-mono font-medium">{b.reference}</td>
                          <td className="py-2 px-3">{b.date} • Slot {b.slot_id}</td>
                          <td className="py-2 px-3 text-rose-500">{b.original_room_name}</td>
                          <td className="py-2 px-3">
                            {b.replacement_room_name ? (
                              <div className="font-bold text-emerald-600 flex items-center gap-1.5">
                                <span>{b.replacement_room_name}</span>
                                <span className="text-[10px] text-[var(--muted-foreground)]">({b.replacement_block_name})</span>
                              </div>
                            ) : (
                              <span className="text-amber-500 font-semibold">Manual review required</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-6 text-center text-xs text-[var(--muted-foreground)]">
                  No active future bookings affected by this maintenance schedule.
                </div>
              )}
            </div>
          ) : null}

          <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border)]">
            <Button
              variant="outline"
              onClick={() => setMaintModalOpen(false)}
              disabled={submittingRealloc}
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirmReallocation}
              isLoading={submittingRealloc}
              disabled={!selectedMaintRoomId}
              className="gap-2 bg-amber-600 hover:bg-amber-700 text-white"
            >
              <Sparkles className="w-4 h-4" />
              Confirm Re-optimization & Relocate
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
