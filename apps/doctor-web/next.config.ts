import path from "node:path";
import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  agentRules: false, // don't generate AGENTS.md / CLAUDE.md in the app folder
  transpilePackages: ["@carebridge/ui", "@carebridge/i18n", "@carebridge/api-client", "@carebridge/shared-types"],
  turbopack: { root: path.resolve(process.cwd(), "../..") },
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
