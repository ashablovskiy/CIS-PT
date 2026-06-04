import type { NextConfig } from "next";

// When NEXT_PUBLIC_API_URL is set (production), the browser calls the API
// directly — no server-side proxy needed, CORS handles it.
//
// When it is NOT set (local dev without .env.local), fall back to the
// Next.js rewrite proxy so the browser never makes cross-origin requests.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

const nextConfig: NextConfig = {
  // Only add the proxy rewrite in dev (when there's no public API URL).
  // In production the frontend calls the Railway API directly via the
  // absolute URL set in NEXT_PUBLIC_API_URL.
  ...(API_URL
    ? {}
    : {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: `http://localhost:8000/api/:path*`,
            },
          ];
        },
      }),
};

export default nextConfig;
