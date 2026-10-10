"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Building2,
  LayoutDashboard,
  CalendarDays,
  DoorOpen,
  Users,
  Layers,
  Settings,
  LogOut,
  ChevronRight,
  Menu,
  X,
  User,
  Shield,
  GraduationCap,
  Sparkles,
  BarChart3,
  Sliders,
  History,
  FileText,
  Clock,
  Boxes,
  Bell,
  FlaskConical,
} from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { PageTransition } from "@/components/page-transition";
import { showToast } from "@/components/ui/toast";
import { apiClient } from "@/lib/api-client";

export type Role = "ADMIN" | "COORDINATOR" | "HOD" | "FACULTY";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const ROLE_NAV_ITEMS: Record<Role, NavItem[]> = {
  ADMIN: [
    { label: "Overview", href: "/admin", icon: LayoutDashboard },
    { label: "Allocation Insights", href: "/admin/allocation", icon: Sparkles },
    { label: "Rooms & Catalog", href: "/admin/rooms", icon: DoorOpen },
    { label: "Slots & Timetable", href: "/admin/timetable", icon: Clock },
    { label: "Users & Staff", href: "/admin/users", icon: Users },
    { label: "Departments", href: "/admin/departments", icon: Layers },
    { label: "Blocks", href: "/admin/blocks", icon: Boxes },
    { label: "Booking History", href: "/admin/bookings", icon: History },
    { label: "Audit Logs", href: "/admin/audit-logs", icon: FileText },
  ],
  COORDINATOR: [
    { label: "Pending Inbox", href: "/coordinator", icon: Clock },
    { label: "Allocation Insights", href: "/coordinator/allocation", icon: Sparkles },
    { label: "All-Blocks Status", href: "/coordinator/overview", icon: LayoutDashboard },
    { label: "Block a Room", href: "/coordinator/block-room", icon: Boxes },
    { label: "History", href: "/coordinator/history", icon: History },
    { label: "Timetable Grid", href: "/coordinator/timetable", icon: CalendarDays },
  ],
  HOD: [
    { label: "Overview & Charts", href: "/hod", icon: LayoutDashboard },
    { label: "Pending Approvals", href: "/hod/approvals", icon: Shield },
    { label: "Department Labs", href: "/hod/labs", icon: FlaskConical },
    { label: "Bookings History", href: "/hod/history", icon: History },
  ],
  FACULTY: [
    { label: "Search & Book", href: "/faculty", icon: CalendarDays },
    { label: "My Bookings", href: "/faculty/my-bookings", icon: DoorOpen },
  ],
};

const ROLE_BADGES: Record<
  Role,
  { label: string; color: string; icon: React.ComponentType<{ className?: string }> }
> = {
  ADMIN: {
    label: "Administrator",
    color: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-200 dark:border-rose-900",
    icon: Shield,
  },
  COORDINATOR: {
    label: "Block Coordinator",
    color: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-200 dark:border-sky-900",
    icon: Building2,
  },
  HOD: {
    label: "Department Head",
    color: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-200 dark:border-purple-900",
    icon: GraduationCap,
  },
  FACULTY: {
    label: "Academic Faculty",
    color: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900",
    icon: Sparkles,
  },
};

export interface DashboardShellProps {
  role: Role;
  userEmail?: string;
  userName?: string;
  notificationCount?: number;
  notificationLabel?: string;
  children: React.ReactNode;
}

export function DashboardShell({
  role,
  userEmail = "staff@college.edu",
  userName = "Faculty Member",
  notificationCount = 0,
  notificationLabel = "Pending requests",
  children,
}: DashboardShellProps) {

  const pathname = usePathname();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const [userMenuOpen, setUserMenuOpen] = React.useState(false);

  const navItems = ROLE_NAV_ITEMS[role] || [];
  const badge = ROLE_BADGES[role];
  const BadgeIcon = badge.icon;

  // Active item computation:
  // An item is active if pathname === href, or if pathname starts with href + "/"
  // (the root dashboard link like /hod must only match exactly so it is not always active).
  // Pick the longest matching href when several match.
  const rootHref = `/${role.toLowerCase()}`;
  const matchingItems = navItems.filter((item) => {
    if (item.href === rootHref) {
      return pathname === item.href;
    }
    return pathname === item.href || pathname.startsWith(`${item.href}/`);
  });

  const activeItem =
    matchingItems.length > 0
      ? matchingItems.reduce((longest, curr) =>
          curr.href.length > longest.href.length ? curr : longest
        )
      : null;

  React.useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("unauthorized") === "1") {
        showToast({
          title: "Access Denied",
          message: "You don't have access to that area.",
          type: "error",
        });
        const url = new URL(window.location.href);
        url.searchParams.delete("unauthorized");
        window.history.replaceState({}, "", url.pathname + (url.search ? url.search : ""));
      }
    }
  }, [pathname]);

  const handleLogout = async () => {
    try {
      await apiClient("/api/auth/logout", { method: "POST" });
    } catch {
      // Ignore network errors on logout
    }
    // Delete cookies client-side as well
    document.cookie = "access_token=; path=/; max-age=0";
    document.cookie = "refresh_token=; path=/; max-age=0";
    document.cookie = "user_role=; path=/; max-age=0";

    try {
      localStorage.clear();
      sessionStorage.clear();
    } catch {
      // Ignore client storage errors
    }

    showToast({
      title: "Logged Out",
      message: "You have been logged out successfully.",
      type: "info",
    });

    const targetLogin = `/${role.toLowerCase()}/login`;
    router.push(targetLogin);
  };

  // Build breadcrumb segments
  const pathParts = pathname.split("/").filter(Boolean);
  const breadcrumbs = pathParts.map((part, index) => {
    const href = "/" + pathParts.slice(0, index + 1).join("/");
    const formatted = part.charAt(0).toUpperCase() + part.slice(1);
    return { label: formatted, href, isLast: index === pathParts.length - 1 };
  });

  return (
    <div className="min-h-screen bg-[var(--background)] flex">
      {/* Mobile Sidebar Backdrop */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-[var(--card)] border-r border-[var(--border)] flex flex-col transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand Header */}
        <div className="h-16 flex items-center justify-between px-6 border-b border-[var(--border)]">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-sky-500/20">
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <span className="font-bold text-base tracking-tight text-[var(--foreground)]">
                Smart Classroom
              </span>
            </div>
          </Link>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1.5 rounded-lg text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Role Identity Tag */}
        <div className="px-6 py-4">
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-xs font-semibold ${badge.color}`}
          >
            <BadgeIcon className="w-4 h-4 shrink-0" />
            <span className="truncate">{badge.label}</span>
          </div>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeItem?.href === item.href;

            const isNotificationItem =
              (role === "COORDINATOR" && (item.href === "/coordinator" || item.href.includes("pending"))) ||
              (role === "HOD" && (item.href === "/hod/approvals" || item.href.includes("approvals"))) ||
              (role === "FACULTY" && item.href.includes("my-bookings"));

            const activeBgClass =
              role === "HOD"
                ? "bg-gradient-to-r from-purple-600 to-indigo-600 shadow-md shadow-purple-600/25"
                : "bg-sky-600 shadow-sm shadow-sky-600/20";

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                aria-current={isActive ? "page" : undefined}
                className={`relative flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                  isActive
                    ? "text-white font-semibold"
                    : "text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-slate-100 dark:hover:bg-slate-800/60"
                }`}
              >
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active-indicator"
                    className={`absolute inset-0 rounded-xl ${activeBgClass}`}
                    transition={{ type: "spring", stiffness: 350, damping: 30 }}
                  />
                )}
                <div className="relative z-10 flex items-center gap-3 min-w-0">
                  <Icon className="w-4 h-4 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </div>
                {isNotificationItem && notificationCount > 0 && (
                  <span className="relative z-10 inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-500 text-white animate-pulse shadow-sm">
                    {notificationCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* User Card & Logout Footer */}
        <div className="p-4 border-t border-[var(--border)] bg-slate-50/50 dark:bg-slate-900/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="h-9 w-9 rounded-full bg-sky-500/10 text-sky-600 dark:text-sky-400 flex items-center justify-center font-bold text-xs shrink-0">
                {userName.charAt(0)}
              </div>
              <div className="truncate">
                <p className="text-xs font-semibold text-[var(--foreground)] truncate">
                  {userName}
                </p>
                <p className="text-[11px] text-[var(--muted-foreground)] truncate">
                  {userEmail}
                </p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="p-1.5 rounded-lg text-[var(--muted-foreground)] hover:text-rose-500 hover:bg-rose-500/10 transition-colors"
              title="Logout"
              aria-label="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-64">
        {/* Topbar */}
        <header className="sticky top-0 z-30 h-16 border-b border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-md flex items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-xl text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-slate-100 dark:hover:bg-slate-800"
              aria-label="Open sidebar"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Breadcrumbs */}
            <nav className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
              <Link
                href="/"
                className="hover:text-[var(--foreground)] transition-colors"
              >
                Home
              </Link>
              {breadcrumbs.map((crumb) => (
                <React.Fragment key={crumb.href}>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-400" />
                  {crumb.isLast ? (
                    <span className="font-semibold text-[var(--foreground)]">
                      {crumb.label}
                    </span>
                  ) : (
                    <Link
                      href={crumb.href}
                      className="hover:text-[var(--foreground)] transition-colors"
                    >
                      {crumb.label}
                    </Link>
                  )}
                </React.Fragment>
              ))}
            </nav>
          </div>

          {/* Right Topbar actions */}
          <div className="flex items-center gap-3">
            {/* Real-time Notification Badge */}
            {notificationCount > 0 && (
              <div
                className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-amber-500/10 dark:bg-amber-500/20 border border-amber-500/30 text-amber-700 dark:text-amber-300 text-xs font-semibold shadow-sm"
                title={`${notificationCount} ${notificationLabel}`}
              >
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                </span>
                <Bell className="w-3.5 h-3.5 shrink-0" />
                <span className="hidden sm:inline">
                  {notificationCount} {notificationLabel}
                </span>
                <span className="sm:hidden font-bold">{notificationCount}</span>
              </div>
            )}

            <ThemeToggle />


            {/* User Dropdown */}
            <div className="relative">
              <button
                onClick={() => setUserMenuOpen((prev) => !prev)}
                className="flex items-center gap-2 p-1.5 rounded-xl border border-[var(--border)] bg-[var(--card)] hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                aria-label="User menu"
              >
                <div className="h-7 w-7 rounded-lg bg-sky-500/10 text-sky-600 dark:text-sky-400 flex items-center justify-center font-bold text-xs">
                  {userName.charAt(0)}
                </div>
                <span className="hidden sm:inline text-xs font-semibold text-[var(--foreground)] pr-1">
                  {userName.split(" ")[0]}
                </span>
              </button>

              <AnimatePresence>
                {userMenuOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-30"
                      onClick={() => setUserMenuOpen(false)}
                    />
                    <motion.div
                      initial={{ opacity: 0, y: 8, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 8, scale: 0.95 }}
                      transition={{ duration: 0.15 }}
                      className="absolute right-0 mt-2 w-48 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-1.5 shadow-xl z-40"
                    >
                      <div className="px-3 py-2 border-b border-[var(--border)]">
                        <p className="text-xs font-semibold text-[var(--foreground)]">
                          {userName}
                        </p>
                        <p className="text-[10px] text-[var(--muted-foreground)] truncate">
                          {userEmail}
                        </p>
                      </div>
                      <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-2 px-3 py-2 mt-1 rounded-xl text-xs font-medium text-rose-500 hover:bg-rose-500/10 transition-colors"
                      >
                        <LogOut className="w-3.5 h-3.5" />
                        Log Out
                      </button>
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
            </div>
          </div>
        </header>

        {/* Page Content with Transitions */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8">
          <PageTransition>{children}</PageTransition>
        </main>
      </div>
    </div>
  );
}
