import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Hide the floating dev indicator badge in the corner.
  devIndicators: false,
};

export default nextConfig;
