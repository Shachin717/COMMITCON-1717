import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";

export type Role = "ADMIN" | "COORDINATOR" | "HOD" | "FACULTY";

export async function verifyServerSession(): Promise<{ role: Role; email: string; id: number } | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  if (!token) return null;

  try {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const res = await fetch(`${apiBase}/api/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
        Cookie: `access_token=${token}`,
      },
      cache: "no-store",
    });

    if (res.ok) {
      const data = await res.json();
      if (data && data.is_active && data.role) {
        return {
          role: data.role.toUpperCase() as Role,
          email: data.email,
          id: data.id,
        };
      }
    }
  } catch {
    // If backend is unreachable, decode JWT payload
    try {
      const parts = token.split(".");
      if (parts.length === 3) {
        const payloadJson = decodeURIComponent(
          atob(parts[1].replace(/-/g, "+").replace(/_/g, "/"))
            .split("")
            .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
            .join("")
        );
        const payload = JSON.parse(payloadJson);
        if (payload.exp && payload.exp * 1000 > Date.now() && payload.role) {
          return {
            role: payload.role.toUpperCase() as Role,
            email: payload.email || "",
            id: Number(payload.sub),
          };
        }
      }
    } catch {}
  }
  return null;
}

export async function requireServerRole(expectedRole: Role, loginPath: string) {
  const headerStore = await headers();
  const pathname = headerStore.get("x-pathname") || "";

  // Bypass server role guard on login pages
  if (pathname.endsWith("/login")) {
    return null;
  }

  const session = await verifyServerSession();
  if (!session) {
    redirect(loginPath);
  }
  if (session.role !== expectedRole) {
    redirect("/403");
  }
  return session;
}

