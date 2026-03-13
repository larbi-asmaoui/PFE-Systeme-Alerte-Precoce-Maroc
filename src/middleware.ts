/**
 * Next.js Edge Middleware – lightweight route protection.
 *
 * Checks for the presence of the auth token cookie / localStorage is
 * not available in middleware, so we rely on a simple cookie that
 * the client sets after login. This provides a fast server-side redirect
 * while the real auth validation happens client-side via AuthGuard.
 *
 * We use a lightweight approach: the client stores a non-sensitive
 * "logged_in" cookie flag when tokens exist so middleware can do
 * fast redirects without needing to verify JWT on the edge.
 */

import { NextRequest, NextResponse } from "next/server";

const AUTH_PAGES = ["/login", "/register"];
const PROTECTED_PREFIX = "/"; // Everything except auth pages

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Check the simple auth indicator cookie
  const isLoggedIn =
    request.cookies.get("heat_wave_logged_in")?.value === "true";

  const isAuthPage = AUTH_PAGES.some((p) => pathname.startsWith(p));

  // Redirect logged-in users away from auth pages
  if (isAuthPage && isLoggedIn) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  // Allow all other requests to pass through
  // (Client-side AuthGuard handles the actual token validation)
  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     *  - _next/static (static files)
     *  - _next/image (image optimization files)
     *  - favicon.ico (favicon file)
     *  - public assets
     */
    "/((?!_next/static|_next/image|favicon.ico|assets/).*)",
  ],
};
