"use client";

import * as React from "react";
import {
  Users,
  UserPlus,
  Search,
  RotateCw,
  Edit2,
  KeyRound,
  UserCheck,
  UserX,
  Check,
  Copy,
  AlertCircle,
  Building2,
  Shield,
  GraduationCap,
  Sparkles,
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
  User,
  UserRole,
  Department,
  Block,
  PaginatedResponse,
} from "@/lib/admin-types";

export default function AdminUsersPage() {
  const [users, setUsers] = React.useState<User[]>([]);
  const [departments, setDepartments] = React.useState<Department[]>([]);
  const [blocks, setBlocks] = React.useState<Block[]>([]);
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

  const [roleFilter, setRoleFilter] = React.useState<string>("");
  const [deptFilter, setDeptFilter] = React.useState<string>("");
  const [statusFilter, setStatusFilter] = React.useState<string>("");

  // Modals
  const [createModalOpen, setCreateModalOpen] = React.useState(false);
  const [editModalOpen, setEditModalOpen] = React.useState(false);
  const [resetPwdModalOpen, setResetPwdModalOpen] = React.useState(false);
  const [confirmStatusModal, setConfirmStatusModal] = React.useState<{
    isOpen: boolean;
    user: User | null;
    action: "activate" | "deactivate";
  }>({ isOpen: false, user: null, action: "deactivate" });

  const [activeUser, setActiveUser] = React.useState<User | null>(null);

  // Form states
  const [formData, setFormData] = React.useState<{
    name: string;
    email: string;
    role: UserRole;
    department_id: string;
    phone: string;
    assigned_block_ids: number[];
  }>({
    name: "",
    email: "",
    role: "FACULTY",
    department_id: "",
    phone: "",
    assigned_block_ids: [],
  });
  const [formErrors, setFormErrors] = React.useState<Record<string, string>>({});
  const [submitting, setSubmitting] = React.useState(false);

  // Password Reset state
  const [resetPasswordVal, setResetPasswordVal] = React.useState("");
  const [copiedPwd, setCopiedPwd] = React.useState(false);
  const [createdTempPwd, setCreatedTempPwd] = React.useState<{
    user: User;
    password?: string;
  } | null>(null);

  // Fetch departments & blocks for selectors
  const fetchMetadata = React.useCallback(async () => {
    try {
      const [deptRes, blockRes] = await Promise.all([
        apiClient<PaginatedResponse<Department>>("/api/admin/departments?page_size=100"),
        apiClient<PaginatedResponse<Block>>("/api/admin/blocks?page_size=100"),
      ]);
      setDepartments(deptRes.items || []);
      setBlocks(blockRes.items || []);
    } catch {
      // ignore
    }
  }, []);

  // Fetch users with filters
  const fetchUsers = React.useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        page_size: pageSize,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (roleFilter) params.role = roleFilter;
      if (deptFilter) params.department_id = deptFilter;
      if (statusFilter !== "") params.is_active = statusFilter === "true";

      const res = await apiClient<PaginatedResponse<User>>("/api/admin/users", {
        params,
      });
      setUsers(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      showToast({
        title: "Error loading users",
        message: err.message || "Failed to fetch user list",
        type: "error",
      });
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, debouncedSearch, roleFilter, deptFilter, statusFilter]);

  React.useEffect(() => {
    fetchMetadata();
  }, [fetchMetadata]);

  React.useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // Validation
  const validateForm = (isEdit = false) => {
    const errs: Record<string, string> = {};
    if (!formData.name.trim()) errs.name = "Full name is required";
    if (!formData.email.trim()) {
      errs.email = "Email address is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email.trim())) {
      errs.email = "Invalid email format";
    }
    if ((formData.role === "HOD" || formData.role === "FACULTY") && !formData.department_id) {
      errs.department_id = "Department is required for HOD and Faculty accounts";
    }
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  // Create user
  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm(false)) return;

    setSubmitting(true);
    try {
      const payload: any = {
        name: formData.name.trim(),
        email: formData.email.trim().toLowerCase(),
        role: formData.role,
        department_id: formData.department_id ? parseInt(formData.department_id, 10) : null,
        phone: formData.phone.trim() || null,
      };

      const res = await apiClient<User & { temporary_password?: string }>("/api/admin/users", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      // If coordinator, assign blocks
      if (formData.role === "COORDINATOR" && formData.assigned_block_ids.length > 0) {
        await Promise.all(
          formData.assigned_block_ids.map((bId) =>
            apiClient(`/api/admin/blocks/${bId}/coordinators`, {
              method: "POST",
              body: JSON.stringify({ user_id: res.id }),
            }).catch(() => null)
          )
        );
        fetchMetadata();
      }

      setCreateModalOpen(false);
      setCreatedTempPwd({ user: res, password: res.temporary_password });
      showToast({
        title: "Account Created",
        message: `Account for ${res.name} created successfully.`,
        type: "success",
      });
      fetchUsers();
    } catch (err: any) {
      showToast({
        title: "Creation Failed",
        message: err.message || "Could not create user",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Edit user
  const handleEditUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeUser || !validateForm(true)) return;

    setSubmitting(true);
    try {
      const payload: any = {
        name: formData.name.trim(),
        role: formData.role,
        department_id: formData.department_id ? parseInt(formData.department_id, 10) : null,
        phone: formData.phone.trim() || null,
      };

      await apiClient(`/api/admin/users/${activeUser.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });

      // Synchronize coordinator blocks if coordinator
      if (formData.role === "COORDINATOR") {
        for (const block of blocks) {
          const isCurrentlyAssigned = block.coordinators.some((c) => c.id === activeUser.id);
          const shouldBeAssigned = formData.assigned_block_ids.includes(block.id);

          if (!isCurrentlyAssigned && shouldBeAssigned) {
            await apiClient(`/api/admin/blocks/${block.id}/coordinators`, {
              method: "POST",
              body: JSON.stringify({ user_id: activeUser.id }),
            }).catch(() => null);
          } else if (isCurrentlyAssigned && !shouldBeAssigned) {
            await apiClient(`/api/admin/blocks/${block.id}/coordinators/${activeUser.id}`, {
              method: "DELETE",
            }).catch(() => null);
          }
        }
        fetchMetadata();
      }

      setEditModalOpen(false);
      showToast({
        title: "User Updated",
        message: `User details saved successfully.`,
        type: "success",
      });
      fetchUsers();
    } catch (err: any) {
      showToast({
        title: "Update Failed",
        message: err.message || "Could not update user details",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Open Edit Modal
  const openEditModal = (u: User) => {
    setActiveUser(u);
    // Find blocks where this user is coordinator
    const assignedIds = blocks
      .filter((b) => b.coordinators.some((c) => c.id === u.id))
      .map((b) => b.id);

    setFormData({
      name: u.name,
      email: u.email,
      role: u.role,
      department_id: u.department_id ? String(u.department_id) : "",
      phone: u.phone || "",
      assigned_block_ids: assignedIds,
    });
    setFormErrors({});
    setEditModalOpen(true);
  };

  // Reset password
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeUser) return;
    if (resetPasswordVal.length < 8) {
      showToast({
        title: "Invalid Password",
        message: "Password must be at least 8 characters long",
        type: "error",
      });
      return;
    }

    setSubmitting(true);
    try {
      await apiClient(`/api/admin/users/${activeUser.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          password: resetPasswordVal,
          must_change_password: true,
        }),
      });
      setResetPwdModalOpen(false);
      showToast({
        title: "Password Reset Successfully",
        message: `Temporary password set for ${activeUser.name}.`,
        type: "success",
      });
    } catch (err: any) {
      showToast({
        title: "Reset Failed",
        message: err.message || "Failed to reset password",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Toggle user active status
  const handleToggleStatus = async () => {
    if (!confirmStatusModal.user) return;
    const { user, action } = confirmStatusModal;
    try {
      await apiClient(`/api/admin/users/${user.id}/${action}`, {
        method: "POST",
      });
      showToast({
        title: action === "activate" ? "User Activated" : "User Deactivated",
        message: `${user.name} has been ${action}d.`,
        type: "info",
      });
      setConfirmStatusModal({ isOpen: false, user: null, action: "deactivate" });
      fetchUsers();
    } catch (err: any) {
      showToast({
        title: "Action Failed",
        message: err.message || "Could not change user status",
        type: "error",
      });
    }
  };

  // Helper: map department name
  const getDeptName = (deptId?: number | null) => {
    if (!deptId) return "—";
    const d = departments.find((dept) => dept.id === deptId);
    return d ? `${d.code} (${d.name})` : `#${deptId}`;
  };

  // Helper: get assigned blocks string for coordinator
  const getCoordinatorBlocks = (userId: number) => {
    const assigned = blocks.filter((b) => b.coordinators.some((c) => c.id === userId));
    return assigned.map((b) => b.name).join(", ") || "No blocks assigned";
  };

  const roleBadges: Record<UserRole, { label: string; color: string; icon: any }> = {
    ADMIN: { label: "Admin", color: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-200 dark:border-rose-900", icon: Shield },
    HOD: { label: "HOD", color: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-200 dark:border-purple-900", icon: GraduationCap },
    COORDINATOR: { label: "Coordinator", color: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-200 dark:border-sky-900", icon: Building2 },
    FACULTY: { label: "Faculty", color: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900", icon: Sparkles },
  };

  return (
    <DashboardShell
      role="ADMIN"
      userName="System Admin"
      userEmail="admin@git.edu"
    >
      <div className="space-y-6 pb-12">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-[var(--foreground)]">
              Staff & User Directory
            </h1>
            <p className="text-sm text-[var(--muted-foreground)]">
              Manage accounts, roles, departmental affiliations, and physical block coordinator assignments.
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchUsers}
              isLoading={loading}
              className="gap-2"
            >
              <RotateCw className="w-4 h-4" />
              Refresh
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setFormData({
                  name: "",
                  email: "",
                  role: "FACULTY",
                  department_id: "",
                  phone: "",
                  assigned_block_ids: [],
                });
                setFormErrors({});
                setCreateModalOpen(true);
              }}
              className="gap-2 bg-sky-600 hover:bg-sky-700 text-white"
            >
              <UserPlus className="w-4 h-4" />
              Add User
            </Button>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <Input
              placeholder="Search name, email, phone..."
              icon={<Search className="w-4 h-4" />}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
            <Select
              options={[
                { value: "", label: "All Roles" },
                { value: "ADMIN", label: "Admin" },
                { value: "HOD", label: "Department Head (HOD)" },
                { value: "COORDINATOR", label: "Block Coordinator" },
                { value: "FACULTY", label: "Faculty" },
              ]}
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value);
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
            <Select
              options={[
                { value: "", label: "All Statuses" },
                { value: "true", label: "Active Only" },
                { value: "false", label: "Deactivated" },
              ]}
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
            />
          </div>
        </div>

        {/* Users Table */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-[var(--foreground)]">
              <thead className="border-b border-[var(--border)] bg-slate-50/75 dark:bg-slate-900/40 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">User</th>
                  <th className="px-5 py-3.5">Role</th>
                  <th className="px-5 py-3.5">Department</th>
                  <th className="px-5 py-3.5">Scope / Blocks</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {loading ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={6} className="px-5 py-4">
                        <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                ) : users.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8">
                      <EmptyState
                        title="No users found"
                        description="Try modifying search keywords or clearing active filters."
                        action={{
                          label: "Clear Filters",
                          onClick: () => {
                            setSearch("");
                            setRoleFilter("");
                            setDeptFilter("");
                            setStatusFilter("");
                            setPage(1);
                          },
                        }}
                      />
                    </td>
                  </tr>
                ) : (
                  users.map((u) => {
                    const rBadge = roleBadges[u.role] || roleBadges.FACULTY;
                    const RIcon = rBadge.icon;
                    return (
                      <tr key={u.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30 transition-colors">
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-3">
                            <div className="h-9 w-9 rounded-full bg-sky-500/10 text-sky-600 dark:text-sky-400 font-bold flex items-center justify-center text-xs shrink-0">
                              {u.name.charAt(0).toUpperCase()}
                            </div>
                            <div className="min-w-0">
                              <p className="font-semibold text-[var(--foreground)] truncate">{u.name}</p>
                              <p className="text-xs text-[var(--muted-foreground)] truncate">{u.email}</p>
                              {u.phone && <p className="text-[11px] text-[var(--muted-foreground)]">{u.phone}</p>}
                            </div>
                          </div>
                        </td>
                        <td className="px-5 py-3.5">
                          <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${rBadge.color}`}>
                            <RIcon className="w-3.5 h-3.5" />
                            {rBadge.label}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-xs text-[var(--muted-foreground)] font-medium">
                          {getDeptName(u.department_id)}
                        </td>
                        <td className="px-5 py-3.5 text-xs">
                          {u.role === "COORDINATOR" ? (
                            <span className="text-sky-600 dark:text-sky-400 font-medium bg-sky-50 dark:bg-sky-950/50 px-2 py-0.5 rounded-md border border-sky-200 dark:border-sky-900">
                              {getCoordinatorBlocks(u.id)}
                            </span>
                          ) : (
                            <span className="text-[var(--muted-foreground)]">—</span>
                          )}
                        </td>
                        <td className="px-5 py-3.5">
                          <StatusBadge
                            status={u.is_active ? "ACTIVE" : "REJECTED"}
                            label={u.is_active ? "Active" : "Inactive"}
                          />
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0"
                              title="Edit user"
                              onClick={() => openEditModal(u)}
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 text-amber-600 dark:text-amber-400"
                              title="Reset password"
                              onClick={() => {
                                setActiveUser(u);
                                setResetPasswordVal("College@2026!");
                                setResetPwdModalOpen(true);
                              }}
                            >
                              <KeyRound className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className={`h-8 w-8 p-0 ${u.is_active ? "text-rose-500 hover:text-rose-600" : "text-emerald-500 hover:text-emerald-600"}`}
                              title={u.is_active ? "Deactivate account" : "Activate account"}
                              onClick={() =>
                                setConfirmStatusModal({
                                  isOpen: true,
                                  user: u,
                                  action: u.is_active ? "deactivate" : "activate",
                                })
                              }
                            >
                              {u.is_active ? <UserX className="w-3.5 h-3.5" /> : <UserCheck className="w-3.5 h-3.5" />}
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

          {/* Pagination Footer */}
          {total > pageSize && (
            <div className="p-4 border-t border-[var(--border)] flex items-center justify-between text-xs text-[var(--muted-foreground)]">
              <span>
                Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {total} accounts
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </Button>
                <span className="font-semibold px-2">Page {page} of {Math.ceil(total / pageSize)}</span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= Math.ceil(total / pageSize)}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Create User Modal */}
        <Modal
          isOpen={createModalOpen}
          onClose={() => setCreateModalOpen(false)}
          title="Create Staff Account"
          description="Provision a new HOD, Coordinator, or Faculty member account."
          maxWidth="lg"
        >
          <form onSubmit={handleCreateUser} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Full Name *
              </label>
              <Input
                placeholder="Dr. Jane Smith"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                error={formErrors.name}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Email Address *
              </label>
              <Input
                type="email"
                placeholder="jane.smith@college.edu"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                error={formErrors.email}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  System Role *
                </label>
                <Select
                  options={[
                    { value: "FACULTY", label: "Academic Faculty" },
                    { value: "COORDINATOR", label: "Block Coordinator" },
                    { value: "HOD", label: "Department Head (HOD)" },
                    { value: "ADMIN", label: "System Administrator" },
                  ]}
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value as UserRole })}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Department {formData.role === "HOD" || formData.role === "FACULTY" ? "*" : "(Optional)"}
                </label>
                <Select
                  options={[
                    { value: "", label: "Select Department..." },
                    ...departments.map((d) => ({ value: String(d.id), label: `${d.code} - ${d.name}` })),
                  ]}
                  value={formData.department_id}
                  onChange={(e) => setFormData({ ...formData, department_id: e.target.value })}
                  error={formErrors.department_id}
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Phone Number (Optional)
              </label>
              <Input
                placeholder="+91 9876543210"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              />
            </div>

            {/* If Coordinator: block multi-select assignment */}
            {formData.role === "COORDINATOR" && (
              <div className="pt-2 border-t border-[var(--border)]">
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-2">
                  Assign Physical Blocks (Coordinators oversee room bookings in assigned blocks)
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {blocks.map((b) => {
                    const isChecked = formData.assigned_block_ids.includes(b.id);
                    return (
                      <label
                        key={b.id}
                        className={`flex items-center gap-2 p-2.5 rounded-xl border text-xs cursor-pointer transition-colors ${
                          isChecked
                            ? "bg-sky-500/10 border-sky-500/30 text-sky-700 dark:text-sky-300"
                            : "border-[var(--border)] text-[var(--foreground)] hover:bg-slate-50 dark:hover:bg-slate-900"
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="rounded border-[var(--border)] text-sky-600 focus:ring-sky-500"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setFormData({
                                ...formData,
                                assigned_block_ids: [...formData.assigned_block_ids, b.id],
                              });
                            } else {
                              setFormData({
                                ...formData,
                                assigned_block_ids: formData.assigned_block_ids.filter((id) => id !== b.id),
                              });
                            }
                          }}
                        />
                        <span className="font-medium truncate">{b.name}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="flex justify-end gap-2.5 pt-4 border-t border-[var(--border)]">
              <Button type="button" variant="outline" onClick={() => setCreateModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={submitting} className="bg-sky-600 hover:bg-sky-700 text-white">
                Create Account
              </Button>
            </div>
          </form>
        </Modal>

        {/* Edit User Modal */}
        <Modal
          isOpen={editModalOpen}
          onClose={() => setEditModalOpen(false)}
          title={`Edit Account: ${activeUser?.name || ""}`}
          description="Update role, assigned department, and coordinator building assignments."
          maxWidth="lg"
        >
          <form onSubmit={handleEditUser} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Full Name *
              </label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                error={formErrors.name}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Email Address (Read-only)
              </label>
              <Input value={formData.email} disabled className="opacity-70 cursor-not-allowed" />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  System Role
                </label>
                <Select
                  options={[
                    { value: "FACULTY", label: "Academic Faculty" },
                    { value: "COORDINATOR", label: "Block Coordinator" },
                    { value: "HOD", label: "Department Head (HOD)" },
                    { value: "ADMIN", label: "System Administrator" },
                  ]}
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value as UserRole })}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Department {formData.role === "HOD" || formData.role === "FACULTY" ? "*" : "(Optional)"}
                </label>
                <Select
                  options={[
                    { value: "", label: "Select Department..." },
                    ...departments.map((d) => ({ value: String(d.id), label: `${d.code} - ${d.name}` })),
                  ]}
                  value={formData.department_id}
                  onChange={(e) => setFormData({ ...formData, department_id: e.target.value })}
                  error={formErrors.department_id}
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Phone Number
              </label>
              <Input
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              />
            </div>

            {/* Coordinator block assignments */}
            {formData.role === "COORDINATOR" && (
              <div className="pt-2 border-t border-[var(--border)]">
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-2">
                  Assigned Physical Blocks
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {blocks.map((b) => {
                    const isChecked = formData.assigned_block_ids.includes(b.id);
                    return (
                      <label
                        key={b.id}
                        className={`flex items-center gap-2 p-2.5 rounded-xl border text-xs cursor-pointer transition-colors ${
                          isChecked
                            ? "bg-sky-500/10 border-sky-500/30 text-sky-700 dark:text-sky-300"
                            : "border-[var(--border)] text-[var(--foreground)] hover:bg-slate-50 dark:hover:bg-slate-900"
                        }`}
                      >
                        <input
                          type="checkbox"
                          className="rounded border-[var(--border)] text-sky-600 focus:ring-sky-500"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setFormData({
                                ...formData,
                                assigned_block_ids: [...formData.assigned_block_ids, b.id],
                              });
                            } else {
                              setFormData({
                                ...formData,
                                assigned_block_ids: formData.assigned_block_ids.filter((id) => id !== b.id),
                              });
                            }
                          }}
                        />
                        <span className="font-medium truncate">{b.name}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            )}

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

        {/* Reset Password Modal */}
        <Modal
          isOpen={resetPwdModalOpen}
          onClose={() => setResetPwdModalOpen(false)}
          title={`Reset Password for ${activeUser?.name || ""}`}
          description="Provide a new temporary password. The user will be required to change it upon next login."
          maxWidth="sm"
        >
          <form onSubmit={handleResetPassword} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                New Temporary Password
              </label>
              <div className="flex items-center gap-2">
                <Input
                  type="text"
                  value={resetPasswordVal}
                  onChange={(e) => setResetPasswordVal(e.target.value)}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const rnd = "TempPass#" + Math.floor(1000 + Math.random() * 9000);
                    setResetPasswordVal(rnd);
                  }}
                >
                  Generate
                </Button>
              </div>
              <p className="mt-1 text-[11px] text-[var(--muted-foreground)]">
                Must be at least 8 characters. User must update it on login.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-4 border-t border-[var(--border)]">
              <Button type="button" variant="outline" onClick={() => setResetPwdModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={submitting} className="bg-amber-600 hover:bg-amber-700 text-white">
                Apply Reset
              </Button>
            </div>
          </form>
        </Modal>

        {/* Temporary Password Notification Dialog after Creation */}
        {createdTempPwd && (
          <Modal
            isOpen={true}
            onClose={() => setCreatedTempPwd(null)}
            title="Account Created Successfully"
            description="Copy the temporary password generated for this staff member."
            maxWidth="sm"
          >
            <div className="space-y-4 pt-2">
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-900 border border-[var(--border)] space-y-2">
                <div>
                  <span className="text-xs text-[var(--muted-foreground)] block">User:</span>
                  <span className="font-semibold text-sm text-[var(--foreground)]">{createdTempPwd.user.name} ({createdTempPwd.user.email})</span>
                </div>
                <div>
                  <span className="text-xs text-[var(--muted-foreground)] block">Temporary Password:</span>
                  <div className="flex items-center justify-between mt-1 p-2 rounded-lg bg-[var(--card)] border border-[var(--border)] font-mono text-sm font-bold text-sky-600 dark:text-sky-400">
                    <span>{createdTempPwd.password || "Sent via Email"}</span>
                    {createdTempPwd.password && (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs gap-1"
                        onClick={() => {
                          navigator.clipboard.writeText(createdTempPwd.password || "");
                          setCopiedPwd(true);
                          setTimeout(() => setCopiedPwd(false), 2000);
                        }}
                      >
                        {copiedPwd ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                        {copiedPwd ? "Copied" : "Copy"}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
              <p className="text-xs text-[var(--muted-foreground)]">
                An onboarding email has also been dispatched with login credentials.
              </p>
              <div className="flex justify-end pt-2">
                <Button onClick={() => setCreatedTempPwd(null)}>Done</Button>
              </div>
            </div>
          </Modal>
        )}

        {/* Activate / Deactivate Confirmation */}
        <ConfirmDialog
          isOpen={confirmStatusModal.isOpen}
          onClose={() => setConfirmStatusModal({ isOpen: false, user: null, action: "deactivate" })}
          onConfirm={handleToggleStatus}
          title={confirmStatusModal.action === "activate" ? "Activate User Account" : "Deactivate User Account"}
          message={`Are you sure you want to ${confirmStatusModal.action} the account for ${confirmStatusModal.user?.name}? ${
            confirmStatusModal.action === "deactivate"
              ? "They will no longer be able to log in or approve bookings."
              : "They will regain portal access."
          }`}
          confirmText={confirmStatusModal.action === "activate" ? "Activate" : "Deactivate"}
          variant={confirmStatusModal.action === "activate" ? "info" : "danger"}
        />
      </div>
    </DashboardShell>
  );
}
