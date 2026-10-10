"use client";

import React from "react";
import {
  BookmarkCheck,
  MapPin,
  Sparkles,
  ChevronRight,
  AlertCircle,
  RotateCw,
} from "lucide-react";
import { SpotlightCard } from "@/components/reactbits";
import { Button } from "@/components/ui/button";
import { getFacilityIcon, TimeSlot } from "./room-search-card";

export interface AvailableRoom {
  id: number;
  name: string;
  block_id: number;
  block_name: string;
  floor: number;
  room_type: string;
  capacity: number;
  department_id?: number | null;
  department_name?: string | null;
  facilities: string[];
  fit_score: number;
}

export interface AvailabilityData {
  date: string;
  slot_ids: number[];
  total_available: number;
  available_rooms: AvailableRoom[];
  suggestions?: {
    nearest_free_slots: Array<{
      slot_id: number;
      slot_label: string;
      start_time: string;
      end_time: string;
      available_rooms_count: number;
      rooms: any[];
    }>;
    other_rooms: Array<{
      room_id: number;
      room_name: string;
      block_name: string;
      floor: number;
      capacity: number;
      room_type: string;
      fit_score: number;
      recommendation_reason: string;
    }>;
  };
}

export interface RoomResultsGridProps {
  hasSearched: boolean;
  isSearching: boolean;
  searchDate: string;
  slots: TimeSlot[];
  selectedSlotIds: number[];
  expectedStrength: number;
  searchResults: AvailabilityData | null;
  error?: string | null;
  onRetry?: () => void;
  onBookRoom: (room: AvailableRoom) => void;
  onSelectSlot?: (slotId: number) => void;
  onJoinWaitlist?: (room?: any, slot?: any) => void;
  isFaculty?: boolean;
}

export function RoomResultsGrid({
  hasSearched,
  isSearching,
  searchDate,
  slots,
  selectedSlotIds,
  expectedStrength,
  searchResults,
  error,
  onRetry,
  onBookRoom,
  onSelectSlot,
  onJoinWaitlist,
  isFaculty = false,
}: RoomResultsGridProps) {
  if (!hasSearched && !isSearching) {
    return null;
  }

  return (
    <section id="search-results-section" className="py-8 relative z-10 space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300 text-xs font-semibold uppercase tracking-wider mb-2">
            <BookmarkCheck className="w-3.5 h-3.5" />
            {isFaculty ? "Faculty Allocation Results" : "Live Search Allotments"}
          </div>
          <h3 className="text-2xl sm:text-3xl font-extrabold text-[var(--foreground)]">
            Available Venues for {searchDate}
          </h3>
          <p className="text-xs text-[var(--muted-foreground)] mt-1">
            Ranked by allocation fit score (capacity optimization and facility match)
          </p>
        </div>

        {searchResults && !isSearching && !error && (
          <div className="text-sm font-bold px-3.5 py-1.5 rounded-full bg-slate-100 dark:bg-slate-800 border border-[var(--border)] text-[var(--foreground)] w-fit">
            Found {searchResults.total_available} room{searchResults.total_available !== 1 ? "s" : ""}
          </div>
        )}
      </div>

      {/* Loading state */}
      {isSearching && (
        <div className="glass-card p-12 text-center border-[var(--border)] rounded-2xl bg-[var(--card)]/50 backdrop-blur-md">
          <div className="h-10 w-10 border-3 border-sky-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <h4 className="text-base font-bold text-[var(--foreground)]">
            Checking Live Schedule Grid
          </h4>
          <p className="text-xs text-[var(--muted-foreground)] mt-1 max-w-sm mx-auto">
            Verifying room locks, timetable entries, and existing reservations across all physical blocks...
          </p>
        </div>
      )}

      {/* Error state */}
      {!isSearching && error && (
        <div className="glass-card p-8 text-center border-rose-500/30 bg-rose-500/5 rounded-2xl max-w-2xl mx-auto space-y-4">
          <div className="w-12 h-12 rounded-full bg-rose-100 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 mx-auto flex items-center justify-center">
            <AlertCircle className="w-6 h-6" />
          </div>
          <div>
            <h4 className="text-lg font-bold text-[var(--foreground)]">
              Search Request Failed
            </h4>
            <p className="text-xs text-rose-600 dark:text-rose-400 mt-1 max-w-md mx-auto">
              {error}
            </p>
          </div>
          {onRetry && (
            <Button
              variant="outline"
              size="sm"
              onClick={onRetry}
              className="gap-2 mx-auto"
            >
              <RotateCw className="w-3.5 h-3.5" />
              Try Searching Again
            </Button>
          )}
        </div>
      )}

      {/* Results or Empty State */}
      {!isSearching && !error && searchResults && (
        <>
          {searchResults.available_rooms.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {searchResults.available_rooms.map((room) => {
                const fitPercent = Math.min(Math.round(room.fit_score), 100);
                const capacityPercent = Math.min(
                  Math.round((expectedStrength / room.capacity) * 100),
                  100
                );
                const currentSlot = slots.find((s) => s.id === (selectedSlotIds[0] || 1));

                return (
                  <SpotlightCard
                    key={room.id}
                    className="border-[var(--border)] flex flex-col justify-between rounded-2xl p-5 bg-[var(--card)]"
                    spotlightColor="rgba(56, 189, 248, 0.15)"
                  >
                    <div>
                      {/* Header: Name, Room Type, Fit Score */}
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-[var(--muted-foreground)]">
                            {room.room_type}
                          </span>
                          <h4 className="text-xl font-black text-[var(--foreground)] mt-1">
                            {room.name}
                          </h4>
                          <p className="text-xs text-[var(--muted-foreground)] mt-0.5 flex items-center gap-1">
                            <MapPin className="w-3 h-3 text-sky-500" />
                            {room.block_name} • Floor {room.floor}
                          </p>
                        </div>

                        <div className="text-right">
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-black bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                            <Sparkles className="w-3 h-3" />
                            {fitPercent}% Fit
                          </span>
                        </div>
                      </div>

                      {/* Capacity Progress Bar */}
                      <div className="my-4 p-3 rounded-xl bg-slate-50 dark:bg-slate-900 border border-[var(--border)]">
                        <div className="flex justify-between text-xs font-semibold mb-1.5">
                          <span className="text-[var(--muted-foreground)]">Capacity:</span>
                          <span className="text-[var(--foreground)]">
                            {room.capacity} Seats ({expectedStrength} Expected)
                          </span>
                        </div>
                        <div className="w-full h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-sky-500 to-indigo-500 rounded-full"
                            style={{ width: `${capacityPercent}%` }}
                          />
                        </div>
                      </div>

                      {/* Facilities Badges */}
                      {room.facilities && room.facilities.length > 0 && (
                        <div className="mb-4">
                          <span className="text-[11px] font-semibold text-[var(--muted-foreground)] block mb-1.5">
                            Amenities:
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {room.facilities.map((fac) => (
                              <span
                                key={fac}
                                className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 border border-[var(--border)] text-[var(--foreground)]"
                              >
                                {getFacilityIcon(fac)}
                                <span>{fac}</span>
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Bottom Book Button */}
                    <div className="pt-3 border-t border-[var(--border)] flex items-center justify-between gap-3">
                      <div className="text-[11px] text-[var(--muted-foreground)]">
                        {currentSlot ? currentSlot.label : `Slot ${selectedSlotIds[0] || ""}`}
                      </div>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => onBookRoom(room)}
                        className="px-4 font-bold bg-sky-600 hover:bg-sky-700 text-white"
                      >
                        {isFaculty ? "Book as Faculty" : "Book Room"}
                        <ChevronRight className="w-3.5 h-3.5 ml-1" />
                      </Button>
                    </div>
                  </SpotlightCard>
                );
              })}
            </div>
          ) : (
            /* EMPTY STATE WITH SMART SUGGESTIONS */
            <div className="glass-card p-8 sm:p-12 text-center border-[var(--border)] max-w-3xl mx-auto space-y-8 rounded-2xl bg-[var(--card)]">
              <div className="w-16 h-16 rounded-full bg-amber-100 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 mx-auto flex items-center justify-center">
                <AlertCircle className="w-8 h-8" />
              </div>

              <div>
                <h4 className="text-2xl font-extrabold text-[var(--foreground)]">
                  No Exact Room Match Found
                </h4>
                <p className="text-sm text-[var(--muted-foreground)] mt-2 max-w-md mx-auto">
                  All rooms meeting your specific criteria for {searchDate} are currently allocated, scheduled for class timetables, or under maintenance block.
                </p>
              </div>

              {/* Nearest Free Slots Suggestions */}
              {searchResults?.suggestions?.nearest_free_slots &&
                searchResults.suggestions.nearest_free_slots.length > 0 && (
                  <div className="text-left space-y-3 pt-4 border-t border-[var(--border)]">
                    <h5 className="text-xs font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                      Suggested Alternative Free Periods on {searchDate}
                    </h5>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {searchResults.suggestions.nearest_free_slots.map((sug) => (
                        <div
                          key={sug.slot_id}
                          className="p-3.5 rounded-xl border border-sky-500/20 bg-sky-50/50 dark:bg-sky-950/20 flex items-center justify-between"
                        >
                          <div>
                            <div className="text-xs font-bold text-[var(--foreground)]">
                              {sug.slot_label}
                            </div>
                            <div className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold mt-0.5">
                              {sug.available_rooms_count} rooms available
                            </div>
                          </div>
                          {onSelectSlot && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => onSelectSlot(sug.slot_id)}
                            >
                              Select Slot
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {/* Alternative rooms suggestions */}
              {searchResults?.suggestions?.other_rooms &&
                searchResults.suggestions.other_rooms.length > 0 && (
                  <div className="text-left space-y-3 pt-4 border-t border-[var(--border)]">
                    <h5 className="text-xs font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                      Alternative Rooms in Other Blocks / Sizes
                    </h5>
                    <div className="space-y-2">
                      {searchResults.suggestions.other_rooms.map((alt) => (
                        <div
                          key={alt.room_id}
                          className="p-3.5 rounded-xl border border-[var(--border)] bg-[var(--background)]/60 flex items-center justify-between text-xs"
                        >
                          <div>
                            <strong className="text-[var(--foreground)]">{alt.room_name}</strong>{" "}
                            <span className="text-[var(--muted-foreground)]">
                              ({alt.block_name} • {alt.capacity} seats)
                            </span>
                            <div className="text-[11px] text-[var(--muted-foreground)] mt-0.5">
                              {alt.recommendation_reason}
                            </div>
                          </div>
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() =>
                              onBookRoom({
                                id: alt.room_id,
                                name: alt.room_name,
                                block_id: 0,
                                block_name: alt.block_name,
                                floor: alt.floor,
                                room_type: alt.room_type,
                                capacity: alt.capacity,
                                facilities: [],
                                fit_score: alt.fit_score,
                              })
                            }
                            className="bg-sky-600 hover:bg-sky-700 text-white"
                          >
                            Book This
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {!isFaculty && onJoinWaitlist && (
                <div className="pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onJoinWaitlist()}
                    className="gap-2"
                  >
                    Join Waitlist for this Slot
                  </Button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}

