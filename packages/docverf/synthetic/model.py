"""A synthetic application as plain data (TRD §13).

`build_clean_app` fills every document from one set of values chosen to satisfy all reasoning
rules (dates read from docverf.config). Defects (defects.py) change this data; the HTML, PDFs and
ground_truth.json are all derived from it afterwards, so a defect cannot exist as a label only.
"""

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from docverf.config import get_settings
from docverf.schemas import (
    DocType,
    ExtractionResult,
    FieldValue,
    GroundTruth,
    GroundTruthDoc,
    InjectedDefect,
)
from docverf.units import ACRES_PER_UNIT

PREFIXES = [
    "Shree Vidya", "Sahyadri", "Godavari", "Krishna Valley", "Rajarshi Shahu", "Sant Dnyaneshwar",
    "Bharat", "Lokmanya", "Savitribai Phule", "Deccan", "Konkan", "Vidarbha", "Marathwada",
    "Nashik Valley", "Pune Central", "Mumbai Coastal", "Ajanta", "Ellora", "Sinhagad", "Pratapgad",
]  # fmt: skip
INSTITUTE_TYPES = [
    "Institute of Technology",
    "College of Engineering",
    "Institute of Engineering and Technology",
    "Polytechnic",
]
TRUST_TYPES = ["Education Trust", "Education Society", "Charitable Trust"]
ABBREVIATIONS = {"Institute": "Inst.", "Technology": "Tech.", "Engineering": "Engg."}
FIRST = ["Rajesh", "Sunita", "Anil", "Meena", "Prakash", "Vandana", "Suresh", "Kavita", "Mahesh"]
LAST = ["Patil", "Deshmukh", "Kulkarni", "Jadhav", "More", "Pawar", "Shinde", "Joshi", "Bhosale"]
PLACES = [
    "Wagholi", "Hinjewadi", "Talegaon", "Lonavala", "Pirangut", "Chakan", "Khed", "Mulshi",
    "Baramati", "Saswad",
]  # fmt: skip
DISTRICTS = ["Pune", "Nashik", "Satara", "Kolhapur", "Sangli", "Ahmednagar", "Solapur"]
PROGRAMS = [
    "Computer Engineering", "Civil Engineering", "Mechanical Engineering",
    "Electrical Engineering", "Information Technology", "Electronics Engineering",
]  # fmt: skip
ROOM_LABELS = [
    "Computer Lab 1", "Computer Lab 2", "Electronics Lab", "Networking Lab", "CAD CAM Lab",
    "Programming Lab", "Research Lab", "Software Lab",
]  # fmt: skip
NOC_ISSUERS = [
    "Maharashtra Fire Services",
    "Chief Fire Officer, Pune Municipal Corporation",
    "Directorate of Fire Services, Maharashtra",
]
NOC_PURPOSES = [
    "Fire safety clearance for educational building",
    "Fire safety clearance for engineering college campus",
]
UNIT_WEIGHTS = {"acre": 55, "hectare": 20, "guntha": 25}
MARATHI_UNITS = {"acre": "एकर", "hectare": "हेक्टर", "guntha": "गुंठा"}
_MARATHI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


@dataclass
class Area:
    """An area as printed on a document. `unit` is canonical (acre | hectare | guntha)."""

    value: float
    unit: str
    marathi: bool = False  # print digits and unit in Devanagari (land deeds)

    @property
    def acres(self) -> float:
        return self.value * ACRES_PER_UNIT[self.unit]

    def printed(self) -> str:
        number = f"{self.value:g}"
        if not self.marathi:
            return f"{number} {self.unit}"
        return f"{number.translate(_MARATHI_DIGITS)} {MARATHI_UNITS[self.unit]}"


def make_area(acres: float, unit: str, marathi: bool = False) -> Area:
    """The area of `acres` expressed in `unit`, rounded as a document would print it."""
    if unit == "guntha":
        value = float(round(acres / ACRES_PER_UNIT["guntha"]))
    elif unit == "hectare":
        value = round(acres / ACRES_PER_UNIT["hectare"], 4)
    else:
        value = round(acres, 3)
    return Area(value, unit, marathi)


@dataclass
class Photo:
    n: int  # lab_photo_{n}.jpg
    seed: int  # the image is drawn from these four values: equal values, equal bytes
    room_label: str
    equipment_count: int
    capture_date: date
    copied_from: str | None = None  # doc_id of the photo this one duplicates (DUPLICATE_PHOTO)


@dataclass
class Accreditation:
    body: str
    cert_no: str
    institute_name: str
    programs: list[str]
    valid_from: date
    valid_to: date


@dataclass
class AppSpec:
    app_id: str
    index: int
    # institute and trust
    institute_name: str
    institute_short: str | None  # abbreviated form used by the affidavit, if any
    aicte_permanent_id: str
    application_no: str
    ter_txn_id: str
    trust_name: str
    trust_reg_no: str
    trust_reg_date: date
    address: str
    principal_name: str
    built_up_area_sqm: float
    programs: list[tuple[str, int]]
    survey_no: str
    village: str
    taluka: str
    district: str
    application_date: date
    form_area: Area
    # land deed
    deed_area: Area
    owner_name: str
    registration_no: str
    registration_date: date
    mortgage_status: str
    deed_lang: str  # "mr" or "hi": language of the local-script labels
    # NOC
    noc_issuer: str
    noc_ref_no: str
    noc_institute_name: str
    noc_purpose: str
    noc_issue_date: date
    noc_valid_until: date
    noc_signatory: str
    # affidavit
    affidavit_area: Area
    deponent_name: str
    affidavit_date: date
    notary_reg_no: str
    accreditation: Accreditation | None
    photos: list[Photo]
    # injection state
    missing: set[str] = field(default_factory=set)  # doc_type values left out
    pasted_signature: bool = False
    defects: list[InjectedDefect] = field(default_factory=list)

    @property
    def affidavit_institute_name(self) -> str:
        return self.institute_short or self.institute_name

    def doc_id(self, doc_type: str) -> str:
        return f"{self.app_id}_{doc_type}"

    def photo_doc_id(self, photo: Photo) -> str:
        n = f"_{photo.n}" if len(self.photos) > 1 else ""
        return f"{self.app_id}_lab_photo{n}"

    def documents(self) -> list[tuple[str, str, str]]:
        """(doc_id, doc_type, file name) of every document that is present (TRD §13.1)."""
        docs = [
            ("application_form", "application_form.json"),
            ("land_deed", "land_deed.pdf"),
            ("noc", "noc.pdf"),
            ("affidavit", "affidavit.pdf"),
        ]
        if self.accreditation:
            docs.append(("accreditation_cert", "accreditation_cert.pdf"))
        present = [(self.doc_id(t), t, name) for t, name in docs if t not in self.missing]
        present += [
            (self.photo_doc_id(p), "lab_photo", f"lab_photo_{p.n}.jpg") for p in self.photos
        ]
        return present


def _person(rng: random.Random) -> str:
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def abbreviate(name: str) -> str | None:
    """'Shree Vidya Institute of Technology' -> 'Shree Vidya Inst. of Tech.' (None if unchanged)."""
    short = " ".join(ABBREVIATIONS.get(word, word) for word in name.split())
    return short if short != name else None


def build_clean_app(index: int, seed: int = 42) -> AppSpec:
    """Application number `index` (1-based) with no defect, deterministic in (index, seed)."""
    rng = random.Random(f"{seed}:{index}")
    settings = get_settings()
    window_start, window_end = settings.APPLICATION_WINDOW_START, settings.APPLICATION_WINDOW_END
    app_id = f"app{index:03d}"

    prefix = PREFIXES[(index * 7 + seed) % len(PREFIXES)]  # 7 is coprime with 20: distinct prefixes
    institute = f"{prefix} {rng.choice(INSTITUTE_TYPES)}"
    trust = f"{prefix} {rng.choice(TRUST_TYPES)}"

    # Dates: trust < deed < NOC issue < application, which and the affidavit are in the window;
    # the NOC outlives the academic year.
    span = (window_end - window_start).days - 10
    application_date = window_start + timedelta(days=10 + rng.randint(0, max(span, 0)))
    affidavit_date = application_date - timedelta(days=rng.randint(0, 9))
    noc_issue = application_date - timedelta(days=rng.randint(45, 1000))
    registration_date = noc_issue - timedelta(days=rng.randint(60, 1500))
    trust_reg_date = registration_date - timedelta(days=rng.randint(90, 2500))
    noc_valid_until = settings.ACADEMIC_YEAR_END + timedelta(days=rng.randint(30, 1500))

    acres = round(
        rng.randint(40, 240) * ACRES_PER_UNIT["guntha"], 3
    )  # whole gunthas: exact in all units
    units = rng.choices(list(UNIT_WEIGHTS), weights=list(UNIT_WEIGHTS.values()), k=3)
    village, district = rng.choice(PLACES), rng.choice(DISTRICTS)
    survey_no = f"{rng.randint(10, 99)}/{rng.randint(1, 9)}"

    accreditation = None
    if index % 2 == 1:  # about half of the applications carry an accreditation certificate
        body = rng.choice(["NBA", "NAAC"])
        valid_from = max(
            application_date - timedelta(days=rng.randint(400, 1800)),
            trust_reg_date + timedelta(days=365),
        )
        accreditation = Accreditation(
            body=body,
            cert_no=f"{body}/{valid_from.year}/{rng.randint(1000, 9999)}",
            institute_name=institute,
            programs=rng.sample(PROGRAMS, rng.randint(1, 2)),
            valid_from=valid_from,
            valid_to=max(
                valid_from + timedelta(days=3 * 365),
                settings.ACADEMIC_YEAR_END + timedelta(days=rng.randint(0, 700)),
            ),
        )

    photos = [
        Photo(
            n=n,
            seed=rng.randrange(1 << 30),
            room_label=rng.choice(ROOM_LABELS),
            equipment_count=rng.randint(6, 24),
            capture_date=application_date - timedelta(days=rng.randint(5, 120)),
        )
        for n in range(1, rng.choice([1, 2]) + 1)
    ]

    return AppSpec(
        app_id=app_id,
        index=index,
        institute_name=institute,
        institute_short=abbreviate(institute) if rng.random() < 0.5 else None,
        aicte_permanent_id=f"1-{1000000 + index * 137 + rng.randint(0, 99)}",
        application_no=f"1-4620000{index:04d}",
        ter_txn_id=f"TER2027{index:06d}",
        trust_name=trust,
        trust_reg_no=f"E-{rng.randint(1000, 9999)}/PUNE",
        trust_reg_date=trust_reg_date,
        address=f"Survey No. {survey_no}, {village}, {district}, Maharashtra",
        principal_name=_person(rng),
        built_up_area_sqm=float(rng.randint(1500, 9000)),
        programs=[(name, rng.choice([30, 60, 90, 120])) for name in rng.sample(PROGRAMS, 3)],
        survey_no=survey_no,
        village=village,
        taluka=rng.choice(PLACES),
        district=district,
        application_date=application_date,
        form_area=make_area(acres, units[0]),
        deed_area=make_area(acres, units[1], marathi=rng.random() < 0.3),
        owner_name=trust,
        registration_no=f"DRN/{registration_date.year}/{rng.randint(10000, 99999)}",
        registration_date=registration_date,
        mortgage_status="none",
        deed_lang=rng.choice(["mr", "mr", "hi"]),
        noc_issuer=rng.choice(NOC_ISSUERS),
        noc_ref_no=f"FIRE/MH/{noc_issue.year}/{rng.randint(100000, 999999)}",
        noc_institute_name=institute,
        noc_purpose=rng.choice(NOC_PURPOSES),
        noc_issue_date=noc_issue,
        noc_valid_until=noc_valid_until,
        noc_signatory=_person(rng),
        affidavit_area=make_area(acres, units[2]),
        deponent_name=_person(rng),
        affidavit_date=affidavit_date,
        notary_reg_no=f"NOT/MH/{affidavit_date.year}/{rng.randint(1000, 9999)}",
        accreditation=accreditation,
        photos=photos,
    )


# ---- ground truth (TRD §5, field names exactly as TRD §6) ----


def _area(area: Area) -> dict[str, Any]:
    return {"value": area.value, "unit": area.unit}


def true_fields(app: AppSpec) -> dict[str, dict[str, Any]]:
    """doc_id -> field -> true normalized value, for the documents that are present.

    Areas are {"value", "unit"}; dates are ISO strings."""
    fields: dict[str, dict[str, Any]] = {
        app.doc_id("application_form"): {
            "institute_name": app.institute_name,
            "aicte_permanent_id": app.aicte_permanent_id,
            "application_no": app.application_no,
            "trust_name": app.trust_name,
            "trust_reg_no": app.trust_reg_no,
            "trust_reg_date": app.trust_reg_date.isoformat(),
            "address": app.address,
            "land_survey_no": app.survey_no,
            "land_area": _area(app.form_area),
            "built_up_area_sqm": app.built_up_area_sqm,
            "programs": [{"name": n, "intake": i} for n, i in app.programs],
            "principal_name": app.principal_name,
            "application_date": app.application_date.isoformat(),
            "ter_txn_id": app.ter_txn_id,
        },
        app.doc_id("land_deed"): {
            "owner_name": app.owner_name,
            "survey_no": app.survey_no,
            "area": _area(app.deed_area),
            "village": app.village,
            "district": app.district,
            "registration_no": app.registration_no,
            "registration_date": app.registration_date.isoformat(),
            "mortgage_status": app.mortgage_status,
        },
        app.doc_id("noc"): {
            "issuer": app.noc_issuer,
            "ref_no": app.noc_ref_no,
            "institute_name": app.noc_institute_name,
            "purpose": app.noc_purpose,
            "issue_date": app.noc_issue_date.isoformat(),
            "valid_until": app.noc_valid_until.isoformat(),
            "signatory": app.noc_signatory,
        },
        app.doc_id("affidavit"): {
            "deponent_name": app.deponent_name,
            "institute_name": app.affidavit_institute_name,
            "application_no": app.application_no,
            "date": app.affidavit_date.isoformat(),
            "land_area_declared": _area(app.affidavit_area),
            "notary_reg_no": app.notary_reg_no,
        },
    }
    if app.accreditation:
        a = app.accreditation
        fields[app.doc_id("accreditation_cert")] = {
            "body": a.body,
            "cert_no": a.cert_no,
            "institute_name": a.institute_name,
            "programs": list(a.programs),
            "valid_from": a.valid_from.isoformat(),
            "valid_to": a.valid_to.isoformat(),
        }
    for photo in app.photos:
        fields[app.photo_doc_id(photo)] = {
            "room_label": photo.room_label,
            "equipment_count": photo.equipment_count,
            "capture_date": photo.capture_date.isoformat(),
        }
    present = {doc_id for doc_id, _, _ in app.documents()}
    return {doc_id: f for doc_id, f in fields.items() if doc_id in present}


def ground_truth(app: AppSpec) -> GroundTruth:
    return GroundTruth(
        app_id=app.app_id,
        documents=[
            GroundTruthDoc(doc_id=doc_id, doc_type=DocType(doc_type), path=path)
            for doc_id, doc_type, path in app.documents()
        ],
        true_fields=true_fields(app),
        injected_defects=list(app.defects),
    )


def extractions_from_truth(truth: GroundTruth, confidence: float = 1.0) -> list[ExtractionResult]:
    """The true fields of every document as perfect extractions (the reasoning oracle)."""
    results = []
    for doc in truth.documents:
        fields = {}
        for name, value in truth.true_fields[doc.doc_id].items():
            if isinstance(value, dict) and set(value) == {"value", "unit"}:
                fields[name] = FieldValue(
                    value=value["value"], unit=value["unit"], confidence=confidence
                )
            else:
                fields[name] = FieldValue(value=value, confidence=confidence)
        results.append(
            ExtractionResult(
                doc_id=doc.doc_id, app_id=truth.app_id, doc_type=doc.doc_type, fields=fields
            )
        )
    return results


def extraction_results(app: AppSpec, confidence: float = 1.0) -> list[ExtractionResult]:
    """The true fields of every present document of `app` as perfect extractions."""
    return extractions_from_truth(ground_truth(app), confidence)
