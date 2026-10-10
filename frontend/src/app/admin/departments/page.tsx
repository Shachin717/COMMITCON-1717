"use client";

import * as React from "react";
import {
  Layers,
  Plus,
  Search,
  RotateCw,
  Edit2,
  Trash2,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  HelpCircle,
} from "lucide-react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { showToast } from "@/components/ui/toast";
import { apiClient } from "@/lib/api-client";
import { Department, PaginatedResponse } from "@/lib/admin-types";

export default function AdminDepartmentsPage() {
  const [departments, setDepartments] = React.useState<Department[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [pageSize] = React.useState(15);
  const [search, setSearch] = React.useState("");

  // Modals
  const [createModalOpen, setCreateModalOpen] = React.useState(false);
  const [editModalOpen, setEditModalOpen] = React.useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = React.useState(false);
  const [activeDept, setActiveDept] = React.useState<Department | null>(null);

  // Form states
  const [formData, setFormData] = React.useState({
    name: "",
    code: "",
    hod_approval_required: true,
  });
  const [formErrors, setFormErrors] = React.useState<Record<string, string>>({});
  const [submitting, setSubmitting] = React.useState(false);

  // Fetch departments
  const fetchDepartments = React.useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        page_size: pageSize,
      };
      if (search.trim()) params.search = search.trim();

      const res = await apiClient<PaginatedResponse<Department>>("/api/admin/departments", {
        params,
      });
      setDepartments(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      showToast({
        title: "Error loading departments",
        message: err.message || "Failed to fetch departments",
        type: "error",
      });
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search]);

  React.useEffect(() => {
    fetchDepartments();
  }, [fetchDepartments]);

  // Validation
  const validateForm = () => {
    const errs: Record<string, string> = {};
    if (!formData.name.trim()) errs.name = "Department name is required";
    if (!formData.code.trim()) {
      errs.code = "Department code is required";
    } else if (formData.code.trim().length > 10) {
      errs.code = "Code should not exceed 10 characters";
    }
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  // Toggle HOD approval requirement
  const handleToggleHodApproval = async (dept: Department) => {
    // Optimistic UI update
    const previousState = dept.hod_approval_required;
    const nextState = !previousState;
    setDepartments((prev) =>
      prev.map((d) => (d.id === dept.id ? { ...d, hod_approval_required: nextState } : d))
    );

    try {
      const updated = await apiClient<Department>(
        `/api/admin/departments/${dept.id}/toggle-hod-approval`,
        { method: "POST" }
      );
      setDepartments((prev) =>
        prev.map((d) => (d.id === dept.id ? updated : d))
      );
      showToast({
        title: updated.hod_approval_required ? "HOD Approval Enabled" : "HOD Approval Disabled",
        message: `${dept.code}: ${
          updated.hod_approval_required
            ? "LAB and EXAM_HALL bookings now require HOD approval."
            : "LAB and EXAM_HALL bookings will be confirmed upon coordinator review."
        }`,
        type: "info",
      });
    } catch (err: any) {
      // Revert on error
      setDepartments((prev) =>
        prev.map((d) => (d.id === dept.id ? { ...d, hod_approval_required: previousState } : d))
      );
      showToast({
        title: "Toggle Failed",
        message: err.message || "Could not toggle HOD approval",
        type: "error",
      });
    }
  };

  // Create department
  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setSubmitting(true);
    try {
      await apiClient("/api/admin/departments", {
        method: "POST",
        body: JSON.stringify({
          name: formData.name.trim(),
          code: formData.code.trim().toUpperCase(),
        }),
      });
      setCreateModalOpen(false);
      showToast({
        title: "Department Created",
        message: `${formData.code} department has been added.`,
        type: "success",
      });
      fetchDepartments();
    } catch (err: any) {
      showToast({
        title: "Creation Failed",
        message: err.message || "Failed to create department",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Edit department
  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeDept || !validateForm()) return;

    setSubmitting(true);
    try {
      await apiClient(`/api/admin/departments/${activeDept.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: formData.name.trim(),
          code: formData.code.trim().toUpperCase(),
          hod_approval_required: formData.hod_approval_required,
        }),
      });
      setEditModalOpen(false);
      showToast({
        title: "Department Updated",
        message: "Department details saved.",
        type: "success",
      });
      fetchDepartments();
    } catch (err: any) {
      showToast({
        title: "Update Failed",
        message: err.message || "Failed to update department",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Delete department
  const handleDelete = async () => {
    if (!activeDept) return;
    try {
      await apiClient(`/api/admin/departments/${activeDept.id}`, {
        method: "DELETE",
      });
      setDeleteConfirmOpen(false);
      showToast({
        title: "Department Deleted",
        message: `${activeDept.code} has been removed.`,
        type: "info",
      });
      fetchDepartments();
    } catch (err: any) {
      showToast({
        title: "Delete Failed",
        message: err.message || "Could not delete department (it may have rooms assigned)",
        type: "error",
      });
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
              Departments & Approval Rules
            </h1>
            <p className="text-sm text-[var(--muted-foreground)]">
              Manage academic departments and configure the 2-tier approval workflow for specialized facilities (Labs & Exam Halls).
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchDepartments}
              isLoading={loading}
              className="gap-2"
            >
              <RotateCw className="w-4 h-4" />
              Refresh
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setFormData({ name: "", code: "", hod_approval_required: true });
                setFormErrors({});
                setCreateModalOpen(true);
              }}
              className="gap-2 bg-sky-600 hover:bg-sky-700 text-white"
            >
              <Plus className="w-4 h-4" />
              Add Department
            </Button>
          </div>
        </div>

        {/* Explain Card */}
        <div className="rounded-2xl border border-sky-500/20 bg-sky-500/5 p-4 flex items-start gap-3 text-xs text-sky-800 dark:text-sky-200">
          <HelpCircle className="w-5 h-5 text-sky-500 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold text-sm block mb-0.5 text-sky-900 dark:text-sky-100">
              HOD Approval Policy (SPEC Section 4)
            </span>
            When <strong>"HOD Approval Required"</strong> is enabled for a department, any booking request for a <strong>LAB</strong> or <strong>EXAM_HALL</strong> in that department automatically escalates to the HOD after block coordinator verification before confirmation.
          </div>
        </div>

        {/* Search */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
          <div className="w-full sm:w-80">
            <Input
              placeholder="Search department name or code..."
              icon={<Search className="w-4 h-4" />}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
        </div>

        {/* Table */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-[var(--foreground)]">
              <thead className="border-b border-[var(--border)] bg-slate-50/75 dark:bg-slate-900/40 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Code</th>
                  <th className="px-5 py-3.5">Department Name</th>
                  <th className="px-5 py-3.5">HOD Approval Required</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {loading ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={4} className="px-5 py-4">
                        <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                ) : departments.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-8">
                      <EmptyState
                        title="No departments found"
                        description="Add a department or adjust search keywords."
                      />
                    </td>
                  </tr>
                ) : (
                  departments.map((dept) => (
                    <tr key={dept.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30 transition-colors">
                      <td className="px-5 py-3.5 font-bold font-mono text-sky-600 dark:text-sky-400">
                        {dept.code}
                      </td>
                      <td className="px-5 py-3.5 font-medium text-[var(--foreground)]">
                        {dept.name}
                      </td>
                      <td className="px-5 py-3.5">
                        <button
                          type="button"
                          onClick={() => handleToggleHodApproval(dept)}
                          className={`group inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
                            dept.hod_approval_required
                              ? "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-200 dark:border-purple-800 hover:bg-purple-500/20"
                              : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:bg-slate-200 dark:hover:bg-slate-700"
                          }`}
                          title="Click to toggle HOD approval requirement"
                        >
                          {dept.hod_approval_required ? (
                            <>
                              <ShieldCheck className="w-4 h-4 text-purple-600 dark:text-purple-400" />
                              <span>Required (Active)</span>
                            </>
                          ) : (
                            <>
                              <ShieldAlert className="w-4 h-4 text-slate-400" />
                              <span>Optional (Bypassed)</span>
                            </>
                          )}
                          <span className="text-[10px] opacity-70 underline font-normal ml-1">
                            Toggle
                          </span>
                        </button>
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                            title="Edit department"
                            onClick={() => {
                              setActiveDept(dept);
                              setFormData({
                                name: dept.name,
                                code: dept.code,
                                hod_approval_required: dept.hod_approval_required,
                              });
                              setFormErrors({});
                              setEditModalOpen(true);
                            }}
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 text-rose-500 hover:text-rose-600"
                            title="Delete department"
                            onClick={() => {
                              setActiveDept(dept);
                              setDeleteConfirmOpen(true);
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

          {/* Pagination */}
          {total > pageSize && (
            <div className="p-4 border-t border-[var(--border)] flex items-center justify-between text-xs text-[var(--muted-foreground)]">
              <span>Showing {departments.length} of {total} departments</span>
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

        {/* Create Modal */}
        <Modal
          isOpen={createModalOpen}
          onClose={() => setCreateModalOpen(false)}
          title="Add New Department"
          description="Register a new academic department in the college."
          maxWidth="sm"
        >
          <form onSubmit={handleCreate} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Department Name *
              </label>
              <Input
                placeholder="e.g. Electrical Engineering"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                error={formErrors.name}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Department Code (Short Abbreviation) *
              </label>
              <Input
                placeholder="e.g. EE"
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                error={formErrors.code}
              />
            </div>

            <div className="flex justify-end gap-2.5 pt-4 border-t border-[var(--border)]">
              <Button type="button" variant="outline" onClick={() => setCreateModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={submitting} className="bg-sky-600 hover:bg-sky-700 text-white">
                Create Department
              </Button>
            </div>
          </form>
        </Modal>

        {/* Edit Modal */}
        <Modal
          isOpen={editModalOpen}
          onClose={() => setEditModalOpen(false)}
          title={`Edit Department: ${activeDept?.code || ""}`}
          description="Update department details and approval configuration."
          maxWidth="sm"
        >
          <form onSubmit={handleEdit} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Department Name *
              </label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                error={formErrors.name}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Department Code *
              </label>
              <Input
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
                error={formErrors.code}
              />
            </div>

            <div className="pt-2">
              <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-[var(--foreground)]">
                <input
                  type="checkbox"
                  className="rounded border-[var(--border)] text-purple-600 focus:ring-purple-500"
                  checked={formData.hod_approval_required}
                  onChange={(e) =>
                    setFormData({ ...formData, hod_approval_required: e.target.checked })
                  }
                />
                Require HOD approval for Labs & Exam Halls
              </label>
              <p className="text-[11px] text-[var(--muted-foreground)] mt-1 ml-5">
                When enabled, booking requests in this department will require approval from the assigned HOD.
              </p>
            </div>

            <div className="flex justify-end gap-2.5 pt-4 border-t border-[var(--border)]">
              <Button type="button" variant="outline" onClick={() => setEditModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={submitting} className="bg-sky-600 hover:bg-sky-700 text-white">
                Save Changes
              </Button>
            </div>
          </form>
        </Modal>

        {/* Delete Confirm */}
        <ConfirmDialog
          isOpen={deleteConfirmOpen}
          onClose={() => setDeleteConfirmOpen(false)}
          onConfirm={handleDelete}
          title="Delete Department"
          message={`Are you sure you want to delete ${activeDept?.name} (${activeDept?.code})? This action cannot be undone.`}
          confirmText="Delete Department"
          variant="danger"
        />
      </div>
    </DashboardShell>
  );
}

