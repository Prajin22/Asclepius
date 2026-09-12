import path from "node:path";
import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  devIndicators: false, // no Next.js badge over the product, in dev or in a demo
  agentRules: false, // don't generate AGENTS.md / CLAUDE.md in the app folder
  transpilePackages: ["@carebridge/ui", "@carebridge/i18n", "@carebridge/api-client", "@carebridge/shared-types"],
  turbopack: { root: path.resolve(process.cwd(), "../..") },
  // The workspace packages live above this app; hosted builds must trace them too.
  outputFileTracingRoot: path.resolve(process.cwd(), "../.."),
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ];
  },
};

export default config;
