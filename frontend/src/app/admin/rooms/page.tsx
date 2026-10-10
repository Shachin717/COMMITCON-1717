"use client";

import * as React from "react";
import {
  DoorOpen,
  Plus,
  Search,
  RotateCw,
  Edit2,
  Trash2,
  Upload,
  FileSpreadsheet,
  AlertTriangle,
  CheckCircle,
  Building2,
  Layers,
  Wrench,
  Download,
  Info,
  ShieldAlert,
} from "lucide-react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { BlockedRoomsView } from "@/components/coordinator/blocked-rooms-view";
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
  Room,
  RoomType,
  RoomStatus,
  Block,
  Department,
  Facility,
  PaginatedResponse,
} from "@/lib/admin-types";

export default function AdminRoomsPage() {
  const [rooms, setRooms] = React.useState<Room[]>([]);
  const [blocks, setBlocks] = React.useState<Block[]>([]);
  const [departments, setDepartments] = React.useState<Department[]>([]);
  const [allFacilities, setAllFacilities] = React.useState<Facility[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [total, setTotal] = React.useState(0);
  const [page, setPage] = React.useState(1);
  const [pageSize] = React.useState(15);

  // Tabs
  const [activeTab, setActiveTab] = React.useState<"catalog" | "blocks">("catalog");

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

  const [blockFilter, setBlockFilter] = React.useState("");
  const [deptFilter, setDeptFilter] = React.useState("");
  const [typeFilter, setTypeFilter] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("");

  // Modals
  const [createModalOpen, setCreateModalOpen] = React.useState(false);
  const [editModalOpen, setEditModalOpen] = React.useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = React.useState(false);
  const [csvModalOpen, setCsvModalOpen] = React.useState(false);
  const [maintenanceModalOpen, setMaintenanceModalOpen] = React.useState(false);

  const [activeRoom, setActiveRoom] = React.useState<Room | null>(null);

  // Form states
  const [formData, setFormData] = React.useState<{
    name: string;
    block_id: string;
    floor: number;
    room_type: RoomType;
    capacity: number;
    department_id: string;
    status: RoomStatus;
    maintenance_note: string;
    facility_ids: number[];
  }>({
    name: "",
    block_id: "",
    floor: 1,
    room_type: "CLASSROOM",
    capacity: 60,
    department_id: "",
    status: "ACTIVE",
    maintenance_note: "",
    facility_ids: [],
  });
  const [formErrors, setFormErrors] = React.useState<Record<string, string>>({});
  const [submitting, setSubmitting] = React.useState(false);

  // Maintenance Quick Toggle state
  const [maintStatus, setMaintStatus] = React.useState<RoomStatus>("MAINTENANCE");
  const [maintNote, setMaintNote] = React.useState("");

  // CSV Import state
  const [csvFile, setCsvFile] = React.useState<File | null>(null);
  const [csvResult, setCsvResult] = React.useState<{
    total_rows: number;
    imported: number;
    errors: { row: number; error: string }[];
  } | null>(null);

  // Fetch metadata (blocks, departments, facilities)
  const fetchMetadata = React.useCallback(async () => {
    try {
      const [blockRes, deptRes, facRes] = await Promise.all([
        apiClient<PaginatedResponse<Block>>("/api/admin/blocks?page_size=100"),
        apiClient<PaginatedResponse<Department>>("/api/admin/departments?page_size=100"),
        apiClient<PaginatedResponse<Facility>>("/api/admin/facilities?page_size=100"),
      ]);
      setBlocks(blockRes.items || []);
      setDepartments(deptRes.items || []);
      setAllFacilities(facRes.items || []);
    } catch {
      // ignore
    }
  }, []);

  // Fetch rooms
  const fetchRooms = React.useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        page_size: pageSize,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (blockFilter) params.block_id = blockFilter;
      if (deptFilter) params.department_id = deptFilter;
      if (typeFilter) params.room_type = typeFilter;
      if (statusFilter) params.status = statusFilter;

      const res = await apiClient<PaginatedResponse<Room>>("/api/admin/rooms", {
        params,
      });
      setRooms(res.items || []);
      setTotal(res.total || 0);
    } catch (err: any) {
      showToast({
        title: "Error loading rooms",
        message: err.message || "Failed to fetch room catalog",
        type: "error",
      });
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, debouncedSearch, blockFilter, deptFilter, typeFilter, statusFilter]);

  React.useEffect(() => {
    fetchMetadata();
  }, [fetchMetadata]);

  React.useEffect(() => {
    fetchRooms();
  }, [fetchRooms]);

  // Validation
  const validateForm = () => {
    const errs: Record<string, string> = {};
    if (!formData.name.trim()) errs.name = "Room identifier is required";
    if (!formData.block_id) errs.block_id = "Physical block selection is required";
    if (!formData.capacity || formData.capacity <= 0) {
      errs.capacity = "Capacity must be greater than 0";
    }
    if (formData.room_type === "LAB" && !formData.department_id) {
      errs.department_id = "Department is required for LAB rooms";
    }
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  // Create room
  const handleCreateRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setSubmitting(true);
    try {
      const payload: any = {
        name: formData.name.trim(),
        block_id: parseInt(formData.block_id, 10),
        floor: Number(formData.floor),
        room_type: formData.room_type,
        capacity: Number(formData.capacity),
        department_id: formData.department_id ? parseInt(formData.department_id, 10) : null,
        status: formData.status,
        maintenance_note: formData.maintenance_note.trim() || null,
        facility_ids: formData.facility_ids,
      };

      await apiClient("/api/admin/rooms", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setCreateModalOpen(false);
      showToast({
        title: "Room Added",
        message: `${formData.name} added to catalog.`,
        type: "success",
      });
      fetchRooms();
    } catch (err: any) {
      showToast({
        title: "Creation Failed",
        message: err.message || "Could not add room",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Edit room
  const handleEditRoom = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeRoom || !validateForm()) return;

    setSubmitting(true);
    try {
      const payload: any = {
        name: formData.name.trim(),
        block_id: parseInt(formData.block_id, 10),
        floor: Number(formData.floor),
        room_type: formData.room_type,
        capacity: Number(formData.capacity),
        department_id: formData.department_id ? parseInt(formData.department_id, 10) : null,
        status: formData.status,
        maintenance_note: formData.maintenance_note.trim() || null,
        facility_ids: formData.facility_ids,
      };

      await apiClient(`/api/admin/rooms/${activeRoom.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });

      setEditModalOpen(false);
      showToast({
        title: "Room Updated",
        message: `Changes to ${formData.name} saved.`,
        type: "success",
      });
      fetchRooms();
    } catch (err: any) {
      showToast({
        title: "Update Failed",
        message: err.message || "Could not update room",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Quick maintenance toggle
  const handleSaveMaintenance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeRoom) return;

    setSubmitting(true);
    try {
      await apiClient(`/api/admin/rooms/${activeRoom.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({
          status: maintStatus,
          maintenance_note: maintStatus === "MAINTENANCE" ? maintNote.trim() || "Under scheduled maintenance" : null,
        }),
      });

      setMaintenanceModalOpen(false);
      showToast({
        title: maintStatus === "MAINTENANCE" ? "Room Set to Maintenance" : "Room Restored to Active",
        message:
          maintStatus === "MAINTENANCE"
            ? `${activeRoom.name} is now in MAINTENANCE. Launch Allocation Insights to re-optimize affected bookings.`
            : `${activeRoom.name} is now ACTIVE.`,
        type: maintStatus === "MAINTENANCE" ? "warning" : "success",
      });
      fetchRooms();
    } catch (err: any) {
      showToast({
        title: "Status Update Failed",
        message: err.message || "Failed to update room status",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Open Quick Maintenance modal
  const openMaintenanceModal = (r: Room) => {
    setActiveRoom(r);
    const nextStatus = r.status === "ACTIVE" ? "MAINTENANCE" : "ACTIVE";
    setMaintStatus(nextStatus);
    setMaintNote(r.maintenance_note || "");
    setMaintenanceModalOpen(true);
  };

  // Open Edit modal
  const openEditModal = (r: Room) => {
    setActiveRoom(r);
    setFormData({
      name: r.name,
      block_id: String(r.block_id),
      floor: r.floor,
      room_type: r.room_type,
      capacity: r.capacity,
      department_id: r.department_id ? String(r.department_id) : "",
      status: r.status,
      maintenance_note: r.maintenance_note || "",
      facility_ids: r.facilities.map((f) => f.id),
    });
    setFormErrors({});
    setEditModalOpen(true);
  };

  // Delete room
  const handleDeleteRoom = async () => {
    if (!activeRoom) return;
    try {
      await apiClient(`/api/admin/rooms/${activeRoom.id}`, {
        method: "DELETE",
      });
      setDeleteConfirmOpen(false);
      showToast({
        title: "Room Deleted",
        message: `${activeRoom.name} deleted successfully.`,
        type: "info",
      });
      fetchRooms();
    } catch (err: any) {
      showToast({
        title: "Delete Failed",
        message: err.message || "Cannot delete room with active bookings or timetable entries",
        type: "error",
      });
    }
  };

  // CSV Import
  const handleCsvImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!csvFile) {
      showToast({ title: "No file selected", message: "Choose a CSV file to upload", type: "error" });
      return;
    }

    setSubmitting(true);
    setCsvResult(null);
    try {
      const data = new FormData();
      data.append("file", csvFile);

      const res = await apiClient<{
        total_rows: number;
        imported: number;
        errors: { row: number; error: string }[];
      }>("/api/admin/rooms/import-csv", {
        method: "POST",
        body: data,
      });

      setCsvResult(res);
      showToast({
        title: "CSV Import Complete",
        message: `Imported ${res.imported} of ${res.total_rows} rooms.`,
        type: res.errors.length === 0 ? "success" : "warning",
      });
      fetchRooms();
    } catch (err: any) {
      showToast({
        title: "Import Error",
        message: err.message || "Failed to process CSV file",
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Download Sample CSV
  const handleDownloadSample = () => {
    const csvContent =
      "name,block,floor,room_type,capacity,department,facilities,status,maintenance_note\n" +
      "A-101,Block A,1,CLASSROOM,60,,Projector;AC;Smart Board,ACTIVE,\n" +
      "CS-LAB-01,Block A,2,LAB,40,CSE,PCs;AC;Internet;Projector,ACTIVE,\n" +
      "EXAM-HALL-1,Science Block,1,EXAM_HALL,120,,AC;Mic;Sound System,ACTIVE,\n" +
      "AUDITORIUM,Block B,1,SEMINAR_HALL,250,,AC;Projector;Mic;Sound System,ACTIVE,\n";

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "sample_rooms.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Helpers
  const getBlockName = (bId: number) => blocks.find((b) => b.id === bId)?.name || `#${bId}`;
  const getDeptCode = (dId?: number | null) => (dId ? departments.find((d) => d.id === dId)?.code || `#${dId}` : "—");

  const roomTypeBadges: Record<RoomType, { label: string; color: string }> = {
    CLASSROOM: { label: "Classroom", color: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-200 dark:border-blue-900" },
    LAB: { label: "Laboratory", color: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-200 dark:border-purple-900" },
    EXAM_HALL: { label: "Exam Hall", color: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-900" },
    SEMINAR_HALL: { label: "Seminar Hall", color: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900" },
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
              Room Catalog & Facilities
            </h1>
            <p className="text-sm text-[var(--muted-foreground)]">
              Manage lecture halls, departmental laboratories, seating capacity, amenities, and maintenance blackouts.
            </p>
          </div>
          <div className="flex items-center gap-2.5">
            {activeTab === "catalog" && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={fetchRooms}
                  isLoading={loading}
                  className="gap-2"
                >
                  <RotateCw className="w-4 h-4" />
                  Refresh
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setCsvFile(null);
                    setCsvResult(null);
                    setCsvModalOpen(true);
                  }}
                  className="gap-2"
                >
                  <Upload className="w-4 h-4" />
                  Bulk CSV Import
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    setFormData({
                      name: "",
                      block_id: blocks[0] ? String(blocks[0].id) : "",
                      floor: 1,
                      room_type: "CLASSROOM",
                      capacity: 60,
                      department_id: "",
                      status: "ACTIVE",
                      maintenance_note: "",
                      facility_ids: [],
                    });
                    setFormErrors({});
                    setCreateModalOpen(true);
                  }}
                  className="gap-2 bg-sky-600 hover:bg-sky-700 text-white"
                >
                  <Plus className="w-4 h-4" />
                  Add Room
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-2 border-b border-[var(--border)] pb-2">
          <button
            type="button"
            onClick={() => setActiveTab("catalog")}
            className={`px-4 py-2 text-sm font-semibold rounded-xl transition-all ${
              activeTab === "catalog"
                ? "bg-sky-500/10 text-sky-600 dark:text-sky-400 border border-sky-500/20 shadow-xs"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)]"
            }`}
          >
            Room Catalog
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("blocks")}
            className={`px-4 py-2 text-sm font-semibold rounded-xl transition-all ${
              activeTab === "blocks"
                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 shadow-xs"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--accent)]"
            }`}
          >
            Blocked Rooms & Maintenance
          </button>
        </div>

        {activeTab === "blocks" ? (
          <BlockedRoomsView mode="admin" />
        ) : (
          <>
            {/* Filter Toolbar */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <Input
              placeholder="Search room name..."
              icon={<Search className="w-4 h-4" />}
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
            <Select
              options={[
                { value: "", label: "All Blocks" },
                ...blocks.map((b) => ({ value: String(b.id), label: b.name })),
              ]}
              value={blockFilter}
              onChange={(e) => {
                setBlockFilter(e.target.value);
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
                { value: "", label: "All Room Types" },
                { value: "CLASSROOM", label: "Classrooms" },
                { value: "LAB", label: "Laboratories" },
                { value: "EXAM_HALL", label: "Exam Halls" },
                { value: "SEMINAR_HALL", label: "Seminar Halls" },
              ]}
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value);
                setPage(1);
              }}
            />
            <Select
              options={[
                { value: "", label: "All Statuses" },
                { value: "ACTIVE", label: "Active Only" },
                { value: "MAINTENANCE", label: "Under Maintenance" },
              ]}
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
            />
          </div>
        </div>

        {/* Rooms Table */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-[var(--foreground)]">
              <thead className="border-b border-[var(--border)] bg-slate-50/75 dark:bg-slate-900/40 text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Room</th>
                  <th className="px-5 py-3.5">Type</th>
                  <th className="px-5 py-3.5">Location</th>
                  <th className="px-5 py-3.5">Capacity</th>
                  <th className="px-5 py-3.5">Department</th>
                  <th className="px-5 py-3.5">Facilities</th>
                  <th className="px-5 py-3.5">Status (Toggle)</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {loading ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={8} className="px-5 py-4">
                        <div className="h-5 bg-slate-200 dark:bg-slate-800 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))
                ) : rooms.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-8">
                      <EmptyState
                        title="No rooms match your filter criteria"
                        description="Try clearing search filters or add a new room."
                        action={{
                          label: "Reset Filters",
                          onClick: () => {
                            setSearch("");
                            setBlockFilter("");
                            setDeptFilter("");
                            setTypeFilter("");
                            setStatusFilter("");
                            setPage(1);
                          },
                        }}
                      />
                    </td>
                  </tr>
                ) : (
                  rooms.map((room) => {
                    const typeBadge = roomTypeBadges[room.room_type] || roomTypeBadges.CLASSROOM;
                    const isMaint = room.status === "MAINTENANCE";
                    return (
                      <tr key={room.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30 transition-colors">
                        <td className="px-5 py-3.5">
                          <div className="font-bold text-[var(--foreground)]">{room.name}</div>
                        </td>
                        <td className="px-5 py-3.5">
                          <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold border ${typeBadge.color}`}>
                            {typeBadge.label}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-xs">
                          <span className="font-medium text-[var(--foreground)]">{getBlockName(room.block_id)}</span>
                          <span className="text-[var(--muted-foreground)] block">Floor {room.floor}</span>
                        </td>
                        <td className="px-5 py-3.5 text-xs font-semibold">
                          {room.capacity} seats
                        </td>
                        <td className="px-5 py-3.5 text-xs text-[var(--muted-foreground)] font-medium">
                          {getDeptCode(room.department_id)}
                        </td>
                        <td className="px-5 py-3.5">
                          <div className="flex flex-wrap gap-1 max-w-xs">
                            {room.facilities && room.facilities.length > 0 ? (
                              room.facilities.map((f) => (
                                <span
                                  key={f.id}
                                  className="inline-block px-1.5 py-0.5 rounded text-[11px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                                >
                                  {f.name}
                                </span>
                              ))
                            ) : (
                              <span className="text-xs text-[var(--muted-foreground)]">None</span>
                            )}
                          </div>
                        </td>
                        <td className="px-5 py-3.5">
                          <button
                            type="button"
                            onClick={() => openMaintenanceModal(room)}
                            className={`group inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border transition-all ${
                              isMaint
                                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-800 hover:bg-amber-500/20"
                                : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800 hover:bg-emerald-500/20"
                            }`}
                            title="Click to toggle Maintenance state"
                          >
                            {isMaint ? <Wrench className="w-3.5 h-3.5" /> : <CheckCircle className="w-3.5 h-3.5" />}
                            <span>{isMaint ? "Maintenance" : "Active"}</span>
                            <span className="text-[10px] opacity-70 underline font-normal ml-0.5">Toggle</span>
                          </button>
                          {room.maintenance_note && isMaint && (
                            <p className="mt-1 text-[11px] text-amber-600 dark:text-amber-400 italic max-w-xs truncate" title={room.maintenance_note}>
                              Note: {room.maintenance_note}
                            </p>
                          )}
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0"
                              title="Edit room"
                              onClick={() => openEditModal(room)}
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 text-rose-500 hover:text-rose-600"
                              title="Delete room"
                              onClick={() => {
                                setActiveRoom(room);
                                setDeleteConfirmOpen(true);
                              }}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
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

          {/* Pagination */}
          {total > pageSize && (
            <div className="p-4 border-t border-[var(--border)] flex items-center justify-between text-xs text-[var(--muted-foreground)]">
              <span>Showing {rooms.length} of {total} rooms</span>
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
        </>
      )}

        {/* Add Room Modal */}
        <Modal
          isOpen={createModalOpen}
          onClose={() => setCreateModalOpen(false)}
          title="Add New Room"
          description="Provision a lecture hall, laboratory, or exam hall into the campus catalog."
          maxWidth="lg"
        >
          <form onSubmit={handleCreateRoom} className="space-y-4 pt-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Room Identifier / Code *
                </label>
                <Input
                  placeholder="e.g. A-201, CS-LAB-01"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  error={formErrors.name}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Room Category *
                </label>
                <Select
                  options={[
                    { value: "CLASSROOM", label: "Lecture Classroom" },
                    { value: "LAB", label: "Departmental Laboratory" },
                    { value: "EXAM_HALL", label: "Assessment Exam Hall" },
                    { value: "SEMINAR_HALL", label: "Auditorium / Seminar Hall" },
                  ]}
                  value={formData.room_type}
                  onChange={(e) => setFormData({ ...formData, room_type: e.target.value as RoomType })}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Physical Block *
                </label>
                <Select
                  options={[
                    { value: "", label: "Select Block..." },
                    ...blocks.map((b) => ({ value: String(b.id), label: b.name })),
                  ]}
                  value={formData.block_id}
                  onChange={(e) => setFormData({ ...formData, block_id: e.target.value })}
                  error={formErrors.block_id}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Floor Number
                </label>
                <Input
                  type="number"
                  value={formData.floor}
                  onChange={(e) => setFormData({ ...formData, floor: parseInt(e.target.value, 10) || 1 })}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Seat Capacity *
                </label>
                <Input
                  type="number"
                  placeholder="60"
                  value={formData.capacity}
                  onChange={(e) => setFormData({ ...formData, capacity: parseInt(e.target.value, 10) || 0 })}
                  error={formErrors.capacity}
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Department Affiliation {formData.room_type === "LAB" ? "(Required for Labs)" : "(Optional)"}
              </label>
              <Select
                options={[
                  { value: "", label: "General College Venue" },
                  ...departments.map((d) => ({ value: String(d.id), label: `${d.code} - ${d.name}` })),
                ]}
                value={formData.department_id}
                onChange={(e) => setFormData({ ...formData, department_id: e.target.value })}
                error={formErrors.department_id}
              />
            </div>

            {/* Facilities Multi-Select */}
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-2">
                Available Facilities & Amenities
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 p-3 rounded-xl border border-[var(--border)] bg-slate-50/50 dark:bg-slate-900/30 max-h-44 overflow-y-auto">
                {allFacilities.map((f) => {
                  const isChecked = formData.facility_ids.includes(f.id);
                  return (
                    <label key={f.id} className="flex items-center gap-2 text-xs cursor-pointer select-none">
                      <input
                        type="checkbox"
                        className="rounded border-[var(--border)] text-sky-600 focus:ring-sky-500"
                        checked={isChecked}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setFormData({ ...formData, facility_ids: [...formData.facility_ids, f.id] });
                          } else {
                            setFormData({ ...formData, facility_ids: formData.facility_ids.filter((id) => id !== f.id) });
                          }
                        }}
                      />
                      <span className="truncate">{f.name}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="flex justify-end gap-2.5 pt-4 border-t border-[var(--border)]">
              <Button type="button" variant="outline" onClick={() => setCreateModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={submitting} className="bg-sky-600 hover:bg-sky-700 text-white">
                Add Room
              </Button>
            </div>
          </form>
        </Modal>

        {/* Edit Room Modal */}
        <Modal
          isOpen={editModalOpen}
          onClose={() => setEditModalOpen(false)}
          title={`Edit Room: ${activeRoom?.name || ""}`}
          description="Update capacity, room type, block location, or facility amenities."
          maxWidth="lg"
        >
          <form onSubmit={handleEditRoom} className="space-y-4 pt-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Room Identifier *
                </label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  error={formErrors.name}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Room Category *
                </label>
                <Select
                  options={[
                    { value: "CLASSROOM", label: "Lecture Classroom" },
                    { value: "LAB", label: "Departmental Laboratory" },
                    { value: "EXAM_HALL", label: "Assessment Exam Hall" },
                    { value: "SEMINAR_HALL", label: "Auditorium / Seminar Hall" },
                  ]}
                  value={formData.room_type}
                  onChange={(e) => setFormData({ ...formData, room_type: e.target.value as RoomType })}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Block *
                </label>
                <Select
                  options={[
                    { value: "", label: "Select Block..." },
                    ...blocks.map((b) => ({ value: String(b.id), label: b.name })),
                  ]}
                  value={formData.block_id}
                  onChange={(e) => setFormData({ ...formData, block_id: e.target.value })}
                  error={formErrors.block_id}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Floor
                </label>
                <Input
                  type="number"
                  value={formData.floor}
                  onChange={(e) => setFormData({ ...formData, floor: parseInt(e.target.value, 10) || 1 })}
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Capacity *
                </label>
                <Input
                  type="number"
                  value={formData.capacity}
                  onChange={(e) => setFormData({ ...formData, capacity: parseInt(e.target.value, 10) || 0 })}
                  error={formErrors.capacity}
                />
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Department Affiliation {formData.room_type === "LAB" ? "(Required for Labs)" : "(Optional)"}
              </label>
              <Select
                options={[
                  { value: "", label: "General College Venue" },
                  ...departments.map((d) => ({ value: String(d.id), label: `${d.code} - ${d.name}` })),
                ]}
                value={formData.department_id}
                onChange={(e) => setFormData({ ...formData, department_id: e.target.value })}
                error={formErrors.department_id}
              />
            </div>

            {/* Facilities Multi-Select */}
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-2">
                Available Facilities & Amenities
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 p-3 rounded-xl border border-[var(--border)] bg-slate-50/50 dark:bg-slate-900/30 max-h-44 overflow-y-auto">
                {allFacilities.map((f) => {
                  const isChecked = formData.facility_ids.includes(f.id);
                  return (
                    <label key={f.id} className="flex items-center gap-2 text-xs cursor-pointer select-none">
                      <input
                        type="checkbox"
                        className="rounded border-[var(--border)] text-sky-600 focus:ring-sky-500"
                        checked={isChecked}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setFormData({ ...formData, facility_ids: [...formData.facility_ids, f.id] });
                          } else {
                            setFormData({ ...formData, facility_ids: formData.facility_ids.filter((id) => id !== f.id) });
                          }
                        }}
                      />
                      <span className="truncate">{f.name}</span>
                    </label>
                  );
                })}
              </div>
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

        {/* Quick Maintenance Note Modal */}
        <Modal
          isOpen={maintenanceModalOpen}
          onClose={() => setMaintenanceModalOpen(false)}
          title={`Update Status: ${activeRoom?.name || ""}`}
          description={
            maintStatus === "MAINTENANCE"
              ? "Placing this room into maintenance will block all new public and staff bookings."
              : "Mark this room as active to reopen it for allocations and scheduling."
          }
          maxWidth="sm"
        >
          <form onSubmit={handleSaveMaintenance} className="space-y-4 pt-2">
            <div>
              <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                Target Status
              </label>
              <Select
                options={[
                  { value: "ACTIVE", label: "ACTIVE (Online & Bookable)" },
                  { value: "MAINTENANCE", label: "MAINTENANCE (Blocked / Offline)" },
                ]}
                value={maintStatus}
                onChange={(e) => setMaintStatus(e.target.value as RoomStatus)}
              />
            </div>

            {maintStatus === "MAINTENANCE" && (
              <div>
                <label className="text-xs font-semibold text-[var(--foreground)] block mb-1">
                  Maintenance Reason / Note *
                </label>
                <Input
                  placeholder="e.g. AC servicing, Projector bulb replacement"
                  value={maintNote}
                  onChange={(e) => setMaintNote(e.target.value)}
                />
              </div>
            )}

            <div className="flex justify-end gap-2.5 pt-4 border-t border-[var(--border)]">
              <Button type="button" variant="outline" onClick={() => setMaintenanceModalOpen(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                isLoading={submitting}
                className={maintStatus === "MAINTENANCE" ? "bg-amber-600 hover:bg-amber-700 text-white" : "bg-emerald-600 hover:bg-emerald-700 text-white"}
              >
                {maintStatus === "MAINTENANCE" ? "Set Maintenance" : "Restore to Active"}
              </Button>
            </div>
          </form>
        </Modal>

        {/* Bulk CSV Import Modal */}
        <Modal
          isOpen={csvModalOpen}
          onClose={() => setCsvModalOpen(false)}
          title="Bulk Import Rooms via CSV"
          description="Upload a CSV spreadsheet to create or update rooms in bulk."
          maxWidth="lg"
        >
          <div className="space-y-4 pt-2">
            <div className="flex items-center justify-between p-3.5 rounded-xl bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-800 text-xs text-sky-800 dark:text-sky-300">
              <div className="flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-sky-600 shrink-0" />
                <span>Need formatting reference? Download sample spreadsheet template.</span>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-1.5 shrink-0"
                onClick={handleDownloadSample}
              >
                <Download className="w-3.5 h-3.5" />
                Sample Template
              </Button>
            </div>

            <form onSubmit={handleCsvImport} className="space-y-4">
              <div className="border-2 border-dashed border-[var(--border)] rounded-2xl p-6 text-center hover:border-sky-500/50 transition-colors">
                <input
                  type="file"
                  id="csv-file-input"
                  accept=".csv,text/csv"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setCsvFile(f);
                  }}
                />
                <label htmlFor="csv-file-input" className="cursor-pointer block">
                  <Upload className="w-8 h-8 text-[var(--muted-foreground)] mx-auto mb-2" />
                  <span className="text-sm font-semibold text-[var(--foreground)] block">
                    {csvFile ? csvFile.name : "Click to select CSV file"}
                  </span>
                  <span className="text-xs text-[var(--muted-foreground)] mt-1 block">
                    Supported columns: name, block, floor, room_type, capacity, department, facilities
                  </span>
                </label>
              </div>

              {/* Import Results Box */}
              {csvResult && (
                <div className="p-4 rounded-xl border border-[var(--border)] bg-slate-50 dark:bg-slate-900 text-xs space-y-2">
                  <div className="flex items-center justify-between font-semibold">
                    <span>Processed: {csvResult.total_rows} rows</span>
                    <span className="text-emerald-600 dark:text-emerald-400">Successfully Imported: {csvResult.imported}</span>
                  </div>
                  {csvResult.errors.length > 0 && (
                    <div className="pt-2 border-t border-[var(--border)] space-y-1">
                      <span className="text-rose-500 font-bold block">Errors encountered:</span>
                      <div className="max-h-32 overflow-y-auto space-y-1 text-[11px] text-rose-600 dark:text-rose-400">
                        {csvResult.errors.map((err, idx) => (
                          <div key={idx}>Row {err.row}: {err.error}</div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="flex justify-end gap-2.5 pt-2 border-t border-[var(--border)]">
                <Button type="button" variant="outline" onClick={() => setCsvModalOpen(false)}>
                  Close
                </Button>
                <Button
                  type="submit"
                  disabled={!csvFile}
                  isLoading={submitting}
                  className="bg-sky-600 hover:bg-sky-700 text-white"
                >
                  Upload & Import
                </Button>
              </div>
            </form>
          </div>
        </Modal>

        {/* Delete Confirmation Dialog */}
        <ConfirmDialog
          isOpen={deleteConfirmOpen}
          onClose={() => setDeleteConfirmOpen(false)}
          onConfirm={handleDeleteRoom}
          title="Delete Room"
          message={`Are you sure you want to delete ${activeRoom?.name}? This action cannot be reversed.`}
          confirmText="Delete Room"
          variant="danger"
        />
      </div>
    </DashboardShell>
  );
}
