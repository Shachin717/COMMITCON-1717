import { NextResponse, type NextRequest } from "next/server";

export type Role = "ADMIN" | "COORDINATOR" | "HOD" | "FACULTY";

function getRoleDashboard(role: Role): string {
  switch (role) {
    case "ADMIN":
      return "/admin";
    case "COORDINATOR":
      return "/coordinator";
    case "HOD":
      return "/hod";
    case "FACULTY":
      return "/faculty";
    default:
      return "/";
  }
}

async function verifySignedToken(token: string): Promise<Role | null> {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const [headerB64, payloadB64, sigB64] = parts;
    const secret =
      process.env.SECRET_KEY || "change-this-to-a-super-secret-random-key-in-production";

    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(secret),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["verify"]
    );

    const base64Sig = sigB64.replace(/-/g, "+").replace(/_/g, "/");
    const binarySig = atob(base64Sig);
    const bytesSig = new Uint8Array(binarySig.length);
    for (let i = 0; i < binarySig.length; i++) {
      bytesSig[i] = binarySig.charCodeAt(i);
    }

    const dataBytes = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
    const valid = await crypto.subtle.verify("HMAC", key, bytesSig, dataBytes);
    if (!valid) return null;

    const payloadJson = decodeURIComponent(
      atob(payloadB64.replace(/-/g, "+").replace(/_/g, "/"))
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    const payload = JSON.parse(payloadJson);
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      return null;
    }

    if (
      payload.role &&
      ["ADMIN", "COORDINATOR", "HOD", "FACULTY"].includes(payload.role.toUpperCase())
    ) {
      return payload.role.toUpperCase() as Role;
    }
    return null;
  } catch {
    return null;
  }
}

async function getVerifiedRole(request: NextRequest): Promise<Role | null> {
  const accessToken = request.cookies.get("access_token")?.value;
  if (!accessToken) return null;

  // 1. Cryptographically verify signature and token expiration
  const tokenRole = await verifySignedToken(accessToken);
  if (!tokenRole) return null;

  // 2. Query /api/auth/me to re-load active state and role from DB
  try {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 800);
    const res = await fetch(`${apiBase}/api/auth/me`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        Cookie: `access_token=${accessToken}`,
      },
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (res.ok) {
      const data = await res.json();
      if (data && data.is_active && data.role) {
        return data.role.toUpperCase() as Role;
      }
      return null;
    } else if (res.status === 401 || res.status === 403) {
      return null;
    }
  } catch {
    // Backend network timeout/offline: rely on cryptographically verified role
  }

  return tokenRole;
}

const LOGIN_ROUTES = [
  "/admin/login",
  "/coordinator/login",
  "/faculty/login",
  "/hod/login",
  "/staff/login",
];

const PROTECTED_AREAS: { prefix: string; role: Role; loginPage: string }[] = [
  { prefix: "/admin", role: "ADMIN", loginPage: "/admin/login" },
  { prefix: "/coordinator", role: "COORDINATOR", loginPage: "/coordinator/login" },
  { prefix: "/faculty", role: "FACULTY", loginPage: "/faculty/login" },
  { prefix: "/hod", role: "HOD", loginPage: "/hod/login" },
];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const userRole = await getVerifiedRole(request);

  // Expose current pathname to Server Component layouts
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-pathname", pathname);

  // Rule 3: Logged in and opening ANY login page -> redirect to user's own dashboard
  const isLoginPage = LOGIN_ROUTES.includes(pathname);
  if (userRole && isLoginPage) {
    const target = getRoleDashboard(userRole);
    return NextResponse.redirect(new URL(target, request.url));
  }

  // Check role-protected areas
  for (const area of PROTECTED_AREAS) {
    const isAreaRoute = pathname === area.prefix || pathname.startsWith(`${area.prefix}/`);
    const isAreaLogin = pathname === area.loginPage;

    if (isAreaRoute && !isAreaLogin) {
      // Rule 1: Not logged in and opening protected area -> redirect to that area's login page
      if (!userRole) {
        const loginUrl = new URL(area.loginPage, request.url);
        loginUrl.searchParams.set("redirect", pathname);
        return NextResponse.redirect(loginUrl);
      }

      // Rule 2: Logged in with role X and opening area belonging to another role -> redirect to X's dashboard
      if (userRole !== area.role) {
        const userDashboard = getRoleDashboard(userRole);
        const redirectUrl = new URL(userDashboard, request.url);
        redirectUrl.searchParams.set("unauthorized", "1");
        return NextResponse.redirect(redirectUrl);
      }
    }
  }

  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
}

export const config = {
  matcher: [
    "/admin/:path*",
    "/coordinator/:path*",
    "/faculty/:path*",
    "/hod/:path*",
    "/staff/login",
  ],
};
