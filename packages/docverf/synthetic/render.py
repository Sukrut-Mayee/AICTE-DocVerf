"""HTML from Jinja2 templates, and PDFs from that HTML with headless Chrome / Edge.

Chrome is used because the documents carry Marathi / Hindi labels and only a browser with a
Devanagari font renders them (on WSL the Windows Chrome does; the Linux fonts here do not).
Set CHROME_PATH to use another browser.
"""

import base64
import io
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path, PureWindowsPath
from typing import Any

import jinja2
from PIL import Image, ImageDraw, ImageFont

from docverf.synthetic.model import AppSpec

TEMPLATES = Path(__file__).parent / "templates"


def _watermark_uri() -> str:
    """'SYNTHETIC TEST DOCUMENT' as a faint diagonal PNG. It is a picture, not text, so the PDF
    text layer (and any OCR-like use of it) is not polluted by diagonal words."""
    text, font = "SYNTHETIC TEST DOCUMENT", ImageFont.load_default(size=72)
    layer = Image.new("RGBA", (int(font.getlength(text)) + 40, 120), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((20, 20), text, font=font, fill=(255, 0, 0, 45))
    buffer = io.BytesIO()
    layer.rotate(45, expand=True, resample=Image.Resampling.BICUBIC).save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES),
    autoescape=True,
    undefined=jinja2.StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.globals["watermark"] = _watermark_uri()

# Local-script labels of the land deed, in Marathi and Hindi (the English label is the exact
# text the rules extractor matches; see rules_extractor._LABEL_SPECS).
LOCAL_LABELS = {
    "mr": {
        "title": "खरेदीखत", "property": "मालमत्तेची माहिती", "parties": "पक्षकार",
        "deed": "दस्त तपशील", "village": "गाव", "taluka": "तालुका", "district": "जिल्हा",
        "survey_no": "गट नंबर", "area": "जमिनीचे क्षेत्रफळ", "mortgage_status": "गहाण स्थिती",
        "owner_name": "मालकाचे नाव", "registration_no": "दस्त नोंदणी क्रमांक",
        "registration_date": "नोंदणी दिनांक", "office": "नोंदणी कार्यालय",
    },
    "hi": {
        "title": "विक्रय विलेख", "property": "संपत्ति विवरण", "parties": "पक्षकार",
        "deed": "दस्तावेज़ विवरण", "village": "गाँव", "taluka": "तहसील", "district": "जिला",
        "survey_no": "सर्वे नंबर", "area": "भूमि का क्षेत्रफल", "mortgage_status": "बंधक स्थिति",
        "owner_name": "मालिक का नाम", "registration_no": "दस्तावेज़ पंजीकरण क्रमांक",
        "registration_date": "पंजीकरण तिथि", "office": "पंजीकरण कार्यालय",
    },
}  # fmt: skip


def context(app: AppSpec, doc_type: str) -> dict[str, Any]:
    """What the template of `doc_type` prints, from the application data."""
    if doc_type == "land_deed":
        return {
            "local": LOCAL_LABELS[app.deed_lang],
            "deed": {
                "village": app.village,
                "taluka": app.taluka,
                "district": app.district,
                "survey_no": app.survey_no,
                "area": app.deed_area.printed(),
                "mortgage_status": app.mortgage_status.capitalize(),
                "owner_name": app.owner_name,
                "registration_no": app.registration_no,
                "registration_date": f"{app.registration_date:%d/%m/%Y}",
            },
        }
    if doc_type == "noc":
        return {
            "noc": {
                "ref_no": app.noc_ref_no,
                "issuer": app.noc_issuer,
                "issue_date": f"{app.noc_issue_date:%d %B %Y}",
                "valid_until": f"{app.noc_valid_until:%d %B %Y}",
                "institute_name": app.noc_institute_name,
                "purpose": app.noc_purpose,
                "signatory": app.noc_signatory,
            }
        }
    if doc_type == "affidavit":
        return {
            "aff": {
                "deponent_name": app.deponent_name,
                "institute_name": app.affidavit_institute_name,
                "application_no": app.application_no,
                "date": app.affidavit_date.isoformat(),
                "area": app.affidavit_area.printed(),
                "notary_reg_no": app.notary_reg_no,
            }
        }
    if doc_type == "accreditation_cert" and app.accreditation:
        a = app.accreditation
        return {
            "cert": {
                "institute_name": a.institute_name,
                "cert_no": a.cert_no,
                "body": a.body,
                "programs": "; ".join(a.programs),
                "valid_from": a.valid_from.isoformat(),
                "valid_to": a.valid_to.isoformat(),
            }
        }
    raise ValueError(f"no template for {doc_type!r}")


def render_html(app: AppSpec, doc_type: str) -> str:
    return _env.get_template(f"{doc_type}.html.j2").render(**context(app, doc_type))


# ---- PDF ----

_BROWSERS = [  # Windows browsers first: they have Devanagari fonts
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
]
_ON_PATH = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge"]


def find_browser() -> str | None:
    configured = os.environ.get("CHROME_PATH")
    if configured and Path(configured).exists():
        return configured
    for path in _BROWSERS:
        if Path(path).exists():
            return path
    return next((found for name in _ON_PATH if (found := shutil.which(name))), None)


def _for_browser(path: Path, windows_browser: bool) -> str:
    """The path as the browser sees it (a Windows browser on WSL needs a Windows path)."""
    if not windows_browser:
        return str(path.resolve())
    out = subprocess.run(["wslpath", "-w", str(path.resolve())], capture_output=True, text=True)
    return out.stdout.strip()


def _windows_temp() -> Path | None:
    """The Windows TEMP folder as a WSL path. A browser profile there starts about 4x faster than
    one on the Linux file system, which a Windows browser reaches over the network share."""
    try:
        out = subprocess.run(
            ["cmd.exe", "/c", "echo %TEMP%"], capture_output=True, text=True, timeout=20
        ).stdout.strip()
        path = subprocess.run(["wslpath", "-u", out], capture_output=True, text=True).stdout.strip()
        return Path(path) if path and Path(path).is_dir() else None
    except (OSError, subprocess.SubprocessError):
        return None


class PdfRenderer:
    """Prints HTML files to PDF with one headless browser profile that is deleted afterwards."""

    def __init__(self, work_dir: Path):
        browser = find_browser()
        if browser is None:
            raise RuntimeError("no Chrome / Edge found; install one or set CHROME_PATH")
        self.browser = browser
        self.windows = browser.lower().endswith(".exe") and platform.system() == "Linux"
        parent = (_windows_temp() if self.windows else None) or work_dir
        parent.mkdir(parents=True, exist_ok=True)
        self.profile = Path(tempfile.mkdtemp(prefix="docverf-chrome-", dir=parent))

    def __enter__(self) -> "PdfRenderer":
        return self

    def __exit__(self, *exc: object) -> None:
        shutil.rmtree(self.profile, ignore_errors=True)

    def render(self, html: Path, pdf: Path) -> None:
        source = _for_browser(html, self.windows)
        url = PureWindowsPath(source).as_uri() if self.windows else html.resolve().as_uri()
        command = [
            self.browser,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--no-first-run",
            f"--user-data-dir={_for_browser(self.profile, self.windows)}",
            f"--print-to-pdf={_for_browser(pdf, self.windows)}",
            url,
        ]
        pdf.unlink(missing_ok=True)
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if not pdf.exists():
            raise RuntimeError(f"browser did not write {pdf}: {result.stderr[-400:]}")
