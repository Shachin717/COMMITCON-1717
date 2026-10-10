"use client";

import * as React from "react";
import {
  FileText,
  Search,
  RotateCw,
  Code,
  Calendar,
  User,
  ShieldAlert,
  ShieldCheck,
  Eye,
  Filter,
} from "lucide-react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Modal } from "@/components/ui/modal";
import { EmptyState } from "@/components/ui/empty-state";
import { showToast } from "@/components/ui/toast";
import { apiClient } from "@/lib/api-client";
import { AuditLog, PaginatedResponse } from "@/lib/admin-types";

export default function AdminAuditLogsPage() {
  const [logs, setLogs] = React.useState<AuditLog[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [pageSize] = React.useState(20);

  // Filters
  const [search, setSearch] = React.useState("");
  const [actionFilter, setActionFilter] = React.useState("");
  const [entityFilter, setEntityFilter] = React.useState("");

  // Inspect Modal
  const [inspectModalOpen, setInspectModalOpen] = React.useState(false);
  const [activeLog, setActiveLog] = React.useState<AuditLog | null>(null);

  // Fetch logs
  const fetchLogs = React.useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        page_size: pageSize,
      };
      if (search.trim()) params.search = search.trim();
      if (actionFilter) params.action = actionFilter;
      if (entityFilter) params.entity = entityFilter;

      const res = await apiClient<PaginatedResponse<AuditLog>>("/api/admin/audit-logs", {
        params,
      });
      setLogs(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      showToast({
        title: "Error loading logs",
        message: err.message || "Failed to load audit logs",
        type: "error",
      });
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, actionFilter, entityFilter]);

  React.useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  // Action badge style
  const getActionBadgeColor = (action: string) => {
    const act = action.toUpperCase();
    if (act.includes("CREATE") || act.includes("REGISTER")) {
      return "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20";
    }
    if (act.includes("DELETE") || act.includes("CANCEL") || act.includes("FAIL")) {
      return "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20";
    }
    if (act.includes("UPDATE") || act.includes("TOGGLE") || act.includes("EDIT")) {
      return "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20";
    }
    if (act.includes("LOGIN") || act.includes("AUTH")) {
      return "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20";
    }
    return "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700";
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
              Security & Audit Trail Logs
            </h1>
            <p className="text-sm text-[var(--muted-foreground)]">
              Immutable ledger of administrative actions, authentication attempts, room catalog mutations, and booking decisions.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchLogs}
              isLoading={loading}
              className="gap-2"
            >
              <RotateCw className="w-4 h-4" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Filters */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <Input
              placeholder="Search action, entity, actor or metadata..."
              icon={<Search className="w-4 h-4" />}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
            <Select
              options={[
                { value: "", label: "All Actions" },
                { value: "LOGIN_STAFF", label: "Staff Login" },
                { value: "LOGIN_FAILED", label: "Failed Login" },
                { value: "LOGOUT", label: "Logout" },
                { value: "USER_CREATED", label: "User Created" },
                { value: "USER_UPDATED", label: "User Updated" },
                { value: "ROOM_CREATED", label: "Room Created" },
                { value: "ROOM_UPDATED", label: "Room Updated" },
                { value: "ROOM_STATUS_CHANGED", label: "Room Status Changed" },
                { value: "DEPARTMENT_CREATED", label: "Department Created" },
                { value: "DEPARTMENT_TOGGLE_HOD_APPROVAL", label: "HOD Approval Toggled" },
                { value: "BOOKING_APPROVED", label: "Booking Approved" },
                { value: "BOOKING_CANCELLED", label: "Booking Cancelled" },
                { value: "ROOMS_CSV_IMPORTED", label: "Rooms CSV Imported" },
                { value: "TIMETABLE_CSV_IMPORTED", label: "Timetable CSV Imported" },
              ]}
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setPage(1);
              }}
            />
            <Select
              options={[
                { value: "", label: "All Entity Types" },
                { value: "User", label: "User" },
                { value: "Room", label: "Room" },
                { value: "Department", label: "Department" },
                { value: "Block", label: "Block" },
                { value: "Booking", label: "Booking" },
                { value: "TimetableEntry", label: "Timetable Entry" },
                { value: "Facility", label: "Facility" },
              ]}
              value={entityFilter}
              onChange={(e) => {
                setEntityFilter(e.target.value);
                setPage(1);
              }}
            />
          </div>
        </div>

        {/* Audit Logs Table */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-[var(--foreground)]">
              <thead className="border-b border-[var(--border)] bg-slate-50/75 dark:bg-slate-900/40 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Timestamp</th>
                  <th className="px-5 py-3.5">Action Event</th>
                  <th className="px-5 py-3.5">Entity Target</th>
                  <th className="px-5 py-3.5">Actor User</th>
                  <th className="px-5 py-3.5">Metadata Snapshot</th>
                  <th className="px-5 py-3.5 text-right">Inspect</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {loading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={6} className="px-5 py-4">
                        <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                ) : logs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8">
                      <EmptyState
                        title="No audit logs recorded"
                        description="Audit events are registered automatically whenever administrative operations occur."
                      />
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => {
                    return (
                      <tr key={log.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30 transition-colors">
                        <td className="px-5 py-3.5 text-xs font-mono text-[var(--muted-foreground)] whitespace-nowrap">
                          {new Date(log.created_at).toLocaleString([], {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })}
                        </td>
                        <td className="px-5 py-3.5">
                          <span
                            className={`inline-block px-2.5 py-1 rounded-md text-xs font-semibold font-mono border ${getActionBadgeColor(
                              log.action
                            )}`}
                          >
                            {log.action}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-xs font-semibold">
                          <span>{log.entity}</span>
                          {log.entity_id && (
                            <span className="text-[var(--muted-foreground)] ml-1 font-mono font-normal">
                              #{log.entity_id}
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-xs">
                          {log.actor_id ? (
                            <span className="font-medium text-sky-600 dark:text-sky-400">
                              User #{log.actor_id}
                            </span>
                          ) : (
                            <span className="text-[var(--muted-foreground)] italic">System / Anonymous</span>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-xs text-[var(--muted-foreground)] max-w-xs truncate font-mono">
                          {JSON.stringify(log.meta)}
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                            onClick={() => {
                              setActiveLog(log);
                              setInspectModalOpen(true);
                            }}
                          >
                            <Eye className="w-3.5 h-3.5" />
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
              <span>Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {total} records</span>
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

        {/* JSON Inspector Modal */}
        {activeLog && (
          <Modal
            isOpen={inspectModalOpen}
            onClose={() => setInspectModalOpen(false)}
            title={`Audit Event #${activeLog.id}: ${activeLog.action}`}
            description="Complete payload recorded at time of execution."
            maxWidth="lg"
          >
            <div className="space-y-4 pt-2 text-xs">
              <div className="grid grid-cols-2 gap-3 p-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-[var(--border)]">
                <div>
                  <span className="text-[var(--muted-foreground)] block">Target Entity:</span>
                  <span className="font-bold text-[var(--foreground)]">{activeLog.entity} {activeLog.entity_id ? `(#${activeLog.entity_id})` : ""}</span>
                </div>
                <div>
                  <span className="text-[var(--muted-foreground)] block">Actor User:</span>
                  <span className="font-bold text-[var(--foreground)]">{activeLog.actor_id ? `User #${activeLog.actor_id}` : "System Automated"}</span>
                </div>
                <div>
                  <span className="text-[var(--muted-foreground)] block">Timestamp:</span>
                  <span className="font-mono text-[var(--foreground)]">{new Date(activeLog.created_at).toISOString()}</span>
                </div>
                <div>
                  <span className="text-[var(--muted-foreground)] block">Action:</span>
                  <span className="font-mono font-bold text-sky-600 dark:text-sky-400">{activeLog.action}</span>
                </div>
              </div>

              <div>
                <span className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Metadata JSON Payload:
                </span>
                <pre className="p-4 rounded-xl bg-slate-950 text-slate-100 font-mono text-[11px] overflow-x-auto max-h-72 border border-slate-800">
                  {JSON.stringify(activeLog.meta, null, 2)}
                </pre>
              </div>

              <div className="flex justify-end pt-2 border-t border-[var(--border)]">
                <Button variant="outline" onClick={() => setInspectModalOpen(false)}>
                  Close
                </Button>
              </div>
            </div>
          </Modal>
        )}
      </div>
    </DashboardShell>
  );
}
