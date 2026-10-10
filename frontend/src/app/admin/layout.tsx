import React from "react";
import { requireServerRole } from "@/lib/server-auth";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireServerRole("ADMIN", "/admin/login");
  return <>{children}</>;
}

