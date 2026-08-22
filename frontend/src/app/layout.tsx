import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { FooterBar, TopBar } from "@/components/TopBar";

/**
 * Geist / Geist Mono (DESIGN §3), self-hosted.
 * NOTE: loaded via next/font/local rather than next/font/google — this Next
 * install's google-font dataset predates Geist's addition ("Unknown font
 * `Geist"` at build time) and deps are outside this change's scope.
 */
const geistSans = localFont({
  src: "./fonts/Geist-Variable.woff2",
  weight: "100 900",
  variable: "--font-sans",
  display: "swap",
});

const geistMono = localFont({
  src: "./fonts/GeistMono-Variable.woff2",
  weight: "100 900",
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AgentAudit — AI-Buy-Readiness Audit",
  description:
    "640 controlled agent trials measure whether AI shopping agents can see, choose, and buy from your catalog.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>
        <TopBar />
        <main className="shell">{children}</main>
        <FooterBar />
      </body>
    </html>
  );
}
