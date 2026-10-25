import type { Metadata } from "next";
import Link from "next/link";
import { FileCheck2, ShieldCheck } from "lucide-react";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "DocVerf Officer Console",
  description: "Evidence-linked review and decision support for AICTE applications.",
};

const shell = "mx-auto w-full max-w-[1920px] px-4 sm:px-6 lg:px-8 2xl:px-10";

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen flex-col">
          <header className="sticky top-0 z-40 border-b bg-white/95 backdrop-blur">
            <div className={`flex h-16 items-center justify-between ${shell}`}>
              <Link href="/officer" className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <ShieldCheck className="h-5 w-5" aria-hidden="true" />
                </span>
                <span>
                  <span className="block text-sm font-semibold leading-4 tracking-tight">
                    AICTE DocVerf
                  </span>
                  <span className="block text-xs text-muted-foreground">Officer Console</span>
                </span>
              </Link>
              <nav className="flex items-center gap-1 text-sm">
                <Link
                  href="/officer"
                  className="rounded-md px-3 py-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                >
                  Review queue
                </Link>
                <Link
                  href="/digital-twin"
                  className="rounded-md px-3 py-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                >
                  Digital twin
                </Link>
                <Link
                  href="/portal"
                  className="rounded-md px-3 py-2 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                >
                  Institute portal
                </Link>
                <span className="hidden items-center gap-1.5 rounded-md border px-3 py-2 text-xs text-muted-foreground sm:flex">
                  <FileCheck2 className="h-3.5 w-3.5" aria-hidden="true" />
                  Human review required
                </span>
              </nav>
            </div>
          </header>
          <main className={`${shell} flex-1 py-5 sm:py-6`}>
            {children}
          </main>
          <footer className="border-t bg-white">
            <div
              className={`flex flex-wrap items-center justify-between gap-2 py-4 text-xs text-muted-foreground ${shell}`}
            >
              <span>
                Decision support only. Findings are preliminary indicators until an officer
                reviews the evidence.
              </span>
              <span>No application is approved or rejected automatically.</span>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
