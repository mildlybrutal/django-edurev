import type { NextConfig } from "next";

// Django origin. The browser only ever talks to Next; /api/v1 is proxied so auth cookies stay same-origin.
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  experimental: {
    agentFeedback: true,
  },
  cacheComponents: true,
  partialPrefetching: true,
  // Django URLs end in "/"; don't let Next strip the slash and turn POSTs into redirects.
  skipTrailingSlashRedirect: true,
  async rewrites() {
    // Next drops the trailing slash when matching :path*; every Django API route ends in "/", so add it back.
    return [{ source: "/api/v1/:path*", destination: `${backendUrl}/api/v1/:path*/` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
