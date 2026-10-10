"use client";

import * as React from "react";
import { Suspense } from "react";
import { DashboardShell } from "@/components/layout/dashboard-shell";
import { AllocationInsightsView } from "@/components/allocation/allocation-insights-view";
import { Skeleton } from "@/components/ui/skeleton";

function AdminAllocationLoading() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-10 w-64" />
      <Skeleton className="h-48 w-full rounded-2xl" />
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Skeleton className="h-32 rounded-2xl" />
        <Skeleton className="h-32 rounded-2xl" />
        <Skeleton className="h-32 rounded-2xl" />
        <Skeleton className="h-32 rounded-2xl" />
      </div>
      <Skeleton className="h-96 w-full rounded-2xl" />
    </div>
  );
}

export default function AdminAllocationPage() {
  return (
    <DashboardShell
      role="ADMIN"
      userName="System Admin"
      userEmail="admin@git.edu"
    >
      <Suspense fallback={<AdminAllocationLoading />}>
        <AllocationInsightsView
          role="ADMIN"
          userName="System Admin"
          userEmail="admin@git.edu"
        />
      </Suspense>
    </DashboardShell>
  );
}

