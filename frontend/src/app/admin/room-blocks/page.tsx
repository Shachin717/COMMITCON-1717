"use client";

import * as React from "react";
import { DashboardShell } from "@/components/layout/dashboard-shell";
import { BlockedRoomsView } from "@/components/coordinator/blocked-rooms-view";

export default function AdminRoomBlocksPage() {
  return (
    <DashboardShell
      role="ADMIN"
      userName="System Admin"
      userEmail="admin@git.edu"
    >
      <div className="space-y-6 pb-12">
        <BlockedRoomsView mode="admin" />
      </div>
    </DashboardShell>
  );
}

