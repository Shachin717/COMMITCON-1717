"use client";

import React from "react";
import {
  Search,
  SlidersHorizontal,
  AirVent,
  Tv,
  Monitor,
  Mic,
  Volume2,
  Microscope,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export interface TimeSlot {
  id: number;
  label: string;
  start_time: string;
  end_time: string;
  order: number;
}

export interface Block {
  id: number;
  name: string;
  description?: string | null;
}

export interface Department {
  id: number;
  name: string;
  code: string;
}

export interface Facility {
  id: number;
  name: string;
}

export function getFacilityIcon(name: string) {
  const n = name.toLowerCase();
  if (n.includes("projector")) return <Tv className="w-3.5 h-3.5" />;
  if (n.includes("ac") || n.includes("air")) return <AirVent className="w-3.5 h-3.5" />;
  if (n.includes("pc") || n.includes("computer")) return <Monitor className="w-3.5 h-3.5" />;
  if (n.includes("mic")) return <Mic className="w-3.5 h-3.5" />;
  if (n.includes("sound") || n.includes("speaker")) return <Volume2 className="w-3.5 h-3.5" />;
  if (n.includes("board")) return <SlidersHorizontal className="w-3.5 h-3.5" />;
  if (n.includes("lab")) return <Microscope className="w-3.5 h-3.5" />;
  return <Sparkles className="w-3.5 h-3.5" />;
}

export interface RoomSearchCardProps {
  searchDate: string;
  onDateChange: (date: string) => void;
  selectedSlotIds: number[];
  onToggleSlotId: (slotId: number) => void;
  slots: TimeSlot[];
  expectedStrength: number;
  onStrengthChange: (strength: number) => void;
  selectedRoomType: string;
  onRoomTypeChange: (roomType: string) => void;
  blocks: Block[];
  selectedBlockId: string;
  onBlockChange: (blockId: string) => void;
  departments: Department[];
  selectedDepartmentId: string;
  onDepartmentChange: (deptId: string) => void;
  facilities: Facility[];
  selectedFacilities: string[];
  onToggleFacility: (facilityName: string) => void;
  onSearch: (e?: React.FormEvent) => void;
  isSearching: boolean;
  minDate?: string;
  cardTitle?: string;
  cardSubtitle?: string;
  isFaculty?: boolean;
  submitButtonText?: string;
}

export function RoomSearchCard({
  searchDate,
  onDateChange,
  selectedSlotIds,
  onToggleSlotId,
  slots,
  expectedStrength,
  onStrengthChange,
  selectedRoomType,
  onRoomTypeChange,
  blocks,
  selectedBlockId,
  onBlockChange,
  departments,
  selectedDepartmentId,
  onDepartmentChange,
  facilities,
  selectedFacilities,
  onToggleFacility,
  onSearch,
  isSearching,
  minDate,
  cardTitle = "Find & Book a Classroom",
  cardSubtitle = "Search available lecture halls, departmental labs, and presentation spaces in real-time.",
  isFaculty = false,
  submitButtonText,
}: RoomSearchCardProps) {
  const effectiveSubmitText = submitButtonText || (isFaculty ? "Search Available Rooms" : "Check Real-Time Availability");
  const todayStr = React.useMemo(() => new Date().toISOString().split("T")[0], []);
  const effectiveMinDate = minDate !== undefined ? minDate : todayStr;

  return (
    <div className="glass-card p-6 sm:p-8 shadow-2xl border-[var(--border)] relative overflow-hidden backdrop-blur-2xl rounded-2xl bg-[var(--card)]">
      {/* Top gradient highlight bar */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-500" />

      {cardTitle && (
        <div className="mb-6">
          <h2 className="text-xl font-bold tracking-tight text-[var(--foreground)]">
            {cardTitle}
          </h2>
          {cardSubtitle && (
            <p className="text-xs text-[var(--muted-foreground)] mt-1">
              {cardSubtitle}
            </p>
          )}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSearch(e);
        }}
        className="space-y-6"
      >
        {/* Row 1: Date & Capacity & Room Type */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Date Picker */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--foreground)] mb-1.5">
              Target Date <span className="text-rose-500">*</span>
            </label>
            <input
              type="date"
              required
              min={effectiveMinDate}
              value={searchDate}
              onChange={(e) => onDateChange(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm font-medium focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          {/* Expected Strength */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--foreground)] mb-1.5">
              {isFaculty ? "Expected Class Strength" : "Expected Strength"}
            </label>
            <input
              type="number"
              min={1}
              max={500}
              value={expectedStrength}
              onChange={(e) => onStrengthChange(Math.max(1, Number(e.target.value) || 1))}
              className="w-full px-3.5 py-2.5 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm font-medium focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          {/* Room Type */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--foreground)] mb-1.5">
              Room Category
            </label>
            <select
              value={selectedRoomType}
              onChange={(e) => onRoomTypeChange(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm font-medium focus:outline-none focus:ring-2 focus:ring-sky-500"
            >
              <option value="ALL">All Categories</option>
              <option value="CLASSROOM">Classroom</option>
              <option value="LAB">Laboratory</option>
              <option value="SEMINAR_HALL">Seminar Hall</option>
              <option value="EXAM_HALL">Exam Hall</option>
            </select>
          </div>
        </div>

        {/* Period Selector Chips (Multi-Select) */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--foreground)]">
              Period Slots {isFaculty ? "(Class Periods)" : "(Multi-Select)"}
            </label>
            <span className="text-[11px] text-[var(--muted-foreground)]">
              {selectedSlotIds.length} slot{selectedSlotIds.length !== 1 ? "s" : ""} selected
            </span>
          </div>
          {slots.length === 0 ? (
            <div className="p-3 text-xs text-[var(--muted-foreground)] rounded-xl border border-dashed border-[var(--border)] text-center">
              Loading schedule time periods...
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {slots.map((s, idx) => {
                const isSelected = selectedSlotIds.includes(s.id);
                return (
                  <button
                    type="button"
                    key={s.id}
                    onClick={() => onToggleSlotId(s.id)}
                    className={`px-3 py-2 rounded-xl text-xs font-semibold border transition-all text-left flex flex-col justify-between ${
                      isSelected
                        ? "bg-sky-600 text-white border-sky-600 shadow-md shadow-sky-500/25 ring-2 ring-sky-500/20"
                        : "bg-[var(--background)] text-[var(--foreground)] border-[var(--border)] hover:border-sky-400"
                    }`}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span>Period {idx + 1}</span>
                      {isSelected && <span className="text-[10px] font-bold">✓</span>}
                    </div>
                    <span
                      className={`text-[10px] mt-0.5 ${
                        isSelected ? "text-sky-100" : "text-[var(--muted-foreground)]"
                      }`}
                    >
                      {s.start_time.slice(0, 5)} - {s.end_time.slice(0, 5)}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Row 2: Block & Department filters */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--foreground)] mb-1.5">
              Physical Campus Block
            </label>
            <select
              value={selectedBlockId}
              onChange={(e) => onBlockChange(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm font-medium focus:outline-none focus:ring-2 focus:ring-sky-500"
            >
              <option value="all">Any Campus Block</option>
              {blocks.map((b) => (
                <option key={b.id} value={String(b.id)}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--foreground)] mb-1.5">
              Affiliated Department
            </label>
            <select
              value={selectedDepartmentId}
              onChange={(e) => onDepartmentChange(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl border border-[var(--border)] bg-[var(--background)] text-sm font-medium focus:outline-none focus:ring-2 focus:ring-sky-500"
            >
              <option value="all">Any Department</option>
              {departments.map((d) => (
                <option key={d.id} value={String(d.id)}>
                  {d.name} ({d.code})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Required Facilities Chips */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-[var(--foreground)] mb-2">
            Required Amenities & Equipment
          </label>
          <div className="flex flex-wrap gap-2">
            {facilities.map((fac) => {
              const isSelected = selectedFacilities.includes(fac.name);
              return (
                <button
                  type="button"
                  key={fac.id}
                  onClick={() => onToggleFacility(fac.name)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium border transition-all ${
                    isSelected
                      ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                      : "bg-[var(--background)] text-[var(--foreground)] border-[var(--border)] hover:border-indigo-400"
                  }`}
                >
                  {getFacilityIcon(fac.name)}
                  <span>{fac.name}</span>
                  {isSelected && <span className="text-[10px] ml-0.5">✓</span>}
                </button>
              );
            })}
          </div>
        </div>

        {/* Submit Search Button */}
        <div className="pt-2">
          <Button
            type="submit"
            size="lg"
            className="w-full relative overflow-hidden bg-gradient-to-r from-sky-600 via-indigo-600 to-purple-600 hover:from-sky-500 hover:to-purple-500 text-white font-bold shadow-xl shadow-sky-500/25 group"
            isLoading={isSearching}
          >
            <Search className="w-5 h-5 mr-2" />
            {effectiveSubmitText}
          </Button>
        </div>
      </form>
    </div>
  );
}
