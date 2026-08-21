import type { Metadata } from "next";
import "./globals.css";
import { FooterBar, TopBar } from "@/components/TopBar";

export const metadata: Metadata = {
  title: "AgentAudit — AI-Buy-Readiness Audit",
  description:
    "640 controlled agent trials measure whether AI shopping agents can see, choose, and buy from your catalog.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <TopBar />
        <main className="shell">{children}</main>
        <FooterBar />
      </body>
    </html>
  );
}
