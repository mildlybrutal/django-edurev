import { NextResponse, type NextRequest } from "next/server";

/**
 * Optimistic check only: send visitors without any session cookie straight to /login
 * instead of rendering a portal shell first. It does not validate the token and is not
 * authorization; Django checks every API request.
 */
export function proxy(request: NextRequest) {
  const hasSession = request.cookies.has("pa_access") || request.cookies.has("pa_refresh");
  if (hasSession) return NextResponse.next();
  const url = new URL("/login", request.url);
  url.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/student/:path*", "/faculty/:path*", "/placement/:path*"],
};
