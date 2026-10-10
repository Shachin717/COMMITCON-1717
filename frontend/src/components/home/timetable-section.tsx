"use client";

import React, { useState, useEffect } from "react";
import { 
  Calendar, 
  Building2, 
  Layers, 
  HelpCircle, 
  Loader2, 
  CheckCircle, 
  Clock, 
  Info,
  ChevronRight
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";

interface TimeSlotSummary {
  id: number;
  label: string;
  start_time: string;
  end_time: string;
  order: number;
}

interface TimetableCell {
  slot_id: number;
  slot_label: string;
  status: "FREE" | "BOOKED" | "CLASS" | "MAINTENANCE" | "EXAM" | string;
  details?: string | null;
}

interface TimetableRoomRow {
  room_id: number;
  room_name: string;
  block_id: number;
  block_name: string;
  floor: number;
  capacity: number;
  room_type: string;
  slots: TimetableCell[];
}

interface TimetableData {
  date: string;
  block_id?: number | null;
  slots: TimeSlotSummary[];
  matrix: TimetableRoomRow[];
}

interface TimetableSectionProps {
  initialDate: string;
  blocks: Array<{ id: number; name: string }>;
  onBookRoomSlot?: (room: any, slot: TimeSlotSummary, date: string) => void;
}

export function TimetableSection({
  initialDate,
  blocks,
  onBookRoomSlot,
}: TimetableSectionProps) {
  const [selectedDate, setSelectedDate] = useState(initialDate);
  const [selectedBlockId, setSelectedBlockId] = useState<string>("all");
  const [roomTypeFilter, setRoomTypeFilter] = useState<string>("all");
  const [timetableData, setTimetableData] = useState<TimetableData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hoveredCell, setHoveredCell] = useState<{
    roomName: string;
    slotLabel: string;
    status: string;
    details?: string | null;
    x: number;
    y: number;
  } | null>(null);

  const fetchTimetable = async (dateStr: string, blockIdVal: string) => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = { date: dateStr };
      if (blockIdVal !== "all") {
        params.block_id = Number(blockIdVal);
      }
      const data = await apiClient<TimetableData>("/api/public/timetable", { params });
      setTimetableData(data);
    } catch (err) {
      console.error("Failed to load timetable", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTimetable(selectedDate, selectedBlockId);
  }, [selectedDate, selectedBlockId]);

  const filteredMatrix = (timetableData?.matrix || []).filter((row) => {
    if (roomTypeFilter === "all") return true;
    return row.room_type.toUpperCase() === roomTypeFilter.toUpperCase();
  });

  const getStatusStyle = (status: string) => {
    switch (status) {
      case "FREE":
        return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/25";
      case "BOOKED":
        return "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30 hover:bg-amber-500/25";
      case "CLASS":
        return "bg-sky-500/15 text-sky-700 dark:text-sky-300 border-sky-500/30 hover:bg-sky-500/25";
      case "MAINTENANCE":
        return "bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/30 hover:bg-rose-500/25";
      case "EXAM":
        return "bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/30 hover:bg-purple-500/25";
      default:
        return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-[var(--border)]";
    }
  };

  return (
    <section id="timetable-section" className="py-16 relative w-full min-w-0">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full min-w-0">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300 text-xs font-semibold uppercase tracking-wider mb-3">
              <Calendar className="w-3.5 h-3.5" />
              Public Timetable & Room Occupancy
            </div>
            <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[var(--foreground)]">
              Daily Master Timetable
            </h2>
            <p className="text-sm text-[var(--muted-foreground)] mt-2">
              Real-time occupancy grid for all rooms and periods. Hover over any cell for details.
            </p>
          </div>

          {/* Timetable Filters */}
          <div className="flex flex-wrap items-center gap-3">
            <div>
              <label className="block text-[11px] font-semibold text-[var(--muted-foreground)] mb-1">
                Date
              </label>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="px-3 py-1.5 rounded-xl border border-[var(--border)] bg-[var(--card)] text-xs font-medium focus:outline-none focus:ring-2 focus:ring-sky-500"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-[var(--muted-foreground)] mb-1">
                Campus Block
              </label>
              <select
                value={selectedBlockId}
                onChange={(e) => setSelectedBlockId(e.target.value)}
                className="px-3 py-1.5 rounded-xl border border-[var(--border)] bg-[var(--card)] text-xs font-medium focus:outline-none focus:ring-2 focus:ring-sky-500"
              >
                <option value="all">All Blocks</option>
                {blocks.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-[var(--muted-foreground)] mb-1">
                Room Category
              </label>
              <select
                value={roomTypeFilter}
                onChange={(e) => setRoomTypeFilter(e.target.value)}
                className="px-3 py-1.5 rounded-xl border border-[var(--border)] bg-[var(--card)] text-xs font-medium focus:outline-none focus:ring-2 focus:ring-sky-500"
              >
                <option value="all">All Categories</option>
                <option value="CLASSROOM">Classrooms</option>
                <option value="LAB">Laboratories</option>
                <option value="SEMINAR_HALL">Seminar Halls</option>
                <option value="EXAM_HALL">Exam Halls</option>
              </select>
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-4 py-3 px-4 rounded-2xl border border-[var(--border)] bg-[var(--card)]/50 backdrop-blur-sm mb-6 text-xs">
          <span className="font-bold text-[var(--foreground)] mr-1">Legend:</span>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" />
            <span className="text-[var(--foreground)]">Free (Available)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-amber-500 inline-block" />
            <span className="text-[var(--foreground)]">Booked</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-sky-500 inline-block" />
            <span className="text-[var(--foreground)]">Academic Class</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-rose-500 inline-block" />
            <span className="text-[var(--foreground)]">Maintenance</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-purple-500 inline-block" />
            <span className="text-[var(--foreground)]">Exam Block</span>
          </div>
        </div>

        {/* Timetable Matrix Grid */}
        <div className="glass-card shadow-xl border-[var(--border)] overflow-hidden w-full min-w-0">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center py-20 text-[var(--muted-foreground)]">
              <Loader2 className="w-8 h-8 animate-spin mb-3 text-sky-600" />
              <span className="text-sm">Loading campus master grid...</span>
            </div>
          ) : !timetableData || filteredMatrix.length === 0 ? (
            <div className="text-center py-16 text-[var(--muted-foreground)]">
              <p className="text-base font-semibold">No rooms found for selected block/category</p>
            </div>
          ) : (
            <div className="overflow-x-auto w-full min-w-0">
              <table className="w-full text-left border-collapse min-w-[800px]">
                <thead>
                  <tr className="border-b border-[var(--border)] bg-slate-50/70 dark:bg-slate-900/70 text-xs">
                    <th className="py-3 px-4 font-bold sticky left-0 z-20 bg-slate-50/90 dark:bg-slate-900/90 backdrop-blur-md min-w-[180px]">
                      Room / Venue
                    </th>
                    {timetableData.slots.map((s, idx) => (
                      <th
                        key={s.id}
                        className="py-3 px-3 font-semibold text-center whitespace-nowrap min-w-[110px]"
                      >
                        <div>Period {idx + 1}</div>
                        <div className="text-[10px] font-normal text-[var(--muted-foreground)]">
                          {s.start_time.slice(0, 5)} - {s.end_time.slice(0, 5)}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)] text-xs">
                  {filteredMatrix.map((row) => (
                    <tr
                      key={row.room_id}
                      className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors"
                    >
                      {/* Sticky Room Label */}
                      <td className="py-3 px-4 font-medium sticky left-0 z-10 bg-[var(--card)] backdrop-blur-md">
                        <div className="font-bold text-[var(--foreground)]">
                          {row.room_name}
                        </div>
                        <div className="text-[10px] text-[var(--muted-foreground)] flex items-center gap-1 mt-0.5">
                          <span>{row.block_name}</span>
                          <span>•</span>
                          <span>{row.capacity} seats</span>
                        </div>
                      </td>

                      {/* Period Cells */}
                      {row.slots.map((cell) => {
                        const isFree = cell.status === "FREE";
                        const slotObj = timetableData.slots.find((s) => s.id === cell.slot_id);

                        return (
                          <td key={cell.slot_id} className="p-2 text-center">
                            <div
                              onClick={() => {
                                if (isFree && onBookRoomSlot && slotObj) {
                                  onBookRoomSlot(row, slotObj, selectedDate);
                                }
                              }}
                              className={`py-2 px-2 rounded-xl border text-[11px] font-semibold transition-all relative group cursor-pointer ${getStatusStyle(
                                cell.status
                              )}`}
                              title={cell.details || cell.status}
                            >
                              <span>{cell.status}</span>
                              {isFree && (
                                <span className="block text-[9px] font-normal opacity-80 mt-0.5">
                                  Click to book
                                </span>
                              )}

                              {/* Hover Tooltip */}
                              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-30 pointer-events-none">
                                <div className="p-2 rounded-lg bg-slate-900 text-white text-[11px] font-medium shadow-xl whitespace-nowrap text-left border border-slate-700">
                                  <div className="font-bold text-sky-300">
                                    {row.room_name} • {cell.slot_label}
                                  </div>
                                  <div className="text-slate-300 mt-0.5">
                                    Status: <strong className="text-white">{cell.status}</strong>
                                  </div>
                                  {cell.details && (
                                    <div className="text-slate-400 text-[10px] mt-0.5 max-w-[200px] whitespace-normal">
                                      {cell.details}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

