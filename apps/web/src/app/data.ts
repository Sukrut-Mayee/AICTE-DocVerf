export interface Claim {
  doc_id: string;
  doc_name: string;
  entity: string;
  attribute: string;
  value: any;
  authority: "issuer_verified" | "third_party" | "self_declared";
  confidence: number;
  page?: number;
  bbox?: [number, number, number, number];
}

export interface Finding {
  finding_id: string;
  app_id: string;
  type: string;
  severity: "high" | "medium" | "low";
  rule_id: string;
  entity?: string;
  attribute?: string;
  claims: Claim[];
  doc_ids: string[];
  message: string;
  evidence: Record<string, any>;
  status?: "pending" | "confirmed" | "dismissed";
  actionReason?: string;
}

export interface DocumentInfo {
  doc_id: string;
  name: string;
  doc_type: "application_form" | "land_deed" | "noc" | "affidavit" | "accreditation_cert" | "lab_photo";
  overall: "no_issues" | "flagged" | "manual_review_required";
  verification: "verified" | "mismatch_detected" | "expired" | "verification_pending" | "source_unavailable" | "manual_review_required" | null;
  note: string;
  finding_ids: string[];
  fields: Record<string, { value: any; confidence: number; unit?: string; bbox?: [number, number, number, number] }>;
  previewContent?: {
    header: string;
    sections: { label: string; text: string; highlight?: boolean }[];
    stamp?: string;
  };
}

export interface ApplicationCase {
  app_id: string;
  institute_name: string;
  aicte_permanent_id: string;
  application_no: string;
  academic_year: string;
  priority: number;
  status: string;
  documents: DocumentInfo[];
  findings: Finding[];
}

export const CONFLICT_APP: ApplicationCase = {
  app_id: "APP-2027-EOA-0492",
  institute_name: "Shree Vidya Institute of Technology",
  aicte_permanent_id: "1-9876543",
  application_no: "1-46200000001",
  academic_year: "2027-2028",
  priority: 401,
  status: "Under Scrutiny",
  documents: [
    {
      doc_id: "appx_application_form",
      name: "Extension of Approval Form (Form-A)",
      doc_type: "application_form",
      overall: "flagged",
      verification: null,
      note: "Land parcel area conflicts: 2.5 in application_form vs 2.1 in land_deed; Land owner 'Shree Vidya Charitable Society' does not match the trust 'Shree Vidya Education Trust'.",
      finding_ids: ["f_4a9c0181", "f_1214faea", "f_a72a0889"],
      fields: {
        institute_name: { value: "Shree Vidya Institute of Technology", confidence: 1.0 },
        aicte_permanent_id: { value: "1-9876543", confidence: 1.0 },
        application_no: { value: "1-46200000001", confidence: 1.0 },
        trust_name: { value: "Shree Vidya Education Trust", confidence: 1.0 },
        trust_reg_no: { value: "E-12345/PUNE", confidence: 1.0 },
        trust_reg_date: { value: "2009-04-15", confidence: 1.0 },
        land_survey_no: { value: "45/2", confidence: 1.0 },
        land_area: { value: 2.5, unit: "acre", confidence: 1.0, bbox: [0.15, 0.45, 0.35, 0.48] },
        application_date: { value: "2027-01-20", confidence: 1.0 },
        ter_txn_id: { value: "TER2027000123", confidence: 1.0 }
      },
      previewContent: {
        header: "ALL INDIA COUNCIL FOR TECHNICAL EDUCATION - APPLICATION FOR EXTENSION OF APPROVAL",
        sections: [
          { label: "Institution", text: "Shree Vidya Institute of Technology (PID: 1-9876543)" },
          { label: "Sponsoring Trust", text: "Shree Vidya Education Trust (Reg: E-12345/PUNE, Registered: 15-Apr-2009)" },
          { label: "Land Details", text: "Survey No. 45/2, Total Area Declared: 2.50 Acres", highlight: true },
          { label: "TER Fee Ref", text: "TER2027000123 (Verified online)" }
        ],
        stamp: "E-SUBMITTED: 2027-01-20 14:22:10 IST"
      }
    },
    {
      doc_id: "appx_land_deed",
      name: "Registered Sale Deed / Title Deed",
      doc_type: "land_deed",
      overall: "flagged",
      verification: "verified",
      note: "Land parcel area conflicts: 2.5 in application_form vs 2.1 in land_deed; Land owner 'Shree Vidya Charitable Society' does not match the trust 'Shree Vidya Education Trust'.",
      finding_ids: ["f_4a9c0181", "f_1214faea"],
      fields: {
        survey_no: { value: "45/2", confidence: 0.95 },
        area: { value: 2.1, unit: "acre", confidence: 0.93, bbox: [0.12, 0.41, 0.35, 0.44] },
        owner: { value: "Shree Vidya Charitable Society", confidence: 0.91, bbox: [0.12, 0.32, 0.60, 0.36] },
        execution_date: { value: "2010-02-18", confidence: 0.92 }
      },
      previewContent: {
        header: "SUB-REGISTRAR OFFICE, HAVELI TALUKA - DEED OF CONVEYANCE",
        sections: [
          { label: "Purchaser / Owner", text: "Shree Vidya Charitable Society (Society Reg No. MAH/987/PUNE)", highlight: true },
          { label: "Schedule of Property", text: "Plot bearing Gat / Survey No. 45/2, Village Wagholi, Taluka Haveli" },
          { label: "Measurement / Area", text: "Admeasuring 2.10 Acres (8,498.4 sq.m.) clear and unencumbered", highlight: true },
          { label: "Registration Date", text: "18th February 2010; Volume 412, Pages 102-118" }
        ],
        stamp: "SUB-REGISTRAR SEAL & SIGNATURE - VERIFIED AGAINST IGR RECORDS"
      }
    },
    {
      doc_id: "appx_noc",
      name: "Building Safety & Fire NOC",
      doc_type: "noc",
      overall: "flagged",
      verification: "expired",
      note: "NOC expires on 2027-12-31 before the academic year ends (2028-06-30); NOC dated 2008-06-10 is earlier than trust registration 2009-04-15.",
      finding_ids: ["f_164256d5", "f_a72a0889"],
      fields: {
        issue_date: { value: "2008-06-10", confidence: 0.94, bbox: [0.70, 0.15, 0.92, 0.18] },
        valid_until: { value: "2027-12-31", confidence: 0.9, bbox: [0.15, 0.52, 0.45, 0.56] },
        authority: { value: "State Directorate of Fire Services", confidence: 0.95 }
      },
      previewContent: {
        header: "OFFICE OF THE CHIEF FIRE OFFICER - NO OBJECTION CERTIFICATE",
        sections: [
          { label: "Certificate No.", text: "NOC/DFS/2008/8892-B" },
          { label: "Date of Issuance", text: "10th June 2008", highlight: true },
          { label: "Subject", text: "Provisional Fire Safety Clearance for Institutional Building at S.No. 45/2" },
          { label: "Validity Period", text: "Valid strictly up to 31st December 2027", highlight: true }
        ],
        stamp: "GOVT. OF MAHARASHTRA FIRE SERVICES - QR CODE SCANNED"
      }
    },
    {
      doc_id: "appx_affidavit",
      name: "AICTE Statutory Affidavit (Stamp Paper)",
      doc_type: "affidavit",
      overall: "manual_review_required",
      verification: null,
      note: "Area in affidavit could not be read reliably (confidence 0.62); please confirm it manually.",
      finding_ids: ["f_65b757f4"],
      fields: {
        institute_name: { value: "Shree Vidya Institute of Technology", confidence: 0.92 },
        deponent: { value: "Dr. R. K. Deshmukh (Secretary)", confidence: 0.88 },
        declared_area: { value: 2.5, unit: "acre", confidence: 0.62, bbox: [0.3, 0.58, 0.55, 0.62] }
      },
      previewContent: {
        header: "GOVERNMENT OF MAHARASHTRA - NON-JUDICIAL STAMP PAPER ₹100",
        sections: [
          { label: "Deponent Solemn Affirmation", text: "I, Dr. R. K. Deshmukh, Secretary of Shree Vidya Education Trust do hereby affirm..." },
          { label: "Clause 4 (Land)", text: "That the institution possesses uninterrupted possession of [Area: ~2.5? acres / smudged]", highlight: true },
          { label: "Notary Seal", text: "Advocate & Notary Public Govt. of India Reg. 4921" }
        ],
        stamp: "POOR CONTRAST / FAINT STAMP OCR CONFIDENCE 62%"
      }
    }
  ],
  findings: [
    {
      finding_id: "f_164256d5",
      app_id: "APP-2027-EOA-0492",
      type: "expired",
      severity: "high",
      rule_id: "NOC_VALID_FOR_YEAR",
      attribute: "valid_until",
      claims: [
        {
          doc_id: "appx_noc",
          doc_name: "Building Safety & Fire NOC",
          entity: "noc:building",
          attribute: "valid_until",
          value: "2027-12-31",
          authority: "third_party",
          confidence: 0.9,
          page: 1,
          bbox: [0.15, 0.52, 0.45, 0.56]
        }
      ],
      doc_ids: ["appx_noc"],
      message: "NOC expires on 2027-12-31 before the academic year ends (2028-06-30)",
      evidence: {
        field: "valid_until",
        value: "2027-12-31",
        confidence: 0.9,
        compared_to: "2028-06-30 (Academic Year End)",
        rule_desc: "All statutory NOCs must remain valid through the entire proposed academic cycle (Approval Process Handbook clause 4.2)."
      },
      status: "pending"
    },
    {
      finding_id: "f_4a9c0181",
      app_id: "APP-2027-EOA-0492",
      type: "attribute_conflict",
      severity: "high",
      rule_id: "LAND_AREA_AGREE",
      entity: "land_parcel:45/2",
      attribute: "area",
      claims: [
        {
          doc_id: "appx_application_form",
          doc_name: "Extension of Approval Form",
          entity: "land_parcel:45/2",
          attribute: "area",
          value: "2.50 acres",
          authority: "self_declared",
          confidence: 1.0,
          page: 1,
          bbox: [0.15, 0.45, 0.35, 0.48]
        },
        {
          doc_id: "appx_land_deed",
          doc_name: "Registered Sale Deed",
          entity: "land_parcel:45/2",
          attribute: "area",
          value: "2.10 acres",
          authority: "third_party",
          confidence: 0.93,
          page: 1,
          bbox: [0.12, 0.41, 0.35, 0.44]
        }
      ],
      doc_ids: ["appx_application_form", "appx_land_deed"],
      message: "Land parcel area conflicts: 2.50 in application_form vs 2.10 in land_deed",
      evidence: {
        discrepancy: "0.40 acres deficit on registered deed",
        rule_desc: "The total contiguous land area declared by the institution in the portal must match the registered title deed with tolerance <= 0.05 acres."
      },
      status: "pending"
    },
    {
      finding_id: "f_1214faea",
      app_id: "APP-2027-EOA-0492",
      type: "relationship_violation",
      severity: "high",
      rule_id: "OWNER_IS_TRUST",
      entity: "land_parcel:45/2",
      attribute: "owner",
      claims: [
        {
          doc_id: "appx_land_deed",
          doc_name: "Registered Sale Deed",
          entity: "land_parcel:45/2",
          attribute: "owner",
          value: "Shree Vidya Charitable Society",
          authority: "third_party",
          confidence: 0.91,
          page: 1,
          bbox: [0.12, 0.32, 0.60, 0.36]
        },
        {
          doc_id: "appx_application_form",
          doc_name: "Extension of Approval Form",
          entity: "trust:applicant",
          attribute: "trust_name",
          value: "Shree Vidya Education Trust",
          authority: "self_declared",
          confidence: 1.0,
          page: 1
        }
      ],
      doc_ids: ["appx_land_deed", "appx_application_form"],
      message: "Land owner 'Shree Vidya Charitable Society' does not match the trust 'Shree Vidya Education Trust'",
      evidence: {
        entity_resolved_name_1: "Shree Vidya Charitable Society (Society)",
        entity_resolved_name_2: "Shree Vidya Education Trust (Trust)",
        rule_desc: "Title deed ownership must stand solely in the name of the sponsoring Trust/Society declared in the AICTE application form."
      },
      status: "pending"
    },
    {
      finding_id: "f_a72a0889",
      app_id: "APP-2027-EOA-0492",
      type: "timeline_violation",
      severity: "high",
      rule_id: "TL_NOC_AFTER_TRUST",
      entity: "trust:applicant",
      attribute: "trust_reg_date",
      claims: [
        {
          doc_id: "appx_noc",
          doc_name: "Building Safety & Fire NOC",
          entity: "noc:building",
          attribute: "issue_date",
          value: "2008-06-10",
          authority: "third_party",
          confidence: 0.94,
          page: 1,
          bbox: [0.70, 0.15, 0.92, 0.18]
        },
        {
          doc_id: "appx_application_form",
          doc_name: "Extension of Approval Form",
          entity: "trust:applicant",
          attribute: "trust_reg_date",
          value: "2009-04-15",
          authority: "self_declared",
          confidence: 1.0,
          page: 1
        }
      ],
      doc_ids: ["appx_application_form", "appx_noc"],
      message: "NOC dated 2008-06-10 is earlier than trust registration 2009-04-15",
      evidence: {
        sequence: "NOC Issue (10-Jun-2008) -> Trust Registration (15-Apr-2009)",
        temporal_gap: "10 months pre-dating registration",
        rule_desc: "Statutory permits and clearances cannot pre-date the legal incorporation/registration date of the trust."
      },
      status: "pending"
    },
    {
      finding_id: "f_65b757f4",
      app_id: "APP-2027-EOA-0492",
      type: "unreadable",
      severity: "low",
      rule_id: "LAND_AREA_AGREE",
      entity: "land_parcel:45/2",
      attribute: "area",
      claims: [
        {
          doc_id: "appx_affidavit",
          doc_name: "Statutory Affidavit",
          entity: "land_parcel:45/2",
          attribute: "declared_area",
          value: "2.5 (?)",
          authority: "self_declared",
          confidence: 0.62,
          page: 1,
          bbox: [0.3, 0.58, 0.55, 0.62]
        }
      ],
      doc_ids: ["appx_affidavit"],
      message: "Area in affidavit could not be read reliably (confidence 0.62); please confirm it manually",
      evidence: {
        ocr_confidence: 0.62,
        action_required: "Officer manual verification required. Per Core Principle 6: unreadable data does NOT trigger a fake/forged claim."
      },
      status: "pending"
    }
  ]
};

export const CLEAN_APP: ApplicationCase = {
  app_id: "APP-2027-EOA-0105",
  institute_name: "Government College of Engineering & Technology",
  aicte_permanent_id: "1-1209384",
  application_no: "1-46200000889",
  academic_year: "2027-2028",
  priority: 0,
  status: "Verified Clean",
  documents: [
    {
      doc_id: "clean_form",
      name: "Extension of Approval Form (Form-A)",
      doc_type: "application_form",
      overall: "no_issues",
      verification: "verified",
      note: "All mandatory fields extracted with 100% confidence. Form matches institutional records.",
      finding_ids: [],
      fields: {
        institute_name: { value: "Government College of Engineering & Technology", confidence: 1.0 },
        aicte_permanent_id: { value: "1-1209384", confidence: 1.0 },
        trust_name: { value: "Directorate of Technical Education", confidence: 1.0 },
        land_area: { value: 15.0, unit: "acre", confidence: 1.0 }
      },
      previewContent: {
        header: "AICTE APPLICATION FOR EXTENSION OF APPROVAL - STATE GOVT. INSTITUTE",
        sections: [
          { label: "Institution", text: "Govt College of Engineering & Technology" },
          { label: "Land Area", text: "15.00 Acres Government Land (Survey 102/1)" },
          { label: "Approval Status", text: "Complies with norms (0 deficiencies)" }
        ],
        stamp: "E-VERIFIED WITH AICTE REPOSITORIES"
      }
    },
    {
      doc_id: "clean_deed",
      name: "Government Land Allotment Order",
      doc_type: "land_deed",
      overall: "no_issues",
      verification: "verified",
      note: "Revenue department land grant gazette notification verified with digital signature.",
      finding_ids: [],
      fields: {
        survey_no: { value: "102/1", confidence: 1.0 },
        area: { value: 15.0, unit: "acre", confidence: 1.0 }
      },
      previewContent: {
        header: "REVENUE AND FOREST DEPARTMENT - GAZETTE SANCTION ORDER",
        sections: [
          { label: "Grantee", text: "Government College of Engineering & Technology" },
          { label: "Sanctioned Land", text: "15.00 Acres unencumbered" }
        ],
        stamp: "DIGITALLY SIGNED VIA E-MUDHRA CERTIFICATE"
      }
    },
    {
      doc_id: "clean_noc",
      name: "Fire Safety & Building Fitness Certificate",
      doc_type: "noc",
      overall: "no_issues",
      verification: "verified",
      note: "Issued by Municipal Fire Authority. Valid through March 2029.",
      finding_ids: [],
      fields: {
        valid_until: { value: "2029-03-31", confidence: 0.98 }
      },
      previewContent: {
        header: "METROPOLITAN FIRE BRIGADE - ANNUAL CLEARANCE",
        sections: [
          { label: "Validity", text: "Valid through 31-March-2029" },
          { label: "Compliance", text: "Meets National Building Code Part IV norms" }
        ],
        stamp: "OFFICIALLY VERIFIED VIA QR CODE"
      }
    }
  ],
  findings: []
};
