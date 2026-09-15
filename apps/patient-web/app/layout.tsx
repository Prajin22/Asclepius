import type { Metadata, Viewport } from "next";
import { Geist_Mono, Noto_Sans, Noto_Sans_Devanagari, Noto_Sans_Tamil } from "next/font/google";
import type { ReactNode } from "react";
import "./globals.css";
import { Providers } from "./providers";

// One humanist family across three scripts: Latin, Tamil and Devanagari are drawn
// as one system, so a patient's sentence and its English rendering match in weight
// and rhythm. Each script's file loads only when its glyphs appear on screen.
const sans = Noto_Sans({ subsets: ["latin"], variable: "--font-noto-sans", display: "swap" });
const tamil = Noto_Sans_Tamil({ subsets: ["tamil"], variable: "--font-noto-tamil", display: "swap", preload: false });
const devanagari = Noto_Sans_Devanagari({
  subsets: ["devanagari"],
  variable: "--font-noto-devanagari",
  display: "swap",
  preload: false,
});
// Measured values are instrument readings, not prose: monospaced, tabular figures.
// Not preloaded: a phone on mobile data should not pay for Tamil, Devanagari or the
// mono face on a page that renders none of them. Each arrives when its glyphs do.
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap", preload: false });

export const metadata: Metadata = {
  title: { default: "Asclepius", template: "%s · Asclepius" },
  description: "Your health information, organised — in your own words, shared on your terms.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#d83a2e",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // `lang` is updated on the client to the active UI language.
    <html
      lang="en"
      suppressHydrationWarning
      className={`${sans.variable} ${geistMono.variable} ${tamil.variable} ${devanagari.variable}`}
    >
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
