import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";

export const metadata: Metadata = {
  title: "Forgetter — Bosch GDPR Data Discovery",
  description: "Local-first PII scanning, mosaic re-identification, Article 17 erasure.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen flex">
        <Sidebar />
        <main className="flex-1 overflow-x-hidden">{children}</main>
      </body>
    </html>
  );
}
