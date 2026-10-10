"use client";

import * as React from "react";
import { Suspense, useState, useEffect, useCallback, useMemo } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import {
  Shield,
  Clock,
  CheckCircle2,
  XCircle,
  FlaskConical,
  CalendarDays,
  DoorOpen,
  Users,
  BarChart3,
  Download,
  Filter,
  Search,
  RotateCw,
  AlertTriangle,
  Layers,
  Activity,
  FileText,
  Sparkles,
  Eye,
  Info,
  Calendar,
  ChevronLeft,
  ChevronRight,
  GraduationCap,
  SlidersHorizontal,
  Check,
  X,
  Send,
  Building2,
} from "lucide-react";
import dynamic from "next/dynamic";

const HodOverviewCharts = dynamic(
  () => import("@/components/hod/hod-overview-charts"),
  {
    ssr: false,
    loading: () => (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-64 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 flex items-center justify-center">
          <Skeleton className="h-56 w-full rounded-xl" />
        </div>
        <div className="h-64 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 flex items-center justify-center">
          <Skeleton className="h-56 w-full rounded-xl" />
        </div>
      </div>
    ),
  }
);

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { StatCard } from "@/components/ui/stat-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Modal } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { showToast } from "@/components/ui/toast";
import { apiClient } from "@/lib/api-client";
import {
  Booking,
  BookingStatus,
  HodSummary,
  HodLab,
  HodRoomOption,
  HodPendingApprovalsResponse,
  PaginatedResponse,
  User,
} from "@/lib/admin-types";

function HodDashboardInner() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Tab State: overview | approvals | labs | history
  const activeTab = useMemo(() => {
    if (pathname === "/hod/approvals") return "approvals";
    if (pathname === "/hod/labs") return "labs";
    if (pathname === "/hod/history") return "history";
    const tabParam = searchParams.get("tab");
    if (tabParam && ["overview", "approvals", "labs", "history"].includes(tabParam)) {
      return tabParam;
    }
    return "overview";
  }, [pathname, searchParams]);

  const handleTabChange = (newTab: string) => {
    const route = newTab === "overview" ? "/hod" : `/hod/${newTab}`;
    router.push(route);
  };

  // User Authentication State
  const [user, setUser] = useState<User | null>(null);

  // Core Data States
  const [summary, setSummary] = useState<HodSummary | null>(null);
  const [pendingData, setPendingData] = useState<HodPendingApprovalsResponse | null>(null);
  const [labs, setLabs] = useState<HodLab[]>([]);
  const [rooms, setRooms] = useState<HodRoomOption[]>([]);

  // History State
  const [historyBookings, setHistoryBookings] = useState<Booking[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPages, setHistoryPages] = useState(1);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyPageSize] = useState(10);

  // History Filter States
  const [filterDateFrom, setFilterDateFrom] = useState("");
  const [filterDateTo, setFilterDateTo] = useState("");
  const [filterRoomId, setFilterRoomId] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterStudent, setFilterStudent] = useState("");

  // Loading & Action States
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);

  // Approval / Rejection Modal State
  const [decisionModalOpen, setDecisionModalOpen] = useState(false);
  const [decisionAction, setDecisionAction] = useState<"approve" | "reject">("approve");
  const [targetBooking, setTargetBooking] = useState<Booking | null>(null);
  const [decisionNote, setDecisionNote] = useState("");
  const [decisionSubmitting, setDecisionSubmitting] = useState(false);

  // Booking Detail Modal State
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [detailBooking, setDetailBooking] = useState<Booking | null>(null);

  // Fetch Current User
  useEffect(() => {
    async function loadUser() {
      try {
        const u = await apiClient<User>("/api/auth/me");
        setUser(u);
      } catch (err: any) {
        if (err.status === 401) {
          router.push("/hod/login?redirect=/hod");
        }
      }
    }
    loadUser();
  }, [router]);

  // Load Main Dashboard Data (Summary, Pending, Labs, Rooms)
  const loadDashboardData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoadingInitial(true);

    try {
      const [sumRes, pendRes, labsRes, roomsRes] = await Promise.all([
        apiClient<HodSummary>("/api/hod/summary").catch(() => null),
        apiClient<HodPendingApprovalsResponse>("/api/hod/approvals/pending").catch(() => null),
        apiClient<HodLab[]>("/api/hod/labs").catch(() => []),
        apiClient<HodRoomOption[]>("/api/hod/rooms").catch(() => []),
      ]);

      if (sumRes) setSummary(sumRes);
      if (pendRes) setPendingData(pendRes);
      if (labsRes) setLabs(labsRes);
      if (roomsRes) setRooms(roomsRes);
    } catch (err: any) {
      showToast({
        title: "Load Warning",
        message: err.message || "Failed to load departmental data.",
        type: "error",
      });
    } finally {
      setLoadingInitial(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Load History Bookings with Filters
  const loadHistory = useCallback(
    async (pageToLoad = 1) => {
      setLoadingHistory(true);
      try {
        const params = new URLSearchParams();
        params.set("page", String(pageToLoad));
        params.set("page_size", String(historyPageSize));
        if (filterStatus) params.set("status", filterStatus);
        if (filterDateFrom) params.set("date_from", filterDateFrom);
        if (filterDateTo) params.set("date_to", filterDateTo);
        if (filterRoomId) params.set("room_id", filterRoomId);
        if (filterStudent.trim()) params.set("student", filterStudent.trim());

        const res = await apiClient<PaginatedResponse<Booking>>(
          `/api/hod/bookings/history?${params.toString()}`
        );

        setHistoryBookings(res.items);
        setHistoryTotal(res.total);
        setHistoryPages(res.pages);
        setHistoryPage(res.page);
      } catch (err: any) {
        showToast({
          title: "History Error",
          message: err.message || "Could not retrieve booking history.",
          type: "error",
        });
      } finally {
        setLoadingHistory(false);
      }
    },
    [historyPageSize, filterStatus, filterDateFrom, filterDateTo, filterRoomId, filterStudent]
  );

  useEffect(() => {
    loadHistory(1);
  }, [loadHistory]);

  // Handle Decision Modal Open
  const handleOpenDecision = (booking: Booking, action: "approve" | "reject") => {
    setTargetBooking(booking);
    setDecisionAction(action);
    setDecisionNote("");
    setDecisionModalOpen(true);
  };

  // Submit Decision (Approve or Reject)
  const handleSubmitDecision = async () => {
    if (!targetBooking) return;

    if (decisionAction === "reject" && !decisionNote.trim()) {
      showToast({
        title: "Reason Required",
        message: "Please provide a reason when rejecting a booking.",
        type: "error",
      });
      return;
    }

    setDecisionSubmitting(true);
    try {
      await apiClient(`/api/hod/bookings/${targetBooking.id}/decision`, {
        method: "POST",
        body: JSON.stringify({
          action: decisionAction,
          note: decisionNote.trim() || undefined,
        }),
      });

      showToast({
        title: decisionAction === "approve" ? "Booking Approved" : "Booking Rejected",
        message: `Booking #${targetBooking.reference} has been ${decisionAction === "approve" ? "confirmed" : "rejected"}.`,
        type: decisionAction === "approve" ? "success" : "info",
      });

      setDecisionModalOpen(false);
      setTargetBooking(null);
      setDecisionNote("");

      // Refresh all views
      loadDashboardData(true);
      loadHistory(historyPage);
    } catch (err: any) {
      showToast({
        title: "Action Failed",
        message: err.message || "Failed to submit decision.",
        type: "error",
      });
    } finally {
      setDecisionSubmitting(false);
    }
  };

  // CSV Export Handler
  const handleExportCsv = async () => {
    setExportingCsv(true);
    try {
      const params = new URLSearchParams();
      if (filterStatus) params.set("status", filterStatus);
      if (filterDateFrom) params.set("date_from", filterDateFrom);
      if (filterDateTo) params.set("date_to", filterDateTo);
      if (filterRoomId) params.set("room_id", filterRoomId);
      if (filterStudent.trim()) params.set("student", filterStudent.trim());

      const url = `/api/hod/bookings/export?${params.toString()}`;
      const response = await fetch(url, {
        headers: {
          Accept: "text/csv",
        },
      });

      if (!response.ok) {
        throw new Error("Failed to generate CSV export file.");
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `dept_${summary?.department_code || "HOD"}_bookings_${new Date().toISOString().split("T")[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);

      showToast({
        title: "Export Successful",
        message: "Department bookings history has been downloaded.",
        type: "success",
      });
    } catch (err: any) {
      showToast({
        title: "Export Failed",
        message: err.message || "Unable to download CSV report.",
        type: "error",
      });
    } finally {
      setExportingCsv(false);
    }
  };

  // Reset Filters
  const handleResetFilters = () => {
    setFilterDateFrom("");
    setFilterDateTo("");
    setFilterRoomId("");
    setFilterStatus("");
    setFilterStudent("");
  };

  // Compute Pending Approvals Count
  const pendingApprovalsList = pendingData?.pending_bookings || [];
  const pendingCount = pendingApprovalsList.length;

  return (
    <DashboardShell
      role="HOD"
      userName={user?.name || "Department Head"}
      userEmail={user?.email || "hod@college.edu"}
      notificationCount={pendingCount}
      notificationLabel="Pending HOD Approvals"
    >
      <div className="space-y-6 pb-12">
        {/* TOP BRAND HEADER - Styled with HOD Violet/Purple/Indigo Palette */}
        <div className="relative overflow-hidden rounded-3xl border border-purple-500/20 bg-gradient-to-r from-purple-950/70 via-slate-900/90 to-indigo-950/70 p-6 sm:p-8 shadow-xl backdrop-blur-xl">
          <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-purple-500/10 blur-3xl pointer-events-none" />
          <div className="absolute -left-16 -bottom-16 h-64 w-64 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />

          <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/30 shadow-sm shadow-purple-500/10">
                  <GraduationCap className="w-3.5 h-3.5" />
                  Head of Department Console {summary ? `• ${summary.department_name} (${summary.department_code})` : ""}
                </span>
                {summary && (
                  <span
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border ${
                      summary.hod_approval_required
                        ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                        : "bg-slate-500/20 text-slate-300 border-slate-500/30"
                    }`}
                  >
                    <Shield className="w-3.5 h-3.5" />
                    {summary.hod_approval_required ? "HOD Approval Active" : "HOD Approval Optional"}
                  </span>
                )}
              </div>

              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
                Departmental Allocation & Governance
              </h1>
              <p className="text-sm text-purple-200/75 max-w-2xl leading-relaxed">
                Oversee specialized research laboratories, examine room utilization trends, and authorize student and faculty allocation requests.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  loadDashboardData(true);
                  loadHistory(historyPage);
                }}
                isLoading={refreshing}
                className="gap-2 bg-slate-900/60 border-purple-500/30 text-purple-200 hover:bg-purple-900/40 hover:text-white"
              >
                <RotateCw className="w-4 h-4" />
                Refresh
              </Button>
            </div>
          </div>
        </div>

        {/* NAVIGATION TAB CONTROLS */}
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-2 overflow-x-auto scrollbar-none">
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleTabChange("overview")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                activeTab === "overview"
                  ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-md shadow-purple-600/25"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)]"
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              Overview & Utilization
            </button>

            <button
              onClick={() => handleTabChange("approvals")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                activeTab === "approvals"
                  ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-md shadow-purple-600/25"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)]"
              }`}
            >
              <Shield className="w-4 h-4" />
              Pending Approvals
              {pendingCount > 0 && (
                <span className="ml-1 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-amber-500 text-white animate-pulse">
                  {pendingCount}
                </span>
              )}
            </button>

            <button
              onClick={() => handleTabChange("labs")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                activeTab === "labs"
                  ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-md shadow-purple-600/25"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)]"
              }`}
            >
              <FlaskConical className="w-4 h-4" />
              Department Labs ({labs.length})
            </button>

            <button
              onClick={() => handleTabChange("history")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all ${
                activeTab === "history"
                  ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-md shadow-purple-600/25"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)]"
              }`}
            >
              <FileText className="w-4 h-4" />
              Bookings History
            </button>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* TAB 1: OVERVIEW & UTILIZATION CHARTS */}
        {/* ========================================================================= */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* KPI STAT CARDS */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              <StatCard
                title="Department Labs"
                value={summary?.total_labs ?? labs.length}
                description="Specialized research venues"
                icon={<FlaskConical className="w-5 h-5 text-purple-500" />}
                className="hover:border-purple-500/40"
              />
              <StatCard
                title="Total Department Rooms"
                value={summary?.total_rooms ?? (rooms.length || 0)}
                description="Labs & classrooms owned"
                icon={<DoorOpen className="w-5 h-5 text-indigo-500" />}
                className="hover:border-indigo-500/40"
              />
              <StatCard
                title="Bookings Today"
                value={summary?.bookings_today ?? 0}
                description="Scheduled department sessions"
                icon={<CalendarDays className="w-5 h-5 text-sky-500" />}
                className="hover:border-sky-500/40"
              />
              <StatCard
                title="Today's Occupancy"
                value={`${summary?.utilization_rate ?? 0}%`}
                description="Capacity slot utilization"
                icon={<Activity className="w-5 h-5 text-emerald-500" />}
                className="hover:border-emerald-500/40"
              />
              <StatCard
                title="Pending Approvals"
                value={pendingCount}
                description={
                  summary?.hod_approval_required
                    ? "Requires your sign-off"
                    : "Policy requirement disabled"
                }
                icon={<Clock className="w-5 h-5 text-amber-500" />}
                className={
                  pendingCount > 0
                    ? "border-amber-500/50 bg-amber-500/5 dark:bg-amber-950/20"
                    : "hover:border-amber-500/40"
                }
              />
            </div>

            {/* PENDING APPROVALS CALLOUT BANNER (IF ANY REQUIRE HOD DECISION) */}
            {summary?.hod_approval_required && pendingCount > 0 && (
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-2xl border border-amber-500/40 bg-gradient-to-r from-amber-500/10 via-amber-500/5 to-transparent shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-amber-500/20 text-amber-600 dark:text-amber-400">
                    <AlertTriangle className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-[var(--foreground)]">
                      {pendingCount} Pending LAB / EXAM_HALL Request{pendingCount > 1 ? "s" : ""}
                    </h3>
                    <p className="text-xs text-[var(--muted-foreground)]">
                      These allocations have been cleared by Block Coordinators and await your departmental approval.
                    </p>
                  </div>
                </div>
                <Button
                  size="sm"
                  onClick={() => handleTabChange("approvals")}
                  className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white hover:from-purple-500 hover:to-indigo-500 shadow-md shadow-purple-600/20 whitespace-nowrap"
                >
                  Review Approvals ({pendingCount})
                </Button>
              </div>
            )}

            {/* CHARTS SECTION (Lazy-Loaded) */}
            <HodOverviewCharts summary={summary} />

            {/* PREVIEW OF LABS WITH UPCOMING USAGE */}
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-base font-bold text-[var(--foreground)]">
                    Department Laboratories & Upcoming Usage
                  </h2>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Active laboratories owned by {summary?.department_name || "your department"} with scheduled sessions.
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleTabChange("labs")}
                  className="gap-2 border-purple-500/30 text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/30"
                >
                  <FlaskConical className="w-4 h-4" />
                  View All Labs ({labs.length})
                </Button>
              </div>

              {labs.length === 0 ? (
                <EmptyState
                  icon={<FlaskConical className="w-6 h-6 text-purple-500" />}
                  title="No Laboratories Registered"
                  description="No research or computing laboratories are registered under your department."
                />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {labs.slice(0, 6).map((lab) => (
                    <div
                      key={lab.id}
                      className="rounded-2xl border border-[var(--border)] bg-[var(--background)] p-5 shadow-sm hover:border-purple-500/40 transition-all flex flex-col justify-between"
                    >
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-sm text-[var(--foreground)] flex items-center gap-1.5">
                            <FlaskConical className="w-4 h-4 text-purple-500" />
                            {lab.name}
                          </span>
                          <StatusBadge
                            status={lab.status === "ACTIVE" ? "success" : "error"}
                            label={lab.status}
                            size="sm"
                          />
                        </div>

                        <div className="text-xs text-[var(--muted-foreground)] space-y-1">
                          <p>
                            Location: {lab.block_name} (Floor {lab.floor})
                          </p>
                          <p>Capacity: {lab.capacity} student workstations</p>
                          <p>Today Occupancy: {lab.today_bookings_count} slots ({lab.utilization_rate}%)</p>
                        </div>

                        {lab.facilities.length > 0 && (
                          <div className="flex flex-wrap gap-1 pt-1">
                            {lab.facilities.slice(0, 3).map((f, i) => (
                              <span
                                key={i}
                                className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20"
                              >
                                {f}
                              </span>
                            ))}
                            {lab.facilities.length > 3 && (
                              <span className="px-1.5 py-0.5 rounded-md text-[10px] text-[var(--muted-foreground)]">
                                +{lab.facilities.length - 3}
                              </span>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="mt-4 pt-3 border-t border-[var(--border)]">
                        <div className="flex items-center justify-between text-xs mb-2">
                          <span className="font-semibold text-[var(--foreground)]">
                            Upcoming Usage:
                          </span>
                          <span className="text-[11px] font-bold text-purple-600 dark:text-purple-400">
                            {lab.upcoming_bookings.length} scheduled
                          </span>
                        </div>

                        {lab.upcoming_bookings.length === 0 ? (
                          <p className="text-[11px] text-[var(--muted-foreground)] italic">
                            No upcoming sessions scheduled.
                          </p>
                        ) : (
                          <div className="space-y-1.5">
                            {lab.upcoming_bookings.slice(0, 2).map((ub) => (
                              <div
                                key={ub.id}
                                className="p-2 rounded-lg bg-[var(--card)] border border-[var(--border)] text-[11px] flex items-center justify-between"
                              >
                                <div className="truncate pr-2">
                                  <p className="font-semibold text-[var(--foreground)] truncate">
                                    {ub.purpose}
                                  </p>
                                  <p className="text-[10px] text-[var(--muted-foreground)]">
                                    {ub.date} • {ub.slot_label}
                                  </p>
                                </div>
                                <span className="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-600 dark:text-purple-400">
                                  {ub.requester_name.split(" ")[0]}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: PENDING APPROVALS SECTION (LAB & EXAM_HALL) */}
        {/* ========================================================================= */}
        {activeTab === "approvals" && (
          <div className="space-y-6">
            {/* CONDITIONAL RENDERING BASED ON "HOD approval required" SETTING */}
            {!summary?.hod_approval_required ? (
              /* FRIENDLY INFO CARD WHEN HOD APPROVAL IS DISABLED */
              <div className="rounded-3xl border border-sky-500/20 bg-gradient-to-br from-sky-500/10 via-[var(--card)] to-indigo-500/10 p-8 shadow-sm">
                <div className="max-w-2xl space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="p-3 rounded-2xl bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20 shadow-sm">
                      <Shield className="w-6 h-6" />
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-[var(--foreground)]">
                        HOD Approval Requirement Inactive
                      </h2>
                      <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                        Admin Policy: Disabled for {summary?.department_name || "Department"}
                      </span>
                    </div>
                  </div>

                  <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
                    The institutional administrator has not enabled mandatory Head of Department sign-off for your department.
                    Laboratories and examination halls requested by students and faculty are finalized automatically once verified and endorsed by the respective Block Coordinators.
                  </p>

                  <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--background)]/80 text-xs text-[var(--muted-foreground)] space-y-2">
                    <div className="flex items-center gap-2 font-semibold text-[var(--foreground)]">
                      <Info className="w-4 h-4 text-sky-500" />
                      Policy Information
                    </div>
                    <p>
                      If your department requires prerequisite HOD approval for computer labs, specialized hardware facilities, or departmental assessment halls, please contact the campus System Administrator to toggle <strong>&quot;HOD approval required&quot;</strong> under <em>Admin &gt; Departments</em>.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              /* ACTIVE PENDING APPROVALS LIST */
              <div className="space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-bold text-[var(--foreground)]">
                      Pending Approvals ({pendingCount})
                    </h2>
                    <p className="text-xs text-[var(--muted-foreground)]">
                      Specialized LAB and EXAM_HALL allocations cleared by Block Coordinators that require your departmental decision.
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-[var(--muted-foreground)]">
                      Policy Status:
                    </span>
                    <StatusBadge status="ACTIVE" label="HOD Approval Enforced" size="sm" />
                  </div>
                </div>

                {pendingApprovalsList.length === 0 ? (
                  <EmptyState
                    icon={<CheckCircle2 className="w-6 h-6 text-emerald-500" />}
                    title="All Caught Up!"
                    description="No laboratory or examination hall bookings are currently waiting for your departmental review."
                  />
                ) : (
                  <div className="grid grid-cols-1 gap-4">
                    {pendingApprovalsList.map((booking) => (
                      <div
                        key={booking.id}
                        className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 sm:p-6 shadow-sm hover:border-purple-500/40 transition-all flex flex-col lg:flex-row lg:items-center justify-between gap-6"
                      >
                        {/* Booking Summary */}
                        <div className="space-y-3 flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-2.5">
                            <span className="font-mono text-xs font-bold px-2.5 py-1 rounded-lg bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
                              #{booking.reference}
                            </span>
                            <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                              {booking.room?.room_type || "LAB"}
                            </span>
                            <StatusBadge
                              status="coordinator_approved"
                              label="Coordinator Approved"
                              size="sm"
                            />
                            <span className="text-xs text-[var(--muted-foreground)]">
                              Requested {new Date(booking.created_at).toLocaleDateString()}
                            </span>
                          </div>

                          <div>
                            <h3 className="text-base font-bold text-[var(--foreground)] flex items-center gap-2">
                              {booking.purpose}
                            </h3>
                            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                              Room: <strong>{booking.room?.name || "Room"}</strong> ({booking.room?.block?.name || "Block"}, Floor {booking.room?.floor}) • Capacity: {booking.room?.capacity}
                            </p>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-[var(--muted-foreground)] pt-1">
                            <div className="flex items-center gap-1.5">
                              <Calendar className="w-3.5 h-3.5 text-purple-500" />
                              <span>Date: <strong>{booking.date}</strong></span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <Clock className="w-3.5 h-3.5 text-indigo-500" />
                              <span>Slot: <strong>{booking.slot?.label || "Scheduled"}</strong></span>
                            </div>
                            <div className="flex items-center gap-1.5">
                              <Users className="w-3.5 h-3.5 text-sky-500" />
                              <span>Attendees: <strong>{booking.expected_strength}</strong></span>
                            </div>
                          </div>

                          {/* Requester Identity */}
                          <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--muted-foreground)] pt-1">
                            <span>Requester: <strong className="text-[var(--foreground)]">{booking.name}</strong></span>
                            {booking.roll_no && (
                              <span className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 font-mono text-[11px]">
                                {booking.roll_no}
                              </span>
                            )}
                            <span>({booking.email})</span>
                          </div>

                          {/* Facilities required */}
                          {booking.required_facilities && booking.required_facilities.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1.5 pt-1">
                              <span className="text-[11px] text-[var(--muted-foreground)]">
                                Equipment:
                              </span>
                              {booking.required_facilities.map((fac, i) => (
                                <span
                                  key={i}
                                  className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-[var(--foreground)]"
                                >
                                  {fac}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Action Buttons */}
                        <div className="flex flex-row lg:flex-col items-center gap-2.5 shrink-0 pt-2 lg:pt-0 border-t lg:border-t-0 border-[var(--border)]">
                          <Button
                            size="sm"
                            onClick={() => handleOpenDecision(booking, "approve")}
                            className="w-full sm:w-auto bg-gradient-to-r from-emerald-600 to-teal-600 text-white hover:from-emerald-500 hover:to-teal-500 shadow-sm gap-1.5"
                          >
                            <Check className="w-4 h-4" />
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleOpenDecision(booking, "reject")}
                            className="w-full sm:w-auto border-rose-500/30 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 gap-1.5"
                          >
                            <X className="w-4 h-4" />
                            Reject
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setDetailBooking(booking);
                              setDetailModalOpen(true);
                            }}
                            className="w-full sm:w-auto text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] gap-1"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            Details
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: DEPARTMENT LABS WITH UPCOMING USAGE */}
        {/* ========================================================================= */}
        {activeTab === "labs" && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-[var(--foreground)]">
                  Department Laboratories ({labs.length})
                </h2>
                <p className="text-xs text-[var(--muted-foreground)]">
                  All computing, engineering, and specialized laboratories assigned to {summary?.department_name || "your department"}.
                </p>
              </div>

              <Button
                size="sm"
                variant="outline"
                onClick={() => loadDashboardData(true)}
                isLoading={refreshing}
                className="gap-2 border-purple-500/30 text-purple-600 dark:text-purple-400"
              >
                <RotateCw className="w-3.5 h-3.5" />
                Refresh Labs
              </Button>
            </div>

            {labs.length === 0 ? (
              <EmptyState
                icon={<FlaskConical className="w-6 h-6 text-purple-500" />}
                title="No Laboratories Found"
                description="There are currently no laboratory rooms assigned to your department."
              />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {labs.map((lab) => (
                  <div
                    key={lab.id}
                    className="rounded-3xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm hover:border-purple-500/40 transition-all flex flex-col justify-between"
                  >
                    <div className="space-y-4">
                      {/* Lab Header */}
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="p-2 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400">
                              <FlaskConical className="w-5 h-5" />
                            </span>
                            <div>
                              <h3 className="text-base font-bold text-[var(--foreground)]">
                                {lab.name}
                              </h3>
                              <p className="text-xs text-[var(--muted-foreground)]">
                                {lab.block_name} • Floor {lab.floor}
                              </p>
                            </div>
                          </div>
                        </div>

                        <StatusBadge
                          status={lab.status === "ACTIVE" ? "success" : "error"}
                          label={lab.status}
                          size="md"
                        />
                      </div>

                      {/* Lab Metrics */}
                      <div className="grid grid-cols-3 gap-3 p-3 rounded-2xl bg-[var(--background)] border border-[var(--border)] text-center">
                        <div>
                          <p className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase">
                            Capacity
                          </p>
                          <p className="text-base font-bold text-[var(--foreground)] mt-0.5">
                            {lab.capacity}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase">
                            Today Slots
                          </p>
                          <p className="text-base font-bold text-purple-600 dark:text-purple-400 mt-0.5">
                            {lab.today_bookings_count}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase">
                            All-Time
                          </p>
                          <p className="text-base font-bold text-[var(--foreground)] mt-0.5">
                            {lab.total_bookings}
                          </p>
                        </div>
                      </div>

                      {/* Equipment Tags */}
                      {lab.facilities.length > 0 && (
                        <div>
                          <p className="text-xs font-semibold text-[var(--foreground)] mb-1.5">
                            Installed Facilities:
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {lab.facilities.map((fac, i) => (
                              <span
                                key={i}
                                className="px-2.5 py-1 rounded-lg text-xs font-medium bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20"
                              >
                                {fac}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Maintenance Note if any */}
                      {lab.maintenance_note && (
                        <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-600 dark:text-rose-400 flex items-start gap-2">
                          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                          <span>Maintenance Note: {lab.maintenance_note}</span>
                        </div>
                      )}
                    </div>

                    {/* Upcoming Usage Schedule */}
                    <div className="mt-6 pt-4 border-t border-[var(--border)]">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-xs font-bold text-[var(--foreground)] uppercase tracking-wider flex items-center gap-1.5">
                          <Calendar className="w-3.5 h-3.5 text-purple-500" />
                          Upcoming Lab Usage
                        </h4>
                        <span className="text-xs text-[var(--muted-foreground)]">
                          {lab.upcoming_bookings.length} upcoming
                        </span>
                      </div>

                      {lab.upcoming_bookings.length === 0 ? (
                        <div className="p-4 rounded-xl bg-[var(--background)] border border-[var(--border)] text-center text-xs text-[var(--muted-foreground)]">
                          No upcoming sessions scheduled for this laboratory.
                        </div>
                      ) : (
                        <div className="space-y-2 max-h-56 overflow-y-auto pr-1 scrollbar-thin">
                          {lab.upcoming_bookings.map((ub) => (
                            <div
                              key={ub.id}
                              className="p-3 rounded-xl bg-[var(--background)] border border-[var(--border)] text-xs space-y-1 hover:border-purple-500/30 transition-all"
                            >
                              <div className="flex items-center justify-between font-semibold text-[var(--foreground)]">
                                <span className="truncate pr-2">{ub.purpose}</span>
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-600 dark:text-purple-400 font-mono shrink-0">
                                  #{ub.reference}
                                </span>
                              </div>
                              <div className="flex items-center justify-between text-[11px] text-[var(--muted-foreground)]">
                                <span>
                                  {ub.date} • {ub.slot_label} ({ub.start_time} - {ub.end_time})
                                </span>
                                <span>{ub.expected_strength} attendees</span>
                              </div>
                              <div className="text-[10px] text-[var(--muted-foreground)]">
                                Requested by: <strong className="text-[var(--foreground)]">{ub.requester_name}</strong> {ub.roll_no ? `(${ub.roll_no})` : ""}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: BOOKINGS HISTORY (CLASSES & LABS WITH FILTERS & CSV EXPORT) */}
        {/* ========================================================================= */}
        {activeTab === "history" && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-[var(--foreground)]">
                  Department Bookings History
                </h2>
                <p className="text-xs text-[var(--muted-foreground)]">
                  Historical log of all classrooms, laboratories, and exam halls booked by students and faculty of {summary?.department_name || "your department"}.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={handleExportCsv}
                  isLoading={exportingCsv}
                  className="gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white hover:from-purple-500 hover:to-indigo-500 shadow-md shadow-purple-600/20"
                >
                  <Download className="w-4 h-4" />
                  Export to CSV
                </Button>
              </div>
            </div>

            {/* FILTERS TOOLBAR */}
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 sm:p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
                <div className="flex items-center gap-2 text-xs font-bold text-[var(--foreground)] uppercase tracking-wider">
                  <Filter className="w-4 h-4 text-purple-500" />
                  Filter Records
                </div>
                {(filterDateFrom || filterDateTo || filterRoomId || filterStatus || filterStudent) && (
                  <button
                    onClick={handleResetFilters}
                    className="text-xs text-purple-600 dark:text-purple-400 hover:underline font-semibold"
                  >
                    Reset All Filters
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                {/* Date From */}
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--muted-foreground)] mb-1">
                    Date From
                  </label>
                  <Input
                    type="date"
                    value={filterDateFrom}
                    onChange={(e) => setFilterDateFrom(e.target.value)}
                    className="text-xs"
                  />
                </div>

                {/* Date To */}
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--muted-foreground)] mb-1">
                    Date To
                  </label>
                  <Input
                    type="date"
                    value={filterDateTo}
                    onChange={(e) => setFilterDateTo(e.target.value)}
                    className="text-xs"
                  />
                </div>

                {/* Room Filter */}
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--muted-foreground)] mb-1">
                    Room / Lab
                  </label>
                  <Select
                    options={[
                      { label: "All Department Venues", value: "" },
                      ...rooms.map((r) => ({
                        label: `${r.name} (${r.room_type})`,
                        value: String(r.id),
                      })),
                    ]}
                    value={filterRoomId}
                    onChange={(e) => setFilterRoomId(e.target.value)}
                    className="text-xs"
                  />
                </div>

                {/* Status Filter */}
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--muted-foreground)] mb-1">
                    Booking Status
                  </label>
                  <Select
                    options={[
                      { label: "All Statuses", value: "" },
                      { label: "Approved", value: "APPROVED" },
                      { label: "Coordinator Approved", value: "COORDINATOR_APPROVED" },
                      { label: "Pending Review", value: "PENDING" },
                      { label: "Rejected", value: "REJECTED" },
                      { label: "Cancelled", value: "CANCELLED" },
                    ]}
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="text-xs"
                  />
                </div>

                {/* Student / Roll No Search */}
                <div>
                  <label className="block text-[11px] font-semibold text-[var(--muted-foreground)] mb-1">
                    Student / Roll No
                  </label>
                  <div className="relative">
                    <Input
                      placeholder="Name or Roll No..."
                      value={filterStudent}
                      onChange={(e) => setFilterStudent(e.target.value)}
                      className="text-xs pl-8"
                    />
                    <Search className="w-3.5 h-3.5 text-[var(--muted-foreground)] absolute left-2.5 top-3" />
                  </div>
                </div>
              </div>
            </div>

            {/* HISTORY DATA TABLE */}
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[var(--background)] border-b border-[var(--border)] text-[var(--muted-foreground)] font-semibold uppercase text-[10px] tracking-wider">
                    <tr>
                      <th className="px-4 py-3.5">Reference</th>
                      <th className="px-4 py-3.5">Date & Slot</th>
                      <th className="px-4 py-3.5">Room & Type</th>
                      <th className="px-4 py-3.5">Requester (Student)</th>
                      <th className="px-4 py-3.5">Purpose & Strength</th>
                      <th className="px-4 py-3.5">Status</th>
                      <th className="px-4 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {loadingHistory ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-12 text-center">
                          <div className="flex items-center justify-center gap-2 text-sm text-[var(--muted-foreground)]">
                            <RotateCw className="w-4 h-4 animate-spin text-purple-500" />
                            <span>Loading department booking records...</span>
                          </div>
                        </td>
                      </tr>
                    ) : historyBookings.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-12 text-center">
                          <EmptyState
                            icon={<FileText className="w-6 h-6 text-purple-500" />}
                            title="No History Found"
                            description="No booking records match the selected date, room, status, or student filters."
                          />
                        </td>
                      </tr>
                    ) : (
                      historyBookings.map((b) => (
                        <tr
                          key={b.id}
                          className="hover:bg-[var(--accent)]/50 transition-colors cursor-pointer"
                          onClick={() => {
                            setDetailBooking(b);
                            setDetailModalOpen(true);
                          }}
                        >
                          {/* Reference */}
                          <td className="px-4 py-3 font-mono font-bold text-purple-600 dark:text-purple-400">
                            #{b.reference}
                          </td>

                          {/* Date & Slot */}
                          <td className="px-4 py-3">
                            <p className="font-semibold text-[var(--foreground)]">{b.date}</p>
                            <p className="text-[11px] text-[var(--muted-foreground)]">
                              {b.slot?.label || "Slot"}
                            </p>
                          </td>

                          {/* Room & Type */}
                          <td className="px-4 py-3">
                            <p className="font-semibold text-[var(--foreground)]">{b.room?.name || "Room"}</p>
                            <span className="inline-block mt-0.5 px-2 py-0.5 rounded text-[10px] font-semibold bg-purple-500/10 text-purple-600 dark:text-purple-400">
                              {b.room?.room_type || "ROOM"}
                            </span>
                          </td>

                          {/* Student */}
                          <td className="px-4 py-3">
                            <p className="font-semibold text-[var(--foreground)]">{b.name}</p>
                            <p className="text-[11px] text-[var(--muted-foreground)] font-mono">
                              {b.roll_no || b.email}
                            </p>
                          </td>

                          {/* Purpose & Strength */}
                          <td className="px-4 py-3 max-w-xs">
                            <p className="font-medium text-[var(--foreground)] truncate">
                              {b.purpose}
                            </p>
                            <p className="text-[11px] text-[var(--muted-foreground)]">
                              Expected: {b.expected_strength} attendees
                            </p>
                          </td>

                          {/* Status */}
                          <td className="px-4 py-3">
                            <StatusBadge status={b.status} label={b.status} size="sm" />
                          </td>

                          {/* Actions */}
                          <td className="px-4 py-3 text-right">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={(e) => {
                                e.stopPropagation();
                                setDetailBooking(b);
                                setDetailModalOpen(true);
                              }}
                              className="text-xs gap-1"
                            >
                              <Eye className="w-3.5 h-3.5" />
                              View
                            </Button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* PAGINATION CONTROLS */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4 px-4 py-3.5 border-t border-[var(--border)] bg-[var(--background)]">
                <span className="text-xs text-[var(--muted-foreground)]">
                  Showing <strong>{historyBookings.length}</strong> of <strong>{historyTotal}</strong> records (Page {historyPage} of {historyPages || 1})
                </span>

                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={historyPage <= 1 || loadingHistory}
                    onClick={() => loadHistory(historyPage - 1)}
                    className="gap-1 text-xs"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={historyPage >= historyPages || loadingHistory}
                    onClick={() => loadHistory(historyPage + 1)}
                    className="gap-1 text-xs"
                  >
                    Next
                    <ChevronRight className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* DECISION MODAL (APPROVE / REJECT WITH NOTES) */}
      {/* ========================================================================= */}
      <Modal
        isOpen={decisionModalOpen}
        onClose={() => setDecisionModalOpen(false)}
        title={decisionAction === "approve" ? "Authorize Booking Request" : "Reject Booking Request"}
        description={
          decisionAction === "approve"
            ? "Confirm departmental approval for this specialized laboratory or examination venue."
            : "Reject this request and notify the student with the reason."
        }
      >
        <div className="space-y-4 pt-2">
          {targetBooking && (
            <div className="p-3.5 rounded-xl bg-[var(--accent)]/50 border border-[var(--border)] text-xs space-y-1.5">
              <div className="flex items-center justify-between font-bold text-[var(--foreground)]">
                <span>#{targetBooking.reference} • {targetBooking.room?.name}</span>
                <span className="text-purple-600 dark:text-purple-400 font-mono">
                  {targetBooking.date}
                </span>
              </div>
              <p className="text-[var(--muted-foreground)]">
                Requester: <strong>{targetBooking.name}</strong> ({targetBooking.roll_no || targetBooking.email})
              </p>
              <p className="text-[var(--muted-foreground)]">
                Purpose: &quot;{targetBooking.purpose}&quot;
              </p>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-[var(--foreground)] mb-1.5">
              Department Decision Note {decisionAction === "reject" ? "(Required)" : "(Optional)"}
            </label>
            <textarea
              rows={3}
              placeholder={
                decisionAction === "approve"
                  ? "E.g., Approved. Lab assistant will provide hardware setup..."
                  : "E.g., Department internal exam scheduled during this slot..."
              }
              value={decisionNote}
              onChange={(e) => setDecisionNote(e.target.value)}
              className="w-full rounded-xl border border-[var(--border)] bg-[var(--background)] p-3 text-xs text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-[var(--border)]">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDecisionModalOpen(false)}
              disabled={decisionSubmitting}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              isLoading={decisionSubmitting}
              onClick={handleSubmitDecision}
              className={
                decisionAction === "approve"
                  ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white hover:from-emerald-500 hover:to-teal-500 shadow-md shadow-emerald-600/20"
                  : "bg-rose-600 text-white hover:bg-rose-700 shadow-md shadow-rose-600/20"
              }
            >
              {decisionAction === "approve" ? "Confirm Approval" : "Confirm Rejection"}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ========================================================================= */}
      {/* BOOKING DETAIL MODAL */}
      {/* ========================================================================= */}
      <Modal
        isOpen={detailModalOpen}
        onClose={() => setDetailModalOpen(false)}
        title="Booking Details"
        description="Comprehensive reservation and approval record."
      >
        {detailBooking && (
          <div className="space-y-4 pt-2 text-xs">
            <div className="flex items-center justify-between pb-3 border-b border-[var(--border)]">
              <div>
                <p className="font-mono text-sm font-bold text-purple-600 dark:text-purple-400">
                  #{detailBooking.reference}
                </p>
                <p className="text-[11px] text-[var(--muted-foreground)]">
                  Created {new Date(detailBooking.created_at).toLocaleString()}
                </p>
              </div>
              <StatusBadge status={detailBooking.status} label={detailBooking.status} size="md" />
            </div>

            <div className="grid grid-cols-2 gap-3 p-3 rounded-xl bg-[var(--accent)]/40 border border-[var(--border)]">
              <div>
                <p className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase">
                  Room
                </p>
                <p className="font-bold text-[var(--foreground)] mt-0.5">
                  {detailBooking.room?.name || "Room"} ({detailBooking.room?.room_type})
                </p>
                <p className="text-[10px] text-[var(--muted-foreground)]">
                  {detailBooking.room?.block?.name || "Block"}, Floor {detailBooking.room?.floor}
                </p>
              </div>

              <div>
                <p className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase">
                  Date & Slot
                </p>
                <p className="font-bold text-[var(--foreground)] mt-0.5">
                  {detailBooking.date}
                </p>
                <p className="text-[10px] text-[var(--muted-foreground)]">
                  {detailBooking.slot?.label || "Slot"}
                </p>
              </div>
            </div>

            <div>
              <p className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase mb-1">
                Requester Details
              </p>
              <div className="p-3 rounded-xl bg-[var(--background)] border border-[var(--border)] space-y-1">
                <p className="font-semibold text-[var(--foreground)]">{detailBooking.name}</p>
                {detailBooking.roll_no && <p className="font-mono">Roll No: {detailBooking.roll_no}</p>}
                <p>Email: {detailBooking.email}</p>
                {detailBooking.phone && <p>Phone: {detailBooking.phone}</p>}
                <p>Type: {detailBooking.requester_type}</p>
              </div>
            </div>

            <div>
              <p className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase mb-1">
                Purpose & Strength
              </p>
              <div className="p-3 rounded-xl bg-[var(--background)] border border-[var(--border)] space-y-1">
                <p className="font-medium text-[var(--foreground)]">{detailBooking.purpose}</p>
                <p className="text-[11px] text-[var(--muted-foreground)]">
                  Expected Attendees: {detailBooking.expected_strength}
                </p>
              </div>
            </div>

            {detailBooking.required_facilities && detailBooking.required_facilities.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase mb-1">
                  Required Facilities
                </p>
                <div className="flex flex-wrap gap-1">
                  {detailBooking.required_facilities.map((fac, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded text-[11px] bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20"
                    >
                      {fac}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {detailBooking.decision_note && (
              <div>
                <p className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase mb-1">
                  Decision Notes & Audit Record
                </p>
                <div className="p-3 rounded-xl bg-purple-500/5 border border-purple-500/20 text-purple-700 dark:text-purple-300 font-mono text-[11px]">
                  {detailBooking.decision_note}
                </div>
              </div>
            )}

            <div className="pt-2 flex justify-end">
              <Button size="sm" variant="outline" onClick={() => setDetailModalOpen(false)}>
                Close
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </DashboardShell>
  );
}

export default function HodDashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[var(--background)] flex items-center justify-center p-8">
          <div className="flex items-center gap-3 text-sm text-[var(--muted-foreground)]">
            <div className="h-5 w-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
            <span>Loading Department Head Portal...</span>
          </div>
        </div>
      }
    >
      <HodDashboardInner />
    </Suspense>
  );
}
