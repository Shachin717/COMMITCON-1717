"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { 
  Building2, 
  Calendar, 
  Clock, 
  Users, 
  Search, 
  Sparkles, 
  CheckCircle2, 
  ShieldCheck, 
  Layers, 
  SlidersHorizontal, 
  ChevronRight, 
  ExternalLink, 
  GraduationCap, 
  MapPin, 
  Monitor, 
  AirVent, 
  Tv, 
  Mic, 
  Volume2, 
  Microscope, 
  AlertCircle, 
  Flame, 
  ArrowRight,
  BookmarkCheck,
  CalendarDays,
  FileText
} from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { Aurora, BlurText, SpotlightCard, CountUp } from "@/components/reactbits";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { showToast } from "@/components/ui/toast";
import { BookingModal } from "@/components/home/booking-modal";
import { WaitlistModal } from "@/components/home/waitlist-modal";
import { ManageBookingSection } from "@/components/home/manage-booking";
import { TimetableSection } from "@/components/home/timetable-section";
import { RoomSearchCard } from "@/components/home/room-search-card";
import { RoomResultsGrid } from "@/components/home/room-results-grid";

// Types
interface TimeSlot {
  id: number;
  label: string;
  start_time: string;
  end_time: string;
  order: number;
}

interface Block {
  id: number;
  name: string;
  description?: string;
}

interface Department {
  id: number;
  name: string;
  code: string;
}

interface Facility {
  id: number;
  name: string;
}

interface AvailableRoom {
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

interface AvailabilityData {
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

interface StatsData {
  total_rooms: number;
  total_blocks: number;
  bookings_today: number;
  departments_count: number;
}

export default function Home() {
  // Format today's date YYYY-MM-DD
  const todayStr = new Date().toISOString().split("T")[0];

  // Metadata from backend
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [slots, setSlots] = useState<TimeSlot[]>([]);
  const [stats, setStats] = useState<StatsData>({
    total_rooms: 40,
    total_blocks: 4,
    bookings_today: 0,
    departments_count: 6,
  });

  // Search filter states
  const [searchDate, setSearchDate] = useState<string>(todayStr);
  const [selectedSlotIds, setSelectedSlotIds] = useState<number[]>([]);
  const [expectedStrength, setExpectedStrength] = useState<number>(45);
  const [selectedRoomType, setSelectedRoomType] = useState<string>("ALL");
  const [selectedBlockId, setSelectedBlockId] = useState<string>("all");
  const [selectedFacilities, setSelectedFacilities] = useState<string[]>([]);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string>("all");

  // Search Results
  const [searchResults, setSearchResults] = useState<AvailabilityData | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  // Booking & Waitlist Modals
  const [bookingModalOpen, setBookingModalOpen] = useState(false);
  const [selectedRoomToBook, setSelectedRoomToBook] = useState<AvailableRoom | null>(null);
  const [selectedSlotToBook, setSelectedSlotToBook] = useState<TimeSlot | null>(null);

  const [waitlistModalOpen, setWaitlistModalOpen] = useState(false);
  const [waitlistRoom, setWaitlistRoom] = useState<any | null>(null);
  const [waitlistSlot, setWaitlistSlot] = useState<any | null>(null);

  // Load metadata & stats on mount
  useEffect(() => {
    async function loadMetaAndStats() {
      try {
        const meta = await apiClient<{
          blocks: Block[];
          departments: Department[];
          facilities: Facility[];
          slots: TimeSlot[];
        }>("/api/public/meta");

        if (meta) {
          setBlocks(meta.blocks || []);
          setDepartments(meta.departments || []);
          setFacilities(meta.facilities || []);
          setSlots(meta.slots || []);
          if (meta.slots && meta.slots.length > 0 && selectedSlotIds.length === 0) {
            setSelectedSlotIds([meta.slots[0].id]);
          }
        }
      } catch (err) {
        console.error("Failed to load metadata", err);
      }

      try {
        const statsRes = await apiClient<StatsData>("/api/public/stats");
        if (statsRes) {
          setStats(statsRes);
        }
      } catch (err) {
        console.error("Failed to load stats", err);
      }
    }

    loadMetaAndStats();
  }, []);

  // Search rooms function
  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchDate) return;

    setIsSearching(true);
    setHasSearched(true);

    try {
      const params: Record<string, any> = {
        date: searchDate,
      };

      if (selectedSlotIds.length > 0) {
        params.slot_ids = selectedSlotIds.join(",");
      }
      if (expectedStrength > 0) {
        params.min_capacity = expectedStrength;
      }
      if (selectedRoomType !== "ALL") {
        params.room_type = selectedRoomType;
      }
      if (selectedBlockId !== "all") {
        params.block_id = Number(selectedBlockId);
      }
      if (selectedFacilities.length > 0) {
        params.facilities = selectedFacilities.join(",");
      }
      if (selectedDepartmentId !== "all") {
        params.department_id = Number(selectedDepartmentId);
      }

      const res = await apiClient<AvailabilityData>("/api/public/availability", {
        params,
      });
      setSearchResults(res);

      // Smooth scroll to results
      setTimeout(() => {
        const el = document.getElementById("search-results-section");
        if (el) el.scrollIntoView({ behavior: "smooth" });
      }, 100);
    } catch (err: any) {
      showToast({
        title: "Search Failed",
        message: err.message || "Failed to search rooms.",
        type: "error",
      });
    } finally {
      setIsSearching(false);
    }
  };

  // Toggle slot selection
  const toggleSlotId = (slotId: number) => {
    setSelectedSlotIds((prev) =>
      prev.includes(slotId)
        ? prev.length > 1
          ? prev.filter((id) => id !== slotId)
          : prev // keep at least one
        : [...prev, slotId]
    );
  };

  // Toggle facility chip
  const toggleFacility = (facName: string) => {
    setSelectedFacilities((prev) =>
      prev.includes(facName)
        ? prev.filter((f) => f !== facName)
        : [...prev, facName]
    );
  };

  // Quick book action from Room card or Timetable
  const handleOpenBooking = (room: any, customSlot?: TimeSlot | null, customDate?: string) => {
    if (!room) return;
    const normalizedRoom = {
      ...room,
      id: Number(room.id ?? room.room_id),
      room_id: Number(room.id ?? room.room_id),
      name: room.name || room.room_name || "Room",
      room_name: room.name || room.room_name || "Room",
    };
    setSelectedRoomToBook(normalizedRoom);
    const targetSlot =
      customSlot ||
      slots.find((s) => s.id === (selectedSlotIds[0] || (slots[0]?.id ?? 1))) ||
      slots[0];
    setSelectedSlotToBook(targetSlot);
    if (customDate) setSearchDate(customDate);
    setBookingModalOpen(true);
  };

  // Open waitlist modal
  const handleOpenWaitlist = (room?: any, slot?: any) => {
    setWaitlistRoom(room || { id: 1, name: "Selected Venue", block_name: "Academic Block" });
    setWaitlistSlot(slot || slots[0]);
    setWaitlistModalOpen(true);
  };

  // Helper facility icon
  const getFacilityIcon = (name: string) => {
    const n = name.toLowerCase();
    if (n.includes("projector")) return <Tv className="w-3.5 h-3.5" />;
    if (n.includes("ac") || n.includes("air")) return <AirVent className="w-3.5 h-3.5" />;
    if (n.includes("pc") || n.includes("computer")) return <Monitor className="w-3.5 h-3.5" />;
    if (n.includes("mic")) return <Mic className="w-3.5 h-3.5" />;
    if (n.includes("sound") || n.includes("speaker")) return <Volume2 className="w-3.5 h-3.5" />;
    if (n.includes("board")) return <SlidersHorizontal className="w-3.5 h-3.5" />;
    if (n.includes("lab")) return <Microscope className="w-3.5 h-3.5" />;
    return <Sparkles className="w-3.5 h-3.5" />;
  };

  return (
    <div className="relative min-h-screen w-full overflow-x-clip bg-[var(--background)] selection:bg-sky-500 selection:text-white">
      {/* Contained Animated Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none select-none" aria-hidden="true">
        <div className="relative w-full h-full overflow-hidden">
          <Aurora className="opacity-30 dark:opacity-40" />
          <div className="absolute inset-0 bg-grid-pattern opacity-50" />

          {/* Floating subtle radial glow blobs */}
          <div className="absolute -top-32 -left-32 w-96 h-96 bg-sky-500/15 dark:bg-sky-500/10 rounded-full blur-3xl animate-pulse-slow" />
          <div className="absolute top-1/3 -right-32 w-96 h-96 bg-indigo-500/15 dark:bg-indigo-500/10 rounded-full blur-3xl animate-pulse-slow" />
          <div className="absolute top-2/3 left-1/4 w-96 h-96 bg-purple-500/10 dark:bg-purple-500/10 rounded-full blur-3xl" />
        </div>
      </div>

      {/* Navigation Header */}
      <header className="sticky top-0 z-40 border-b border-[var(--border)] backdrop-blur-md bg-[var(--background)]/80 transition-colors">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3 group">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-sky-600 via-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-lg shadow-sky-500/25 group-hover:scale-105 transition-transform">
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <span className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-sky-600 via-indigo-600 to-purple-600 dark:from-sky-400 dark:via-indigo-300 dark:to-purple-300 bg-clip-text text-transparent">
                Smart Classroom
              </span>
              <span className="hidden sm:inline-block ml-2 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-sky-100 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300">
                Space Engine
              </span>
            </div>
          </Link>

          {/* Quick Links */}
          <nav className="hidden md:flex items-center gap-6 text-xs font-semibold text-[var(--muted-foreground)]">
            <a href="#search-card" className="hover:text-[var(--foreground)] transition-colors">
              Find Rooms
            </a>
            <a href="#timetable-section" className="hover:text-[var(--foreground)] transition-colors">
              Live Timetable
            </a>
            <a href="#manage-section" className="hover:text-[var(--foreground)] transition-colors">
              Manage Booking
            </a>
            <a href="#how-it-works" className="hover:text-[var(--foreground)] transition-colors">
              How It Works
            </a>
          </nav>

          {/* Portal Buttons & Theme Toggle */}
          <div className="flex items-center gap-2.5">
            <Link
              href="/hod/login"
              className="text-xs font-semibold px-3 py-1.5 rounded-xl border border-[var(--border)] hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors hidden sm:inline-block"
            >
              HOD Portal
            </Link>
            <Link
              href="/staff/login"
              className="text-xs font-semibold px-3 py-1.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white shadow-md shadow-sky-500/20 transition-all hover:scale-[1.02]"
            >
              Staff Portal
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* HERO SECTION */}
      <section className="relative z-10 pt-16 pb-12 sm:pt-20 sm:pb-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="text-center max-w-3xl mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300 text-xs font-bold uppercase tracking-wider mb-6 animate-pulse-slow">
            <Sparkles className="w-3.5 h-3.5 text-sky-500" />
            Autonomous Space Allocation Engine
          </div>

          <h1 className="text-4xl sm:text-6xl font-black tracking-tight mb-6 leading-tight">
            <BlurText
              text="Conflict-Free Campus Space, Automated in Real-Time."
              delay={35}
              animateBy="words"
              direction="bottom"
              className="justify-center"
            />
          </h1>

          <p className="text-base sm:text-lg text-[var(--muted-foreground)] leading-relaxed max-w-2xl mx-auto">
            Book lecture halls, computer labs, seminar auditoriums, and examination venues. Powered by database-level conflict locking, multi-tier approvals, and fit-score optimization.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-3 mt-6 text-xs text-[var(--muted-foreground)]">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              <span>No Student Login Required</span>
            </div>
            <span>•</span>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              <span>Zero Double-Booking Guarantee</span>
            </div>
            <span>•</span>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              <span>Automated Token Cancellation</span>
            </div>
          </div>
        </div>

        {/* FLOATING GLASS SEARCH CARD */}
        <div id="search-card" className="max-w-4xl mx-auto">
          <RoomSearchCard
            searchDate={searchDate}
            onDateChange={setSearchDate}
            selectedSlotIds={selectedSlotIds}
            onToggleSlotId={toggleSlotId}
            slots={slots}
            expectedStrength={expectedStrength}
            onStrengthChange={setExpectedStrength}
            selectedRoomType={selectedRoomType}
            onRoomTypeChange={setSelectedRoomType}
            blocks={blocks}
            selectedBlockId={selectedBlockId}
            onBlockChange={setSelectedBlockId}
            departments={departments}
            selectedDepartmentId={selectedDepartmentId}
            onDepartmentChange={setSelectedDepartmentId}
            facilities={facilities}
            selectedFacilities={selectedFacilities}
            onToggleFacility={toggleFacility}
            onSearch={handleSearch}
            isSearching={isSearching}
          />
        </div>
      </section>

      {/* STATS STRIP SECTION */}
      <section className="py-8 border-y border-[var(--border)] bg-slate-50/50 dark:bg-slate-900/30 backdrop-blur-sm relative z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
            <div className="p-4">
              <div className="text-3xl sm:text-4xl font-black text-sky-600 dark:text-sky-400">
                <CountUp to={stats.total_rooms} duration={1.5} />
              </div>
              <div className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mt-1">
                Active Rooms & Labs
              </div>
            </div>

            <div className="p-4">
              <div className="text-3xl sm:text-4xl font-black text-indigo-600 dark:text-indigo-400">
                <CountUp to={stats.total_blocks} duration={1.5} />
              </div>
              <div className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mt-1">
                Campus Blocks
              </div>
            </div>

            <div className="p-4">
              <div className="text-3xl sm:text-4xl font-black text-purple-600 dark:text-purple-400">
                <CountUp to={stats.bookings_today} duration={1.5} />
              </div>
              <div className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mt-1">
                Bookings Today
              </div>
            </div>

            <div className="p-4">
              <div className="text-3xl sm:text-4xl font-black text-emerald-600 dark:text-emerald-400">
                <CountUp to={stats.departments_count} duration={1.5} />
              </div>
              <div className="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mt-1">
                Academic Departments
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* RESULTS SECTION */}
      {hasSearched && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <RoomResultsGrid
            hasSearched={hasSearched}
            isSearching={isSearching}
            searchDate={searchDate}
            slots={slots}
            selectedSlotIds={selectedSlotIds}
            expectedStrength={expectedStrength}
            searchResults={searchResults}
            onBookRoom={handleOpenBooking}
            onSelectSlot={(slotId) => {
              setSelectedSlotIds([slotId]);
              setTimeout(() => {
                handleSearch();
              }, 50);
            }}
            onJoinWaitlist={handleOpenWaitlist}
          />
        </div>
      )}

      {/* LIVE MASTER TIMETABLE SECTION */}
      <TimetableSection
        initialDate={searchDate}
        blocks={blocks}
        onBookRoomSlot={(room, slot, date) => handleOpenBooking(room, slot, date)}
      />

      {/* MANAGE MY BOOKING SECTION */}
      <ManageBookingSection />

      {/* HOW IT WORKS SECTION */}
      <section id="how-it-works" className="py-20 relative z-10 border-t border-[var(--border)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300 text-xs font-semibold uppercase tracking-wider mb-3">
              <Layers className="w-3.5 h-3.5" />
              Workflow Architecture
            </div>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-[var(--foreground)]">
              How Smart Space Allocation Works
            </h2>
            <p className="text-sm text-[var(--muted-foreground)] mt-2">
              From instant student booking to multi-tier coordinator and HOD sign-offs.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="p-6 rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-sm relative group hover:border-sky-500/50 transition-all">
              <div className="w-10 h-10 rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400 flex items-center justify-center font-black mb-4">
                01
              </div>
              <h3 className="font-bold text-base text-[var(--foreground)] mb-2">
                Search & Filter
              </h3>
              <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                Choose date, period chips, expected headcount, and specific amenities. The fit-score engine ranks suitable venues.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-sm relative group hover:border-indigo-500/50 transition-all">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-black mb-4">
                02
              </div>
              <h3 className="font-bold text-base text-[var(--foreground)] mb-2">
                Public Student Form
              </h3>
              <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                Submit Roll No, Name, and Email without passwords. Instant acknowledgement email dispatched with a secure tracking token.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-sm relative group hover:border-purple-500/50 transition-all">
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400 flex items-center justify-center font-black mb-4">
                03
              </div>
              <h3 className="font-bold text-base text-[var(--foreground)] mb-2">
                Multi-Tier Approval
              </h3>
              <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                Assigned Block Coordinator evaluates the request. If the room is a departmental Lab or Exam Hall, HOD sign-off triggers automatically.
              </p>
            </div>

            <div className="p-6 rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-sm relative group hover:border-emerald-500/50 transition-all">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-black mb-4">
                04
              </div>
              <h3 className="font-bold text-base text-[var(--foreground)] mb-2">
                Lock & Guarantee
              </h3>
              <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                Database-level PostgreSQL exclusion locks guarantee zero double-booking. Students can track or cancel with one click.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="border-t border-[var(--border)] bg-slate-50/70 dark:bg-slate-950/70 backdrop-blur-md py-12 relative z-10 text-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6 pb-8 border-b border-[var(--border)]">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center text-white">
                <Building2 className="h-4 w-4" />
              </div>
              <div>
                <span className="font-bold text-sm tracking-tight text-[var(--foreground)]">
                  Smart Classroom Allocation System
                </span>
                <p className="text-[11px] text-[var(--muted-foreground)]">
                  Automated College Facility Management & Scheduling
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 text-xs font-semibold">
              <Link
                href="/admin/login"
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
              >
                Admin
              </Link>
              <Link
                href="/coordinator/login"
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
              >
                Coordinator
              </Link>
              <Link
                href="/faculty/login"
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
              >
                Faculty
              </Link>
              <Link
                href="/hod/login"
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
              >
                HOD
              </Link>
              <Link
                href="/staff/login"
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors text-sky-600 dark:text-sky-400"
              >
                Staff Chooser
              </Link>
              <a
                href="http://localhost:8000/docs"
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors flex items-center gap-1.5"
              >
                API Docs <ExternalLink className="w-3 h-3 text-[var(--muted-foreground)]" />
              </a>
            </div>
          </div>

          <div className="pt-6 flex flex-col sm:flex-row justify-between items-center gap-4 text-[11px] text-[var(--muted-foreground)]">
            <div>
              © {new Date().getFullYear()} Smart Classroom College System. All rights reserved.
            </div>
            <div>
              Compliant with College Academic Schedules & Examination Protocols.
            </div>
          </div>
        </div>
      </footer>

      {/* BOOKING MODAL */}
      <BookingModal
        isOpen={bookingModalOpen}
        onClose={() => setBookingModalOpen(false)}
        room={selectedRoomToBook}
        date={searchDate}
        slot={selectedSlotToBook}
        departments={departments}
        expectedStrength={expectedStrength}
        onBookingSuccess={(ref) => {
          showToast({
            title: "Booking Requested",
            message: `Reference ${ref} generated. Check your email!`,
            type: "success",
          });
        }}
      />

      {/* WAITLIST MODAL */}
      <WaitlistModal
        isOpen={waitlistModalOpen}
        onClose={() => setWaitlistModalOpen(false)}
        room={waitlistRoom}
        date={searchDate}
        slot={waitlistSlot}
        departments={departments}
      />
    </div>
  );
}
