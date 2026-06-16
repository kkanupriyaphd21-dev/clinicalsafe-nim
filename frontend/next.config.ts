import type { NextConfig } from "next";

const backendUrl = process.env.NIM_BACKEND_URL || "http://localhost:8002";

const nextConfig: NextConfig = {
  turbopack: {
    root: process.cwd(),
  },
  async rewrites() {
    return [
      {
        source: "/api/nim/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
