import React from "react";
import { requireServerRole } from "@/lib/server-auth";

export default async function FacultyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireServerRole("FACULTY", "/faculty/login");
  return <>{children}</>;
}

