"use client";

import * as React from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  AreaChart,
  Area,
} from "recharts";
import { AdminOverview } from "@/lib/admin-types";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { TrendingUp, Boxes } from "lucide-react";

interface AdminOverviewChartsProps {
  data: AdminOverview | null;
  loading: boolean;
}

export default function AdminOverviewCharts({ data, loading }: AdminOverviewChartsProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Chart 1: 7-Day Trend */}
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-base font-bold text-[var(--foreground)]">
              7-Day Booking Volume Trend
            </h2>
            <p className="text-xs text-[var(--muted-foreground)]">
              Daily requests split by confirmed vs pending approval
            </p>
          </div>
          <div className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-sky-500/10 text-sky-600 dark:text-sky-400">
            <TrendingUp className="w-3.5 h-3.5" />
            7-Day History
          </div>
        </div>

        <div className="h-72 w-full">
          {loading ? (
            <div className="h-full flex items-center justify-center">
              <Skeleton className="h-60 w-full rounded-xl" />
            </div>
          ) : data?.bookings_per_day && data.bookings_per_day.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={data.bookings_per_day}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="colorConfirmed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0.0} />
                  </linearGradient>
                  <linearGradient id="colorPending" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke="currentColor"
                  className="opacity-10"
                />
                <XAxis dataKey="day" tick={{ fill: "currentColor" }} className="text-xs opacity-60" />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "currentColor" }}
                  className="text-xs opacity-60"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--card)",
                    borderColor: "var(--border)",
                    borderRadius: "1rem",
                    boxShadow: "0 10px 15px -3px rgba(0,0,0,0.1)",
                    color: "var(--foreground)",
                  }}
                />
                <Legend wrapperStyle={{ paddingTop: "10px", fontSize: "12px" }} />
                <Area
                  type="monotone"
                  dataKey="confirmed"
                  name="Approved / Confirmed"
                  stroke="#0ea5e9"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorConfirmed)"
                />
                <Area
                  type="monotone"
                  dataKey="pending"
                  name="Pending Review"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorPending)"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState
              title="No booking trend data"
              description="Bookings submitted will be graphed here."
            />
          )}
        </div>
      </div>

      {/* Chart 2: Room Type Usage */}
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-base font-bold text-[var(--foreground)]">
              Room Inventory & Booking Usage
            </h2>
            <p className="text-xs text-[var(--muted-foreground)]">
              Total available rooms vs booking volume by type
            </p>
          </div>
          <div className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <Boxes className="w-3.5 h-3.5" />
            Category Distribution
          </div>
        </div>

        <div className="h-72 w-full">
          {loading ? (
            <div className="h-full flex items-center justify-center">
              <Skeleton className="h-60 w-full rounded-xl" />
            </div>
          ) : data?.room_type_usage && data.room_type_usage.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.room_type_usage}
                margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  vertical={false}
                  stroke="currentColor"
                  className="opacity-10"
                />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "currentColor" }}
                  className="text-xs opacity-60"
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: "currentColor" }}
                  className="text-xs opacity-60"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--card)",
                    borderColor: "var(--border)",
                    borderRadius: "1rem",
                    boxShadow: "0 10px 15px -3px rgba(0,0,0,0.1)",
                    color: "var(--foreground)",
                  }}
                />
                <Legend wrapperStyle={{ paddingTop: "10px", fontSize: "12px" }} />
                <Bar
                  dataKey="room_count"
                  name="Total Rooms"
                  fill="#0ea5e9"
                  radius={[6, 6, 0, 0]}
                />
                <Bar
                  dataKey="booking_count"
                  name="Total Bookings"
                  fill="#6366f1"
                  radius={[6, 6, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState
              title="No category metrics"
              description="Room categories will appear here once configured."
            />
          )}
        </div>
      </div>
    </div>
  );
}

