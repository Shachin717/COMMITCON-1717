import React from "react";
import { requireServerRole } from "@/lib/server-auth";

export default async function HodLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireServerRole("HOD", "/hod/login");
  return <>{children}</>;
}

