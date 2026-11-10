import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server bundle for the Docker image.
  output: "standalone",
  // Keep the dev-mode overlay badge out of local screenshots/demos.
  devIndicators: false,
};

export default nextConfig;
