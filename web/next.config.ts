import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // small self-contained server for the Docker image
  output: "standalone",
};

export default nextConfig;
