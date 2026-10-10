"use client";

import * as React from "react";
import {
  Boxes,
  Plus,
  Search,
  RotateCw,
  Edit2,
  Trash2,
  UserPlus,
  X,
  UserCheck,
  Building2,
  Users,
} from "lucide-react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Modal } from "@/components/ui/modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { showToast } from "@/components/ui/toast";
import { apiClient } from "@/lib/api-client";
import { Block, User, PaginatedResponse } from "@/lib/admin-types";

export default function AdminBlocksPage() {
  const [blocks, setBlocks] = React.useState<Block[]>([]);
  const [coordinators, setCoordinators] = React.useState<User[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [pageSize] = React.useState(15);
  const [search, setSearch] = React.useState("");

  // Modals
  const [createModalOpen, setCreateModalOpen] = React.useState(false);
  const [editModalOpen, setEditModalOpen] = React.useState(false);
  const [assignModalOpen, setAssignModalOpen] = React.useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = React.useState(false);

  const [activeBlock, setActiveBlock] = React.useState<Block | null>(null);

  // Form states
  const [formData, setFormData] = React.useState({
    name: "",
    description: "",
  });
  const [selectedCoordId, setSelectedCoordId] = React.useState<string>("");
  const [submitting, setSubmitting] = React.useState(false);

  // Fetch coordinators
  const fetchCoordinators = React.useCallback(async () => {
    try {
      const res = await apiClient<PaginatedResponse<User>>("/api/admin/users?role=COORDINATOR&page_size=100");
      setCoordinators(res.items || []);
    } catch {
      // ignore
    }
  }, []);

  // Fetch blocks
  const fetchBlocks = React.useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (search.trim()) params.search = search.trim();

      const res = await apiClient<PaginatedResponse<Block>>("/api/admin/blocks", {
        params,
      });
      setBlocks(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      showToast({
        title: "Error loading blocks",
        message: err.message || "Failed to fetch blocks",
        type: "error",
      });
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search]);

  React.useEffect(() => {
    fetchBlocks();
    fetchCoordinators();
  }, [fetchBlocks, fetchCoordinators]);

  // Create block
  const handleCreateBlock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      showToast({ title: "Validation Error", message: "Block name is required", type: "error" });
      return;
    }

    setSubmitting(true);
    try {
      await apiClient("/api/admin/blocks", {
        method: "POST",
        body: JSON.stringify({
          name: formData.name.trim(),
          description: formData.description.trim() || null,
        }),
      });
      setCreateModalOpen(false);
      showToast({ title: "Block Created", message: `${formData.name} added.`, type: "success" });
      fetchBlocks();
    } catch (err: any) {
      showToast({ title: "Creation Failed", message: err.message || "Failed to create block", type: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  // Edit block
  const handleEditBlock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeBlock || !formData.name.trim()) return;

    setSubmitting(true);
    try {
      await apiClient(`/api/admin/blocks/${activeBlock.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: formData.name.trim(),
          description: formData.description.trim() || null,
        }),
      });
      setEditModalOpen(false);
      showToast({ title: "Block Updated", message: "Block details saved.", type: "success" });
      fetchBlocks();
    } catch (err: any) {
      showToast({ title: "Update Failed", message: err.message || "Failed to update block", type: "error" });
    } finally {
      setSubmitting(false);
    }
  };

  // Delete block
  const handleDeleteBlock = async () => {
    if (!activeBlock) return;
    try {
      await apiClient(`/api/admin/blocks/${activeBlock.id}`, {
        method: "DELETE",
      });
      setDeleteConfirmOpen(false);
      showToast({ title: "Block Deleted", message: `${activeBlock.name} deleted.`, type: "info" });
      fetchBlocks();
    } catch (err: any) {
      showToast({ title: "Delete Failed", message: err.message || "Could not delete block", type: "error" });
    }
  };

  // Assign coordinator
  const handleAssignCoordinator = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeBlock || !selectedCoordId) {
      showToast({ title: "Validation Error", message: "Please select a coordinator", type: "error" });
      return;
    }

    setSubmitting(true);
    try {
      await apiClient(`/api/admin/blocks/${activeBlock.id}/coordinators`, {
        method: "POST",
        body: JSON.stringify({ user_id: parseInt(selectedCoordId, 10) }),
      });
      setAssignModalOpen(false);
      showToast({
        title: "Coordinator Assigned",
        message: `Coordinator assigned to ${activeBlock.name}.`,
        type: "success",
      });
      fetchBlocks();
    } catch (err: any) {
      showToast({
        title: "Assignment Failed",
        message: err.message || "Failed to assign coordinator",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Unassign coordinator
  const handleUnassignCoordinator = async (block: Block, coordId: number) => {
    try {
      await apiClient(`/api/admin/blocks/${block.id}/coordinators/${coordId}`, {
        method: "DELETE",
      });
      showToast({
        title: "Coordinator Removed",
        message: "Coordinator unassigned from block.",
        type: "info",
      });
      fetchBlocks();
    } catch (err: any) {
      showToast({
        title: "Failed to Unassign",
        message: err.message || "Could not remove coordinator",
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
              Physical Blocks & Coordinators
            </h1>
            <p className="text-sm text-[var(--muted-foreground)]">
              Manage college building wings and designate block coordinators who verify and approve room requests.
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchBlocks}
              isLoading={loading}
              className="gap-2"
            >
              <RotateCw className="w-4 h-4" />
              Refresh
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setFormData({ name: "", description: "" });
                setCreateModalOpen(true);
              }}
              className="gap-2 bg-sky-600 hover:bg-sky-700 text-white"
            >
              <Plus className="w-4 h-4" />
              Add Block
            </Button>
          </div>
        </div>

        {/* Search */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
          <div className="w-full sm:w-80">
            <Input
              placeholder="Search blocks..."
              icon={<Search className="w-4 h-4" />}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
        </div>

        {/* Blocks Table */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-[var(--foreground)]">
              <thead className="border-b border-[var(--border)] bg-slate-50/75 dark:bg-slate-900/40 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Block Name</th>
                  <th className="px-5 py-3.5">Description</th>
                  <th className="px-5 py-3.5">Assigned Coordinators</th>
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
                ) : blocks.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-8">
                      <EmptyState
                        title="No blocks found"
                        description="Add a block to catalog physical campus buildings."
                      />
                    </td>
                  </tr>
                ) : (
                  blocks.map((block) => (
                    <tr key={block.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30 transition-colors">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2.5">
                          <div className="h-8 w-8 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 flex items-center justify-center shrink-0">
                            <Building2 className="w-4 h-4" />
                          </div>
                          <span className="font-bold text-[var(--foreground)]">{block.name}</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-xs text-[var(--muted-foreground)]">
                        {block.description || "—"}
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex flex-wrap items-center gap-1.5">
                          {block.coordinators && block.coordinators.length > 0 ? (
                            block.coordinators.map((c) => (
                              <span
                                key={c.id}
                                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-900"
                              >
                                <span>{c.name}</span>
                                <button
                                  type="button"
                                  onClick={() => handleUnassignCoordinator(block, c.id)}
                                  className="text-sky-400 hover:text-rose-500 rounded-full p-0.5"
                                  title={`Remove ${c.name} from ${block.name}`}
                                >
                                  <X className="w-3 h-3" />
                                </button>
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">
                              No coordinator assigned
                            </span>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 text-xs px-2 gap-1 text-sky-600 hover:text-sky-700"
                            onClick={() => {
                              setActiveBlock(block);
                              setSelectedCoordId("");
                              setAssignModalOpen(true);
                            }}
                          >
                            <UserPlus className="w-3 h-3" />
                            Assign
                          </Button>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                            title="Edit block"
                            onClick={() => {
                              setActiveBlock(block);
                              setFormData({
                                name: block.name,
                                description: block.description || "",
                              });
                              setEditModalOpen(true);
                            }}
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0 text-rose-500 hover:text-rose-600"
                            title="Delete block"
                            onClick={() => {
                              setActiveBlock(block);
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
              <span>Showing {blocks.length} of {total} blocks</span>
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

        {/* Create Block Modal */}
        <Modal
          isOpen={createModalOpen}
          onClose={() => setCreateModalOpen(false)}
          title="Add Physical Block"
          description="Create a physical building wing or institutional block."
          maxWidth="sm"
        >
          <form onSubmit={handleCreateBlock} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Block Name *
              </label>
              <Input
                placeholder="e.g. Science Block, Wing B"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Description (Optional)
              </label>
              <Input
                placeholder="e.g. Main lecture halls & physics labs"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>

            <div className="flex justify-end gap-2.5 pt-4 border-t border-[var(--border)]">
              <Button type="button" variant="outline" onClick={() => setCreateModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={submitting} className="bg-sky-600 hover:bg-sky-700 text-white">
                Create Block
              </Button>
            </div>
          </form>
        </Modal>

        {/* Edit Block Modal */}
        <Modal
          isOpen={editModalOpen}
          onClose={() => setEditModalOpen(false)}
          title={`Edit Block: ${activeBlock?.name || ""}`}
          description="Update block details."
          maxWidth="sm"
        >
          <form onSubmit={handleEditBlock} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Block Name *
              </label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Description
              </label>
              <Input
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
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

        {/* Assign Coordinator Modal */}
        <Modal
          isOpen={assignModalOpen}
          onClose={() => setAssignModalOpen(false)}
          title={`Assign Coordinator to ${activeBlock?.name || ""}`}
          description="Select a coordinator to manage and review room bookings within this block."
          maxWidth="sm"
        >
          <form onSubmit={handleAssignCoordinator} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Select Coordinator
              </label>
              <Select
                options={[
                  { value: "", label: "Choose coordinator..." },
                  ...coordinators.map((c) => ({
                    value: String(c.id),
                    label: `${c.name} (${c.email})`,
                  })),
                ]}
                value={selectedCoordId}
                onChange={(e) => setSelectedCoordId(e.target.value)}
              />
            </div>

            <div className="flex justify-end gap-2.5 pt-4 border-t border-[var(--border)]">
              <Button type="button" variant="outline" onClick={() => setAssignModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={submitting} className="bg-sky-600 hover:bg-sky-700 text-white">
                Assign Coordinator
              </Button>
            </div>
          </form>
        </Modal>

        {/* Delete Confirm */}
        <ConfirmDialog
          isOpen={deleteConfirmOpen}
          onClose={() => setDeleteConfirmOpen(false)}
          onConfirm={handleDeleteBlock}
          title="Delete Block"
          message={`Are you sure you want to delete ${activeBlock?.name}? Rooms inside this block must be removed or moved first.`}
          confirmText="Delete Block"
          variant="danger"
        />
      </div>
    </DashboardShell>
  );
}
