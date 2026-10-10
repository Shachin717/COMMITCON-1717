import React from "react";
import { requireServerRole } from "@/lib/server-auth";

export default async function CoordinatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireServerRole("COORDINATOR", "/coordinator/login");
  return <>{children}</>;
}

