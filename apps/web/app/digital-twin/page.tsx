import React from "react";
import Link from "next/link";
import { DigitalTwin } from "@/components/DigitalTwin";
import { ArrowLeft, Building2 } from "lucide-react";

export const metadata = {
  title: "Institute Digital Twin — AICTE DocVerf",
  description: "Interactive 2D architectural SVG floor plan and spatial evidence review (FR-22).",
};

export default function DigitalTwinPage() {
  return (
    <div className="bg-slate-950 text-slate-100 flex flex-col font-sans">
      <header className="border-b border-slate-800 bg-slate-900/90">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Link
              href="/"
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
              title="Return to Officer Review"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-amber-500 to-indigo-600 flex items-center justify-center font-black text-white text-sm">
              AICTE
            </div>
            <div>
              <span className="font-bold text-sm text-white">DocVerf Digital Twin</span>
              <span className="text-[10px] text-slate-400 ml-2">FR-22 Prototype</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200"
            >
              Officer Scrutiny
            </Link>
            <Link
              href="/portal"
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200"
            >
              Institute Portal
            </Link>
            <span className="px-3 py-1.5 rounded-lg bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 text-xs font-bold">
              Digital Twin
            </span>
          </div>
        </div>
      </header>

      <div className="flex-1 p-4 sm:p-6 lg:p-8">
        <DigitalTwin />
      </div>

      <footer className="border-t border-slate-900 bg-slate-950 py-4 px-4 text-center text-xs text-slate-500">
        AICTE DocVerf Digital Twin Component • FR-22 Infrastructure Verification • Submitted photos are supporting evidence only.
      </footer>
    </div>
  );
}
