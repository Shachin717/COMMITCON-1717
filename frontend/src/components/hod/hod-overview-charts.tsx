"use client";

import * as React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from "recharts";
import { BarChart3, DoorOpen } from "lucide-react";

interface HodSummaryData {
  bookings_per_day: { day: string; confirmed: number; pending: number }[];
  room_type_usage: { label: string; booking_count: number; room_count: number }[];
}

interface HodOverviewChartsProps {
  summary: HodSummaryData | null;
}

export default function HodOverviewCharts({ summary }: HodOverviewChartsProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Chart 1: 7-Day History */}
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-bold text-[var(--foreground)]">
              Department Activity (Last 7 Days)
            </h2>
            <p className="text-xs text-[var(--muted-foreground)]">
              Trends for bookings submitted by department students or utilizing department rooms.
            </p>
          </div>
          <span className="p-2 rounded-xl bg-purple-500/10 text-purple-600 dark:text-purple-400">
            <BarChart3 className="w-4 h-4" />
          </span>
        </div>

        <div className="h-64 w-full">
          {summary && summary.bookings_per_day.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={summary.bookings_per_day}>
                <defs>
                  <linearGradient id="colorConfirmed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorPending" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.8} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis dataKey="day" stroke="var(--muted-foreground)" fontSize={12} />
                <YAxis stroke="var(--muted-foreground)" fontSize={12} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--card)",
                    borderColor: "var(--border)",
                    borderRadius: "1rem",
                    fontSize: "12px",
                    boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.2)",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "12px" }} />
                <Area
                  type="monotone"
                  dataKey="confirmed"
                  name="Confirmed"
                  stroke="#8b5cf6"
                  fillOpacity={1}
                  fill="url(#colorConfirmed)"
                />
                <Area
                  type="monotone"
                  dataKey="pending"
                  name="Pending"
                  stroke="#f59e0b"
                  fillOpacity={1}
                  fill="url(#colorPending)"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-[var(--muted-foreground)]">
              No weekly booking data recorded.
            </div>
          )}
        </div>
      </div>

      {/* Chart 2: Room Type Distribution & Utilization */}
      <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-bold text-[var(--foreground)]">
              Room Type Demand Breakdown
            </h2>
            <p className="text-xs text-[var(--muted-foreground)]">
              Cumulative volume of bookings and room count per category.
            </p>
          </div>
          <span className="p-2 rounded-xl bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
            <DoorOpen className="w-4 h-4" />
          </span>
        </div>

        <div className="h-64 w-full">
          {summary && summary.room_type_usage.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={summary.room_type_usage}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                <XAxis dataKey="label" stroke="var(--muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--muted-foreground)" fontSize={12} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "var(--card)",
                    borderColor: "var(--border)",
                    borderRadius: "1rem",
                    fontSize: "12px",
                    boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.2)",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "12px" }} />
                <Bar
                  dataKey="booking_count"
                  name="Bookings"
                  fill="#6366f1"
                  radius={[6, 6, 0, 0]}
                />
                <Bar
                  dataKey="room_count"
                  name="Owned Rooms"
                  fill="#ec4899"
                  radius={[6, 6, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-[var(--muted-foreground)]">
              No room usage distribution available.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

