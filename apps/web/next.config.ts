import type { NextConfig } from "next";

const isProd = !!process.env.NEXT_PUBLIC_API_URL;

const nextConfig: NextConfig = {
  // Static export for GitHub Pages — all pages are "use client" so no SSR needed.
  output: "export",

  // GitHub Pages serves project repos at /<repo-name>/.
  // Set NEXT_PUBLIC_BASE_PATH="" to override for custom domains / Vercel.
  basePath: process.env.NEXT_PUBLIC_BASE_PATH ?? "/CIS-PT",

  // Required for static export with next/image.
  images: { unoptimized: true },

  // Trailing slash makes every route a standalone index.html — works better
  // with GitHub Pages path resolution.
  trailingSlash: true,

  // Dev-only proxy: when NEXT_PUBLIC_API_URL is set (prod) the browser calls
  // the Railway API directly; no server-side proxy needed or supported in
  // static export mode.
  ...(!isProd && {
    async rewrites() {
      return [
        {
          source: "/api/:path*",
          destination: "http://localhost:8000/api/:path*",
        },
      ];
    },
  }),
};

export default nextConfig;
