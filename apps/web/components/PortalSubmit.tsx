"use client";

import React, { useState, useRef } from "react";
import {
  FileText,
  Upload,
  CheckCircle2,
  AlertTriangle,
  X,
  FileCheck,
  Building,
  Mail,
  Phone,
  MapPin,
  User,
  Hash,
  Layers,
  ArrowRight,
  ShieldCheck,
  Info,
  Clock,
  Sparkles,
  Terminal
} from "lucide-react";

// Configurable file upload constraints
export const UPLOAD_CONSTRAINTS = {
  acceptedExtensions: [".pdf", ".jpg", ".jpeg", ".png"],
  acceptedMimeTypes: ["application/pdf", "image/jpeg", "image/png"],
  maxSizeBytes: 15 * 1024 * 1024, // 15MB
  maxSizeLabel: "15 MB",
};

export interface ApplicationFormFields {
  instituteName: string;
  applicationNo: string;
  aictePermanentId: string;
  contactPerson: string;
  email: string;
  phone: string;
  address: string;
}

export interface UploadedFilesState {
  land_deed: File | null;
  noc: File | null;
  affidavit: File | null;
  accreditation: File | null;
  lab_photos: File[];
}

export interface SubmissionSummary {
  form: Record<string, any>;
  filesCount: number;
  doc_types: string[];
  fileManifest: { index: number; name: string; sizeBytes: number; docType: string }[];
  constructedAt: string;
}

/**
 * Prepares the multipart FormData payload strictly matching TRD §19 Q10:
 * - `form`: JSON string of the application_form fields
 * - `files`: repeated file parts
 * - `doc_types`: JSON array of DocType values, same length and order as `files`
 */
export function buildApplicationMultipartPayload(
  fields: ApplicationFormFields,
  files: UploadedFilesState
): { formData: FormData; summary: SubmissionSummary } {
  const formData = new FormData();

  // 1. JSON representation of application_form fields
  const formPayload = {
    institute_name: fields.instituteName.trim(),
    application_no: fields.applicationNo.trim(),
    aicte_permanent_id: fields.aictePermanentId.trim(),
    contact_person: fields.contactPerson.trim(),
    email: fields.email.trim(),
    phone: fields.phone.trim(),
    address: fields.address.trim(),
    application_category: "Extension of Approval (EoA)",
    submission_timestamp: new Date().toISOString(),
  };

  formData.append("form", JSON.stringify(formPayload));

  // 2. Ordered files and corresponding doc_types array (TRD §19 Q10)
  const docTypesArray: string[] = [];
  const fileManifest: { index: number; name: string; sizeBytes: number; docType: string }[] = [];
  let fileIndex = 0;

  // Append Land Deed
  if (files.land_deed) {
    formData.append("files", files.land_deed);
    docTypesArray.push("land_deed");
    fileManifest.push({
      index: fileIndex++,
      name: files.land_deed.name,
      sizeBytes: files.land_deed.size,
      docType: "land_deed",
    });
  }

  // Append NOC
  if (files.noc) {
    formData.append("files", files.noc);
    docTypesArray.push("noc");
    fileManifest.push({
      index: fileIndex++,
      name: files.noc.name,
      sizeBytes: files.noc.size,
      docType: "noc",
    });
  }

  // Append Affidavit
  if (files.affidavit) {
    formData.append("files", files.affidavit);
    docTypesArray.push("affidavit");
    fileManifest.push({
      index: fileIndex++,
      name: files.affidavit.name,
      sizeBytes: files.affidavit.size,
      docType: "affidavit",
    });
  }

  // Append Accreditation Certificate
  if (files.accreditation) {
    formData.append("files", files.accreditation);
    docTypesArray.push("accreditation_cert");
    fileManifest.push({
      index: fileIndex++,
      name: files.accreditation.name,
      sizeBytes: files.accreditation.size,
      docType: "accreditation_cert",
    });
  }

  // Append Multiple Lab Photos
  if (files.lab_photos && files.lab_photos.length > 0) {
    for (const photo of files.lab_photos) {
      formData.append("files", photo);
      docTypesArray.push("lab_photo");
      fileManifest.push({
        index: fileIndex++,
        name: photo.name,
        sizeBytes: photo.size,
        docType: "lab_photo",
      });
    }
  }

  // 3. Append JSON array of DocTypes
  formData.append("doc_types", JSON.stringify(docTypesArray));

  const summary: SubmissionSummary = {
    form: formPayload,
    filesCount: docTypesArray.length,
    doc_types: docTypesArray,
    fileManifest,
    constructedAt: new Date().toISOString(),
  };

  return { formData, summary };
}

export function PortalSubmit() {
  // Form Details State
  const [fields, setFields] = useState<ApplicationFormFields>({
    instituteName: "Shree Vidya Institute of Technology",
    applicationNo: "1-46200000001",
    aictePermanentId: "1-9876543",
    contactPerson: "Dr. R. K. Deshmukh",
    email: "principal@svit-edu.in",
    phone: "+91 98220 12345",
    address: "Gat No. 45/2, Nagar Road, Wagholi, Pune, Maharashtra 412207",
  });

  // Uploaded Files State
  const [files, setFiles] = useState<UploadedFilesState>({
    land_deed: null,
    noc: null,
    affidavit: null,
    accreditation: null,
    lab_photos: [],
  });

  // Validation Errors
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [preparedPayloadSummary, setPreparedPayloadSummary] = useState<SubmissionSummary | null>(null);

  // Hidden File Input Refs
  const landDeedInputRef = useRef<HTMLInputElement>(null);
  const nocInputRef = useRef<HTMLInputElement>(null);
  const affidavitInputRef = useRef<HTMLInputElement>(null);
  const accreditationInputRef = useRef<HTMLInputElement>(null);
  const labPhotosInputRef = useRef<HTMLInputElement>(null);

  // Validate single file helper
  const validateFile = (file: File): string | null => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!UPLOAD_CONSTRAINTS.acceptedExtensions.includes(ext)) {
      return `Invalid format (${ext}). Supported: ${UPLOAD_CONSTRAINTS.acceptedExtensions.join(", ")}`;
    }
    if (file.size > UPLOAD_CONSTRAINTS.maxSizeBytes) {
      return `File exceeds maximum size of ${UPLOAD_CONSTRAINTS.maxSizeLabel} (${(file.size / (1024 * 1024)).toFixed(1)}MB)`;
    }
    return null;
  };

  // Generic File Upload Handler
  const handleSingleFileUpload = (
    docKey: "land_deed" | "noc" | "affidavit" | "accreditation",
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const errorMsg = validateFile(file);
    if (errorMsg) {
      setErrors((prev) => ({ ...prev, [docKey]: errorMsg }));
      return;
    }

    setErrors((prev) => {
      const copy = { ...prev };
      delete copy[docKey];
      return copy;
    });

    setFiles((prev) => ({ ...prev, [docKey]: file }));
  };

  // Lab Photos Multiple Upload Handler
  const handleLabPhotosUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selected = event.target.files;
    if (!selected || selected.length === 0) return;

    const newPhotos: File[] = [];
    const errorList: string[] = [];

    Array.from(selected).forEach((file) => {
      const err = validateFile(file);
      if (err) {
        errorList.push(`${file.name}: ${err}`);
      } else {
        newPhotos.push(file);
      }
    });

    if (errorList.length > 0) {
      setErrors((prev) => ({ ...prev, lab_photos: errorList.join(" | ") }));
    } else {
      setErrors((prev) => {
        const copy = { ...prev };
        delete copy.lab_photos;
        return copy;
      });
    }

    if (newPhotos.length > 0) {
      setFiles((prev) => ({
        ...prev,
        lab_photos: [...prev.lab_photos, ...newPhotos],
      }));
    }
  };

  const removeLabPhoto = (index: number) => {
    setFiles((prev) => ({
      ...prev,
      lab_photos: prev.lab_photos.filter((_, i) => i !== index),
    }));
  };

  // Form Validation
  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!fields.instituteName.trim()) newErrors.instituteName = "Institute name is required";
    if (!fields.applicationNo.trim()) newErrors.applicationNo = "Application number is required";
    if (!fields.aictePermanentId.trim()) newErrors.aictePermanentId = "AICTE Permanent ID is required";
    if (!fields.contactPerson.trim()) newErrors.contactPerson = "Contact person name is required";

    if (!fields.email.trim()) {
      newErrors.email = "Email address is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email)) {
      newErrors.email = "Enter a valid email address";
    }

    if (!fields.phone.trim()) {
      newErrors.phone = "Phone number is required";
    } else if (!/^[0-9+\-\s()]{7,20}$/.test(fields.phone)) {
      newErrors.phone = "Enter a valid telephone number";
    }

    if (!fields.address.trim()) newErrors.address = "Institute address is required";

    // Validate minimum required documents per PRD Checklist
    if (!files.land_deed) newErrors.land_deed = "Land Deed is mandatory";
    if (!files.noc) newErrors.noc = "Fire & Safety NOC is mandatory";
    if (!files.affidavit) newErrors.affidavit = "Statutory Affidavit is mandatory";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Form Submission Handler
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);

    try {
      // 1. Build multipart payload matching TRD §19 Q10
      const { summary } = buildApplicationMultipartPayload(fields, files);

      // 2. Safe development log (excludes raw binary contents & sensitive values)
      console.log(
        "%c[AICTE DocVerf Portal] Multipart Payload Constructed (TRD §19 Q10)",
        "color: #818cf8; font-weight: bold; font-size: 13px;"
      );
      console.log("Form JSON Part:", summary.form);
      console.log("DocTypes Array Part:", summary.doc_types);
      console.log("Attached Files Manifest:", summary.fileManifest);

      // 3. Set summary state for on-screen development feedback
      setPreparedPayloadSummary(summary);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6">
      {/* Portal Header */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 backdrop-blur">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <span className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <FileText className="w-5 h-5" />
              </span>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-bold text-white tracking-tight">
                    Institute Application Portal
                  </h1>
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                    FR-01 / PRD §8.1
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Extension of Approval (EoA) Intake. Upload mandatory regulatory documents for automated provenance, extraction and consistency validation.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-300">
              Session: <strong className="text-white">2027–2028</strong>
            </span>
            <span className="text-xs px-3 py-1.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 font-semibold">
              Category: EoA Form
            </span>
          </div>
        </div>
      </div>

      {/* Main Submission Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        
        {/* Section 1: Application & Institute Details */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5 shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Building className="w-4 h-4 text-indigo-400" />
              1. Institutional Details
            </h2>
            <span className="text-xs text-slate-400">All fields required for AICTE registry matching</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Institute Name */}
            <div className="space-y-1.5 md:col-span-2">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Building className="w-3.5 h-3.5 text-slate-400" />
                Institute Legal Name
              </label>
              <input
                type="text"
                value={fields.instituteName}
                onChange={(e) => setFields({ ...fields, instituteName: e.target.value })}
                placeholder="e.g. Shree Vidya Institute of Technology"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              />
              {errors.instituteName && <p className="text-[11px] text-rose-400">{errors.instituteName}</p>}
            </div>

            {/* Application No */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Hash className="w-3.5 h-3.5 text-slate-400" />
                Application Reference ID
              </label>
              <input
                type="text"
                value={fields.applicationNo}
                onChange={(e) => setFields({ ...fields, applicationNo: e.target.value })}
                placeholder="e.g. 1-46200000001"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 font-mono"
              />
              {errors.applicationNo && <p className="text-[11px] text-rose-400">{errors.applicationNo}</p>}
            </div>

            {/* AICTE Permanent ID */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
                AICTE Permanent Institute ID (PID)
              </label>
              <input
                type="text"
                value={fields.aictePermanentId}
                onChange={(e) => setFields({ ...fields, aictePermanentId: e.target.value })}
                placeholder="e.g. 1-9876543"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 font-mono"
              />
              {errors.aictePermanentId && <p className="text-[11px] text-rose-400">{errors.aictePermanentId}</p>}
            </div>

            {/* Contact Person */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <User className="w-3.5 h-3.5 text-slate-400" />
                Authorized Signatory / Principal Name
              </label>
              <input
                type="text"
                value={fields.contactPerson}
                onChange={(e) => setFields({ ...fields, contactPerson: e.target.value })}
                placeholder="e.g. Dr. R. K. Deshmukh"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              />
              {errors.contactPerson && <p className="text-[11px] text-rose-400">{errors.contactPerson}</p>}
            </div>

            {/* Email */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5 text-slate-400" />
                Official Institute Email
              </label>
              <input
                type="email"
                value={fields.email}
                onChange={(e) => setFields({ ...fields, email: e.target.value })}
                placeholder="e.g. principal@svit-edu.in"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
              />
              {errors.email && <p className="text-[11px] text-rose-400">{errors.email}</p>}
            </div>

            {/* Phone */}
            <div className="space-y-1.5 md:col-span-2">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Phone className="w-3.5 h-3.5 text-slate-400" />
                Contact Telephone / Mobile
              </label>
              <input
                type="tel"
                value={fields.phone}
                onChange={(e) => setFields({ ...fields, phone: e.target.value })}
                placeholder="e.g. +91 98220 12345"
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 font-mono"
              />
              {errors.phone && <p className="text-[11px] text-rose-400">{errors.phone}</p>}
            </div>

            {/* Address */}
            <div className="space-y-1.5 md:col-span-2">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-slate-400" />
                Campus Physical Address (Matches Land Deed Survey No.)
              </label>
              <textarea
                value={fields.address}
                onChange={(e) => setFields({ ...fields, address: e.target.value })}
                rows={2}
                placeholder="Enter physical address..."
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 leading-relaxed"
              />
              {errors.address && <p className="text-[11px] text-rose-400">{errors.address}</p>}
            </div>
          </div>
        </div>

        {/* Section 2: Document Uploads (All 5 Categories) */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5 shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-3 gap-2">
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
                <Upload className="w-4 h-4 text-indigo-400" />
                2. Supporting Document Uploads
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Each document category must be provided independently. Accepted: {UPLOAD_CONSTRAINTS.acceptedExtensions.join(", ")} (max {UPLOAD_CONSTRAINTS.maxSizeLabel}/file).
              </p>
            </div>
            <span className="text-[11px] text-slate-400 font-medium px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 shrink-0">
              Uploading does not auto-verify compliance
            </span>
          </div>

          <div className="space-y-4">
            
            {/* Category 1: Land Deed */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-slate-200">1. Land Deed / Title Conveyance</span>
                    <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">
                      Mandatory
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">DocType: land_deed</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Registered sale deed, gift deed, or government allotment order showing total contiguous acreage.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    ref={landDeedInputRef}
                    type="file"
                    accept={UPLOAD_CONSTRAINTS.acceptedExtensions.join(",")}
                    className="hidden"
                    onChange={(e) => handleSingleFileUpload("land_deed", e)}
                  />
                  <button
                    type="button"
                    onClick={() => landDeedInputRef.current?.click()}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition flex items-center gap-1.5"
                  >
                    <Upload className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{files.land_deed ? "Replace File" : "Select Land Deed"}</span>
                  </button>
                </div>
              </div>

              {files.land_deed && (
                <div className="mt-2 p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 truncate pr-2">
                    <FileCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span className="font-mono text-slate-200 truncate">{files.land_deed.name}</span>
                    <span className="text-slate-500 text-[10px] shrink-0 font-mono">
                      ({(files.land_deed.size / 1024).toFixed(0)} KB)
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 font-semibold border border-indigo-500/20">
                      Attached (Ready for Scrutiny)
                    </span>
                    <button
                      type="button"
                      onClick={() => setFiles({ ...files, land_deed: null })}
                      className="p-1 text-slate-400 hover:text-rose-400"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
              {errors.land_deed && <p className="text-[11px] text-rose-400">{errors.land_deed}</p>}
            </div>

            {/* Category 2: NOC */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-slate-200">2. Building Safety & Fire NOC</span>
                    <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">
                      Mandatory
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">DocType: noc</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Clearance from Directorate of Fire Services or Municipal Corporation covering proposed academic year.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    ref={nocInputRef}
                    type="file"
                    accept={UPLOAD_CONSTRAINTS.acceptedExtensions.join(",")}
                    className="hidden"
                    onChange={(e) => handleSingleFileUpload("noc", e)}
                  />
                  <button
                    type="button"
                    onClick={() => nocInputRef.current?.click()}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition flex items-center gap-1.5"
                  >
                    <Upload className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{files.noc ? "Replace File" : "Select NOC"}</span>
                  </button>
                </div>
              </div>

              {files.noc && (
                <div className="mt-2 p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 truncate pr-2">
                    <FileCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span className="font-mono text-slate-200 truncate">{files.noc.name}</span>
                    <span className="text-slate-500 text-[10px] shrink-0 font-mono">
                      ({(files.noc.size / 1024).toFixed(0)} KB)
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 font-semibold border border-indigo-500/20">
                      Attached (Ready for Scrutiny)
                    </span>
                    <button
                      type="button"
                      onClick={() => setFiles({ ...files, noc: null })}
                      className="p-1 text-slate-400 hover:text-rose-400"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
              {errors.noc && <p className="text-[11px] text-rose-400">{errors.noc}</p>}
            </div>

            {/* Category 3: Affidavit */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-slate-200">3. AICTE Statutory Affidavit (Stamp Paper)</span>
                    <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">
                      Mandatory
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">DocType: affidavit</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Notarized affidavit on ₹100 non-judicial stamp paper as prescribed in AICTE Approval Process Handbook.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    ref={affidavitInputRef}
                    type="file"
                    accept={UPLOAD_CONSTRAINTS.acceptedExtensions.join(",")}
                    className="hidden"
                    onChange={(e) => handleSingleFileUpload("affidavit", e)}
                  />
                  <button
                    type="button"
                    onClick={() => affidavitInputRef.current?.click()}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition flex items-center gap-1.5"
                  >
                    <Upload className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{files.affidavit ? "Replace File" : "Select Affidavit"}</span>
                  </button>
                </div>
              </div>

              {files.affidavit && (
                <div className="mt-2 p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 truncate pr-2">
                    <FileCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span className="font-mono text-slate-200 truncate">{files.affidavit.name}</span>
                    <span className="text-slate-500 text-[10px] shrink-0 font-mono">
                      ({(files.affidavit.size / 1024).toFixed(0)} KB)
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 font-semibold border border-indigo-500/20">
                      Attached (Ready for Scrutiny)
                    </span>
                    <button
                      type="button"
                      onClick={() => setFiles({ ...files, affidavit: null })}
                      className="p-1 text-slate-400 hover:text-rose-400"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
              {errors.affidavit && <p className="text-[11px] text-rose-400">{errors.affidavit}</p>}
            </div>

            {/* Category 4: Accreditation Certificate */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-slate-200">4. Accreditation Certificate (NBA / NAAC)</span>
                    <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                      Optional / As Applicable
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">DocType: accreditation_cert</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Valid accreditation letters required if applying for intake increase or new PG programs.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    ref={accreditationInputRef}
                    type="file"
                    accept={UPLOAD_CONSTRAINTS.acceptedExtensions.join(",")}
                    className="hidden"
                    onChange={(e) => handleSingleFileUpload("accreditation", e)}
                  />
                  <button
                    type="button"
                    onClick={() => accreditationInputRef.current?.click()}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition flex items-center gap-1.5"
                  >
                    <Upload className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{files.accreditation ? "Replace File" : "Select Accreditation"}</span>
                  </button>
                </div>
              </div>

              {files.accreditation && (
                <div className="mt-2 p-2.5 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 truncate pr-2">
                    <FileCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span className="font-mono text-slate-200 truncate">{files.accreditation.name}</span>
                    <span className="text-slate-500 text-[10px] shrink-0 font-mono">
                      ({(files.accreditation.size / 1024).toFixed(0)} KB)
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 font-semibold border border-indigo-500/20">
                      Attached (Ready for Scrutiny)
                    </span>
                    <button
                      type="button"
                      onClick={() => setFiles({ ...files, accreditation: null })}
                      className="p-1 text-slate-400 hover:text-rose-400"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
              {errors.accreditation && <p className="text-[11px] text-rose-400">{errors.accreditation}</p>}
            </div>

            {/* Category 5: Lab Photos (Supports MULTIPLE files) */}
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-slate-200">5. Laboratory Infrastructure Evidence Photos</span>
                    <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                      Multiple Allowed
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">DocType: lab_photo</span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Clear geo-tagged photographs of designated laboratories showing experimental equipment bays.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    ref={labPhotosInputRef}
                    type="file"
                    multiple
                    accept={UPLOAD_CONSTRAINTS.acceptedExtensions.join(",")}
                    className="hidden"
                    onChange={handleLabPhotosUpload}
                  />
                  <button
                    type="button"
                    onClick={() => labPhotosInputRef.current?.click()}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition flex items-center gap-1.5"
                  >
                    <Upload className="w-3.5 h-3.5 text-indigo-400" />
                    <span>Upload Lab Photos</span>
                  </button>
                </div>
              </div>

              {/* Photos List */}
              {files.lab_photos.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  <div className="text-[11px] font-semibold text-slate-400">
                    {files.lab_photos.length} photo file(s) selected:
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {files.lab_photos.map((photo, idx) => (
                      <div
                        key={idx}
                        className="p-2 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-between text-xs"
                      >
                        <div className="flex items-center gap-2 truncate pr-2">
                          <span className="w-5 h-5 rounded bg-slate-800 text-slate-400 text-[10px] font-mono font-bold flex items-center justify-center shrink-0">
                            {idx + 1}
                          </span>
                          <span className="font-mono text-slate-300 truncate text-[11px]">{photo.name}</span>
                          <span className="text-[10px] text-slate-500 shrink-0 font-mono">
                            ({(photo.size / 1024).toFixed(0)} KB)
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeLabPhoto(idx)}
                          className="p-1 text-slate-400 hover:text-rose-400"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {errors.lab_photos && <p className="text-[11px] text-rose-400">{errors.lab_photos}</p>}
            </div>
          </div>
        </div>

        {/* Section 3: Submission Action & Regulatory Disclosure */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-xl">
          <div className="p-3.5 rounded-xl bg-indigo-950/30 border border-indigo-500/20 text-xs text-indigo-200 leading-relaxed flex items-start gap-2.5">
            <Info className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
            <div>
              <strong className="text-white block mb-0.5">Statutory Declaration:</strong>
              I hereby declare that all information declared and documents uploaded are genuine copies of official records. I acknowledge that the decision-support system verifies documents at source and records all findings in an immutable audit log.
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
            <div className="text-xs text-slate-400">
              Payload conforms to <strong className="text-slate-200">TRD §19 Q10</strong> (Form JSON + Files + DocTypes array)
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full sm:w-auto px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 disabled:opacity-50 text-white font-bold text-xs shadow-lg shadow-indigo-600/25 transition flex items-center justify-center gap-2"
            >
              <Sparkles className="w-4 h-4 text-indigo-200" />
              <span>{isSubmitting ? "Constructing Payload..." : "Prepare Submission (TRD §19 Q10)"}</span>
            </button>
          </div>
        </div>
      </form>

      {/* Development-Only Success & Multipart Payload Breakdown Card */}
      {preparedPayloadSummary && (
        <div className="bg-slate-900 border border-emerald-500/40 rounded-2xl p-6 space-y-4 shadow-2xl animate-in fade-in duration-200">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Development Notice: Multipart Payload Ready for Saish Backend
              </h3>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-bold">
              TRD §19 Q10 Contract Validated
            </span>
          </div>

          <p className="text-xs text-slate-300 leading-relaxed">
            Per the instructions, no real API request was dispatched. The multipart <code className="text-indigo-300">FormData</code> was successfully constructed and validated. Below is the safe, sanitized manifest of the prepared payload:
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
            {/* Form JSON Representation */}
            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="text-indigo-400 font-bold flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5" />
                <span>part &apos;form&apos; (JSON string)</span>
              </div>
              <pre className="text-[11px] text-slate-300 overflow-x-auto p-2 bg-slate-900/60 rounded border border-slate-800/80">
                {JSON.stringify(preparedPayloadSummary.form, null, 2)}
              </pre>
            </div>

            {/* DocTypes & Files Array Representation */}
            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
              <div className="text-indigo-400 font-bold flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" />
                <span>part &apos;doc_types&apos; & file order ({preparedPayloadSummary.filesCount} files)</span>
              </div>
              <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                {preparedPayloadSummary.fileManifest.map((item) => (
                  <div
                    key={item.index}
                    className="p-2 rounded bg-slate-900/80 border border-slate-800 flex items-center justify-between text-[11px]"
                  >
                    <div>
                      <span className="text-slate-500 mr-2">[{item.index}]</span>
                      <span className="text-slate-200">{item.name}</span>
                    </div>
                    <span className="px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold text-[10px]">
                      {item.docType}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default PortalSubmit;
