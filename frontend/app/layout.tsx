import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "EditDNA Rank Studio",
  description: "Upload one ranking video. Generate the next one in your style.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-space text-slate-100 antialiased">{children}</body>
    </html>
  );
}
