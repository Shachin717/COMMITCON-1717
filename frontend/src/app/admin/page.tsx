"use client";

import * as React from "react";
import Link from "next/link";
import {
  DoorOpen,
  CalendarDays,
  Clock,
  Activity,
  AlertTriangle,
  RotateCw,
  ArrowRight,
  Shield,
  Layers,
  Users,
  Boxes,
  FileText,
  History,
  TrendingUp,
  Sparkles,
} from "lucide-react";
import dynamic from "next/dynamic";

const AdminOverviewCharts = dynamic(
  () => import("@/components/admin/admin-overview-charts"),
  {
    ssr: false,
    loading: () => (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="h-72 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 flex items-center justify-center">
          <Skeleton className="h-60 w-full rounded-xl" />
        </div>
        <div className="h-72 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 flex items-center justify-center">
          <Skeleton className="h-60 w-full rounded-xl" />
        </div>
      </div>
    ),
  }
);

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { StatCard } from "@/components/ui/stat-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { apiClient } from "@/lib/api-client";
import { AdminOverview } from "@/lib/admin-types";

export default function AdminOverviewPage() {
  const [data, setData] = React.useState<AdminOverview | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const fetchOverview = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient<AdminOverview>("/api/admin/overview");
      setData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load admin overview metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  return (
    <DashboardShell
      role="ADMIN"
      userName="System Admin"
      userEmail="admin@git.edu"
    >
      <div className="space-y-8 pb-10">
        {/* Header Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[var(--foreground)]">
                Administrator Dashboard
              </h1>
              <StatusBadge status="ACTIVE" label="System Online" />
            </div>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Central operational control for rooms, department policies, user accounts, and real-time scheduling.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchOverview}
              isLoading={loading}
              className="gap-2"
            >
              <RotateCw className="w-4 h-4" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Error State */}
        {error && (
          <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-5 text-rose-600 dark:text-rose-400 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <p className="text-sm font-medium">{error}</p>
            </div>
            <Button size="sm" variant="outline" onClick={fetchOverview}>
              Try Again
            </Button>
          </div>
        )}

        {/* StatCards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 space-y-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-8 w-16" />
                <Skeleton className="h-3 w-32" />
              </div>
            ))
          ) : data ? (
            <>
              <StatCard
                title="Total Rooms"
                value={data.total_rooms}
                description="Active college catalog"
                icon={<DoorOpen className="w-5 h-5" />}
              />
              <StatCard
                title="In Maintenance"
                value={data.in_maintenance}
                description={data.in_maintenance > 0 ? "Unavailable for booking" : "All rooms available"}
                icon={<AlertTriangle className="w-5 h-5 text-amber-500" />}
              />
              <StatCard
                title="Bookings Today"
                value={data.bookings_today}
                description="Scheduled sessions"
                icon={<CalendarDays className="w-5 h-5 text-sky-500" />}
              />
              <StatCard
                title="Pending Requests"
                value={data.pending_bookings}
                description="Awaiting approval"
                icon={<Clock className="w-5 h-5 text-indigo-500" />}
              />
              <StatCard
                title="Utilization Rate"
                value={`${data.utilization_rate}%`}
                description="Capacity slot coverage"
                icon={<Activity className="w-5 h-5 text-emerald-500" />}
                trend={{
                  value: `${data.utilization_rate}%`,
                  isPositive: data.utilization_rate >= 50,
                  label: "Overall load",
                }}
              />
            </>
          ) : null}
        </div>

        {/* Charts Section with Lazy-Loaded Recharts */}
        <AdminOverviewCharts data={data} loading={loading} />

        {/* Quick Management Shortcuts */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
          <h2 className="text-base font-bold text-[var(--foreground)] mb-4">
            Quick Administration Modules
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {[
              { label: "Allocation Insights", href: "/admin/allocation", icon: Sparkles, desc: "Baseline vs Optimizer simulator & metrics" },
              { label: "Rooms & Catalog", href: "/admin/rooms", icon: DoorOpen, desc: "Add & edit rooms" },
              { label: "Slots & Timetable", href: "/admin/timetable", icon: Clock, desc: "Periods & schedules" },
              { label: "Staff & Users", href: "/admin/users", icon: Users, desc: "HOD, Coord, Faculty" },
              { label: "Departments", href: "/admin/departments", icon: Layers, desc: "HOD approval toggles" },
              { label: "Blocks", href: "/admin/blocks", icon: Boxes, desc: "Assign coordinators" },
              { label: "Booking History", href: "/admin/bookings", icon: History, desc: "Audit and filter bookings" },
              { label: "Audit Logs", href: "/admin/audit-logs", icon: FileText, desc: "System activity trail" },
            ].map((m) => {
              const Icon = m.icon;
              return (
                <Link
                  key={m.href}
                  href={m.href}
                  className="group flex flex-col justify-between p-4 rounded-xl border border-[var(--border)] hover:border-sky-500/50 hover:bg-sky-500/5 transition-all"
                >
                  <div>
                    <div className="h-9 w-9 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 flex items-center justify-center mb-2.5 group-hover:scale-105 transition-transform">
                      <Icon className="w-5 h-5" />
                    </div>
                    <span className="text-sm font-semibold text-[var(--foreground)] block">
                      {m.label}
                    </span>
                    <span className="text-xs text-[var(--muted-foreground)] mt-0.5 block">
                      {m.desc}
                    </span>
                  </div>
                  <div className="mt-3 flex items-center text-xs font-medium text-sky-600 dark:text-sky-400 group-hover:translate-x-1 transition-transform">
                    <span>Manage</span>
                    <ArrowRight className="w-3.5 h-3.5 ml-1" />
                  </div>
                </Link>
              );
            })}
          </div>
        </div>

        {/* Recent Activity Trail */}
        {data?.recent_activity && data.recent_activity.length > 0 && (
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-bold text-[var(--foreground)]">
                  Recent System Audit Trail
                </h2>
                <p className="text-xs text-[var(--muted-foreground)]">
                  Live administrative and security events logged in real-time
                </p>
              </div>
              <Link
                href="/admin/audit-logs"
                className="text-xs font-semibold text-sky-600 hover:text-sky-500 flex items-center gap-1"
              >
                View all logs <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <div className="divide-y divide-[var(--border)]">
              {data.recent_activity.slice(0, 5).map((log) => (
                <div key={log.id} className="py-3 flex items-center justify-between gap-4 text-xs">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="px-2 py-0.5 rounded-md font-mono text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                      {log.action}
                    </span>
                    <span className="text-[var(--foreground)] truncate font-medium">
                      {log.entity} {log.entity_id ? `(#${log.entity_id})` : ""}
                    </span>
                    {log.meta?.email && (
                      <span className="text-[var(--muted-foreground)] hidden sm:inline">
                        — {log.meta.email}
                      </span>
                    )}
                  </div>
                  <span className="text-[var(--muted-foreground)] shrink-0">
                    {new Date(log.created_at).toLocaleString([], {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </DashboardShell>
  );
}
