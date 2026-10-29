"use client";

import React, { useState } from "react";
import floorplanData from "../mock/floorplan.json";
import {
  Building2,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileCheck,
  Camera,
  MapPin,
  ShieldAlert,
  Info,
  Maximize2,
  Layers,
  ArrowRight
} from "lucide-react";

export interface SvgCoords {
  x: number;
  y: number;
  width: number;
  height: number;
  door?: { x: number; y: number; label: string };
}

export interface LinkedPhoto {
  id: string;
  filename: string;
  caption: string;
  timestamp: string;
  dimensions?: string;
  aspectRatio?: string;
}

export interface CertificateRef {
  doc_id: string;
  title: string;
  referenceNumber: string;
  authority: string;
  status: "submitted" | "verified" | "pending_review";
  validUntil: string;
}

export interface ChecklistItem {
  id: string;
  title: string;
  completed: boolean;
  ruleRef?: string;
  notes?: string;
}

export interface RoomData {
  id: string;
  name: string;
  type: string;
  code: string;
  carpetAreaSqm: number;
  capacity: number;
  svg: SvgCoords;
  siteVisitNeeded: boolean;
  siteVisitReason: string | null;
  linkedPhotos: LinkedPhoto[];
  certificates: CertificateRef[];
  checklistItems: ChecklistItem[];
}

export interface FloorplanData {
  instituteId: string;
  instituteName: string;
  campus: string;
  floor: string;
  totalAreaSqm: number;
  lastUpdated: string;
  rooms: RoomData[];
}

export function DigitalTwin() {
  const data: FloorplanData = floorplanData as unknown as FloorplanData;
  const [selectedRoomId, setSelectedRoomId] = useState<string>("room_lab_1");
  const [hoveredRoomId, setHoveredRoomId] = useState<string | null>(null);

  // Active room data lookup
  const selectedRoom = data.rooms.find((r) => r.id === selectedRoomId) || data.rooms[0];

  // Calculate open checks for the selected room dynamically
  const openChecksCount = selectedRoom.checklistItems.filter((item) => !item.completed).length;
  const completedChecksCount = selectedRoom.checklistItems.filter((item) => item.completed).length;

  const handleRoomKeyDown = (e: React.KeyboardEvent, roomId: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setSelectedRoomId(roomId);
    }
  };

  return (
    <div className="w-full max-w-7xl mx-auto space-y-6">
      {/* Component Header */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 backdrop-blur">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <span className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <Building2 className="w-5 h-5" />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-bold text-white tracking-tight">
                    Institute Digital Twin
                  </h1>
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                    Concept preview
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Interactive 2D architectural layout and spatial compliance review. Rooms and submitted evidence can be reviewed document-by-document.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs">
            <div className="bg-slate-950 px-3.5 py-2 rounded-xl border border-slate-800 text-slate-300">
              <span className="text-slate-500 mr-2">Campus Layout:</span>
              <span className="font-semibold text-slate-200">{data.floor}</span>
            </div>
            <div className="bg-slate-950 px-3.5 py-2 rounded-xl border border-slate-800 text-slate-300">
              <span className="text-slate-500 mr-2">PID:</span>
              <span className="font-mono font-semibold text-indigo-400">{data.instituteId}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: SVG Floor Plan (Left) + Room Details Side Panel (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        {/* Left Side: SVG Floor Plan (7 Columns) */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200">
                Floor Plan Schematic (First Floor)
              </h2>
            </div>
            <div className="flex items-center gap-4 text-xs text-slate-400">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-indigo-500/40 border border-indigo-400 inline-block"></span>
                Active Room
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-amber-500/20 border border-amber-500/50 inline-block"></span>
                Site Visit Flag
              </span>
            </div>
          </div>

          {/* SVG Floor Plan Container */}
          <div className="relative w-full aspect-[800/500] bg-slate-950 rounded-xl border border-slate-800/80 p-2 overflow-hidden select-none">
            <svg
              viewBox="0 0 800 500"
              className="w-full h-full"
              role="region"
              aria-label="Institute Floor Plan SVG Schematic"
            >
              <defs>
                {/* Architectural Grid pattern */}
                <pattern id="archGrid" width="20" height="20" patternUnits="userSpaceOnUse">
                  <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1e293b" strokeWidth="0.5" strokeOpacity="0.5" />
                </pattern>
                {/* Diagonal stripe pattern for corridor */}
                <pattern id="corridorPattern" width="16" height="16" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
                  <line x1="0" y1="0" x2="0" y2="16" stroke="#334155" strokeWidth="1" strokeOpacity="0.3" />
                </pattern>
              </defs>

              {/* Background Grid */}
              <rect width="800" height="500" fill="#090d16" />
              <rect width="800" height="500" fill="url(#archGrid)" />

              {/* Exterior Perimeter Walls */}
              <rect
                x="20"
                y="20"
                width="760"
                height="450"
                fill="none"
                stroke="#475569"
                strokeWidth="4"
                rx="6"
              />

              {/* Central Main Corridor */}
              <rect
                x="20"
                y="205"
                width="760"
                height="60"
                fill="url(#corridorPattern)"
                stroke="#334155"
                strokeWidth="2"
              />
              <text
                x="400"
                y="238"
                textAnchor="middle"
                fill="#64748b"
                fontSize="11"
                fontFamily="monospace"
                letterSpacing="3"
                fontWeight="bold"
              >
                CENTRAL CIRCULATION CORRIDOR (CLEAR WIDTH 2.50m)
              </text>

              {/* North & South Wing Room Renderings */}
              {data.rooms.map((room) => {
                const isSelected = room.id === selectedRoomId;
                const isHovered = room.id === hoveredRoomId;
                const { x, y, width, height } = room.svg;
                const roomOpenChecks = room.checklistItems.filter((i) => !i.completed).length;

                // Color tokens for room state
                let fillColor = "#0f172a";
                let strokeColor = "#334155";
                let strokeWidth = 2;

                if (isSelected) {
                  fillColor = "#1e1b4b"; // deep indigo
                  strokeColor = "#818cf8"; // bright indigo-400
                  strokeWidth = 3;
                } else if (isHovered) {
                  fillColor = "#1e293b";
                  strokeColor = "#64748b";
                }

                if (room.siteVisitNeeded) {
                  if (isSelected) {
                    strokeColor = "#f59e0b"; // amber alert
                  }
                }

                return (
                  <g
                    key={room.id}
                    onClick={() => setSelectedRoomId(room.id)}
                    onMouseEnter={() => setHoveredRoomId(room.id)}
                    onMouseLeave={() => setHoveredRoomId(null)}
                    onKeyDown={(e) => handleRoomKeyDown(e, room.id)}
                    tabIndex={0}
                    role="button"
                    aria-label={`Select room ${room.name}, ${room.type}`}
                    aria-pressed={isSelected}
                    className="cursor-pointer transition-all outline-none focus:ring-2 focus:ring-indigo-400 rounded"
                    style={{ outline: isSelected ? "none" : undefined }}
                  >
                    {/* Room Rectangle */}
                    <rect
                      x={x}
                      y={y}
                      width={width}
                      height={height}
                      fill={fillColor}
                      stroke={strokeColor}
                      strokeWidth={strokeWidth}
                      rx="4"
                      className="transition-colors duration-150"
                    />

                    {/* Subtle Internal Boundary / Carpet zone */}
                    <rect
                      x={x + 6}
                      y={y + 6}
                      width={width - 12}
                      height={height - 12}
                      fill="none"
                      stroke={isSelected ? "#4338ca" : "#1e293b"}
                      strokeWidth="1"
                      strokeDasharray="3 3"
                    />

                    {/* Room Tag / Code Badge */}
                    <rect
                      x={x + 12}
                      y={y + 12}
                      width="64"
                      height="20"
                      rx="3"
                      fill={isSelected ? "#312e81" : "#1e293b"}
                      stroke={isSelected ? "#6366f1" : "#334155"}
                      strokeWidth="1"
                    />
                    <text
                      x={x + 44}
                      y={y + 26}
                      textAnchor="middle"
                      fill={isSelected ? "#e0e7ff" : "#94a3b8"}
                      fontSize="10"
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      {room.code}
                    </text>

                    {/* Room Title */}
                    <text
                      x={x + width / 2}
                      y={y + height / 2 - 2}
                      textAnchor="middle"
                      fill={isSelected ? "#ffffff" : "#f1f5f9"}
                      fontSize="14"
                      fontWeight="bold"
                      fontFamily="system-ui, sans-serif"
                    >
                      {room.name}
                    </text>

                    {/* Room Carpet Area & Capacity */}
                    <text
                      x={x + width / 2}
                      y={y + height / 2 + 18}
                      textAnchor="middle"
                      fill={isSelected ? "#c7d2fe" : "#94a3b8"}
                      fontSize="11"
                      fontFamily="monospace"
                    >
                      {room.carpetAreaSqm} m² • Cap: {room.capacity}
                    </text>

                    {/* Open Checks Indicator Pill */}
                    <g transform={`translate(${x + width - 34}, ${y + 12})`}>
                      <circle
                        cx="10"
                        cy="10"
                        r="10"
                        fill={roomOpenChecks > 0 ? "#78350f" : "#064e3b"}
                        stroke={roomOpenChecks > 0 ? "#f59e0b" : "#10b981"}
                        strokeWidth="1.5"
                      />
                      <text
                        x="10"
                        y="14"
                        textAnchor="middle"
                        fill={roomOpenChecks > 0 ? "#fbbf24" : "#34d399"}
                        fontSize="10"
                        fontWeight="bold"
                        fontFamily="monospace"
                      >
                        {roomOpenChecks}
                      </text>
                    </g>

                    {/* Site Visit Warning Indicator on Room Floor */}
                    {room.siteVisitNeeded && (
                      <g transform={`translate(${x + 12}, ${y + height - 26})`}>
                        <rect
                          width="96"
                          height="18"
                          rx="3"
                          fill="#451a03"
                          stroke="#d97706"
                          strokeWidth="1"
                        />
                        <text
                          x="48"
                          y="13"
                          textAnchor="middle"
                          fill="#fcd34d"
                          fontSize="9"
                          fontWeight="bold"
                          letterSpacing="0.5"
                        >
                          SITE VISIT FLAG
                        </text>
                      </g>
                    )}

                    {/* Architectural Door Swing Indicator */}
                    {room.svg.door && (
                      <g transform={`translate(${room.svg.door.x}, ${room.svg.door.y})`}>
                        <line x1="0" y1="0" x2="22" y2="0" stroke="#94a3b8" strokeWidth="2.5" />
                        <path
                          d="M 22 0 A 22 22 0 0 1 0 22"
                          fill="none"
                          stroke="#64748b"
                          strokeWidth="1"
                          strokeDasharray="2 2"
                        />
                        <text
                          x="8"
                          y="-4"
                          fill="#94a3b8"
                          fontSize="8"
                          fontFamily="monospace"
                        >
                          {room.svg.door.label}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })}

              {/* Compass Rose & Scale Bar */}
              <g transform="translate(735, 45)">
                <circle cx="16" cy="16" r="16" fill="#0f172a" stroke="#334155" strokeWidth="1" />
                <path d="M 16 4 L 20 16 L 16 14 L 12 16 Z" fill="#ef4444" />
                <path d="M 16 28 L 20 16 L 16 14 L 12 16 Z" fill="#64748b" />
                <text x="16" y="2" textAnchor="middle" fill="#ef4444" fontSize="9" fontWeight="bold">N</text>
              </g>

              {/* Graphic Scale Bar */}
              <g transform="translate(40, 475)">
                <line x1="0" y1="0" x2="100" y2="0" stroke="#64748b" strokeWidth="2" />
                <line x1="0" y1="-3" x2="0" y2="3" stroke="#64748b" strokeWidth="2" />
                <line x1="50" y1="-3" x2="50" y2="3" stroke="#64748b" strokeWidth="2" />
                <line x1="100" y1="-3" x2="100" y2="3" stroke="#64748b" strokeWidth="2" />
                <text x="0" y="10" fill="#64748b" fontSize="8" fontFamily="monospace">0m</text>
                <text x="50" y="10" fill="#64748b" fontSize="8" fontFamily="monospace">5m</text>
                <text x="100" y="10" fill="#64748b" fontSize="8" fontFamily="monospace">10m</text>
              </g>
            </svg>
          </div>

          {/* Floor Plan Quick Selector Chips */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-xs text-slate-400 mr-1">Select Room:</span>
            {data.rooms.map((r) => {
              const active = r.id === selectedRoomId;
              return (
                <button
                  key={r.id}
                  onClick={() => setSelectedRoomId(r.id)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                    active
                      ? "bg-indigo-600 text-white shadow-sm ring-1 ring-indigo-400"
                      : "bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white"
                  }`}
                >
                  {r.name}
                  {r.siteVisitNeeded && (
                    <span className="ml-1.5 w-1.5 h-1.5 rounded-full bg-amber-400 inline-block"></span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Right Side: Selected Room Details Side Panel (5 Columns) */}
        <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-5 shadow-xl">
          
          {/* Room Header and Type */}
          <div className="space-y-2 border-b border-slate-800 pb-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-indigo-300 font-mono text-xs font-bold border border-slate-700">
                    {selectedRoom.code}
                  </span>
                  <h3 className="text-lg font-bold text-white tracking-tight">
                    {selectedRoom.name}
                  </h3>
                </div>
                <p className="text-xs text-slate-400 mt-1 font-medium">
                  {selectedRoom.type}
                </p>
              </div>

              {/* Site Visit May Be Needed Badge */}
              {selectedRoom.siteVisitNeeded ? (
                <span className="shrink-0 px-2.5 py-1 rounded-full bg-amber-500/15 text-amber-300 border border-amber-500/30 text-xs font-bold flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
                  Site visit may be needed
                </span>
              ) : (
                <span className="shrink-0 px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-xs font-medium flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  Standard Review
                </span>
              )}
            </div>

            {/* Room Basic Spatial Metrics */}
            <div className="grid grid-cols-3 gap-2 pt-2">
              <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 text-center">
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">Carpet Area</div>
                <div className="text-sm font-bold text-slate-200 font-mono">{selectedRoom.carpetAreaSqm} m²</div>
              </div>
              <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 text-center">
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">Batch Capacity</div>
                <div className="text-sm font-bold text-slate-200 font-mono">{selectedRoom.capacity} students</div>
              </div>
              <div className="p-2 rounded-lg bg-slate-950 border border-slate-800 text-center">
                <div className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">Open Checks</div>
                <div className={`text-sm font-bold font-mono ${openChecksCount > 0 ? "text-amber-400" : "text-emerald-400"}`}>
                  {openChecksCount} pending
                </div>
              </div>
            </div>

            {/* Site Visit Justification Alert if needed */}
            {selectedRoom.siteVisitNeeded && selectedRoom.siteVisitReason && (
              <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/25 text-xs text-amber-200 space-y-1">
                <div className="flex items-center gap-1.5 font-bold text-amber-300">
                  <ShieldAlert className="w-4 h-4 text-amber-400" />
                  <span>Physical Inspection Triggers:</span>
                </div>
                <p className="leading-relaxed pl-5 text-slate-300">
                  {selectedRoom.siteVisitReason}
                </p>
              </div>
            )}
          </div>

          {/* Section: Checklist Items with Completion Statuses */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <FileCheck className="w-3.5 h-3.5 text-indigo-400" />
                Spatial Checklist Items ({selectedRoom.checklistItems.length})
              </h4>
              <span className="text-[11px] text-slate-400">
                {completedChecksCount} completed • {openChecksCount} open
              </span>
            </div>

            <div className="space-y-2">
              {selectedRoom.checklistItems.map((chk) => (
                <div
                  key={chk.id}
                  className={`p-3 rounded-xl border text-xs transition ${
                    chk.completed
                      ? "bg-slate-950/60 border-slate-800 text-slate-300"
                      : "bg-amber-950/20 border-amber-500/30 text-amber-200"
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    {chk.completed ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    ) : (
                      <Clock className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                    )}
                    <div className="space-y-1 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <span className={`font-semibold ${chk.completed ? "text-slate-200" : "text-amber-100"}`}>
                          {chk.title}
                        </span>
                        <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${
                          chk.completed
                            ? "bg-emerald-500/10 text-emerald-400"
                            : "bg-amber-500/20 text-amber-300"
                        }`}>
                          {chk.completed ? "Completed" : "Pending Check"}
                        </span>
                      </div>
                      {chk.ruleRef && (
                        <div className="text-[10px] font-mono text-slate-400">
                          Ref: {chk.ruleRef}
                        </div>
                      )}
                      {chk.notes && (
                        <p className="text-[11px] text-slate-400 leading-snug">
                          {chk.notes}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Section: Linked Photos (CRITICAL SAFEGUARDS ENFORCED) */}
          <div className="space-y-2.5 pt-2 border-t border-slate-800">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <Camera className="w-3.5 h-3.5 text-indigo-400" />
                Submitted evidence ({selectedRoom.linkedPhotos.length})
              </h4>
              <span className="text-[10px] text-slate-400">Image Records</span>
            </div>

            {/* Mandatory Regulatory Warning Note */}
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-start gap-2.5 text-xs text-slate-300">
              <Info className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
              <p className="leading-relaxed text-[11px] text-slate-400">
                <strong className="text-slate-200 block mb-0.5 font-semibold">Regulatory Safeguard:</strong>
                Submitted photos are supporting evidence only and do not independently verify dimensions or compliance. Physical measurements are determined solely by approved civil engineering layout drawings or on-site Expert Visit Committee inspections.
              </p>
            </div>

            {/* Linked Photos Gallery */}
            {selectedRoom.linkedPhotos.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {selectedRoom.linkedPhotos.map((photo) => (
                  <div
                    key={photo.id}
                    className="p-3 rounded-xl bg-slate-950 border border-slate-800 hover:border-slate-700 transition space-y-2"
                  >
                    {/* Simulated Camera Evidence Preview Frame */}
                    <div className="w-full aspect-[4/3] rounded-lg bg-slate-900 border border-slate-800/80 flex flex-col items-center justify-center p-3 relative overflow-hidden group">
                      <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 group-hover:text-indigo-400 transition">
                        <Camera className="w-5 h-5" />
                      </div>
                      <span className="text-[10px] font-mono text-slate-400 mt-2 text-center line-clamp-1 px-1">
                        {photo.filename}
                      </span>
                      <div className="absolute top-2 right-2 px-1.5 py-0.5 rounded bg-slate-950/80 text-[9px] font-mono text-slate-400 border border-slate-800">
                        Submitted evidence
                      </div>
                    </div>

                    <div className="space-y-1">
                      <p className="text-[11px] text-slate-300 leading-snug line-clamp-2">
                        {photo.caption}
                      </p>
                      <div className="text-[10px] font-mono text-slate-500">
                        Captured: {photo.timestamp.substring(0, 10)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-center text-xs text-slate-500">
                No photo evidence uploaded for this room.
              </div>
            )}
          </div>

          {/* Section: Certificates & Document References */}
          <div className="space-y-2.5 pt-2 border-t border-slate-800">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <FileCheck className="w-3.5 h-3.5 text-indigo-400" />
              Certificates & Supporting Records ({selectedRoom.certificates.length})
            </h4>

            {selectedRoom.certificates.length > 0 ? (
              <div className="space-y-2">
                {selectedRoom.certificates.map((cert) => (
                  <div
                    key={cert.doc_id}
                    className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-start justify-between gap-3 text-xs"
                  >
                    <div className="space-y-1">
                      <div className="font-semibold text-slate-200">{cert.title}</div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        Ref: {cert.referenceNumber}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Authority: {cert.authority} • Valid: {cert.validUntil}
                      </div>
                    </div>
                    <span className={`shrink-0 text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                      cert.status === "verified"
                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                        : "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                    }`}>
                      {cert.status.replace("_", " ")}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-center text-xs text-slate-500">
                No specific equipment certificates attached to this room.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default DigitalTwin;
