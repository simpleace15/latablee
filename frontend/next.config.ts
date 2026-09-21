import type { NextConfig } from "next";

// NEXT_PUBLIC_BASE_PATH: serve under a subpath (HA ingress proxies at /<slug> later).
// Static export: nginx serves the app; API reached same-origin via nginx proxy.
// Detail views use query params (?id=N) instead of /recipes/[id] — static export
// can't prerender unknown dynamic segments, and the nginx SPA fallback reuses /index.html.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig: NextConfig = {
  output: "export",
  basePath: basePath || undefined,
  assetPrefix: basePath || undefined,
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;