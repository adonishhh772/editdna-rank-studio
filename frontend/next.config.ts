import type { NextConfig } from "next";

import { buildSecurityHeaders } from "./lib/securityHeaders";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: buildSecurityHeaders(),
      },
    ];
  },
};

export default nextConfig;
