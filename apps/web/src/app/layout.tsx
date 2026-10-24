import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AICTE DocVerf — Officer Review & Decision Support",
  description: "AI-powered application validation, document authentication and regulatory compliance verification for AICTE Extension-of-Approval.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full bg-slate-950 text-slate-100">
      <body className={`${inter.className} min-h-screen flex flex-col bg-slate-950 text-slate-100 antialiased`}>
        {children}
      </body>
    </html>
  );
}
