"""Safe serving of application documents.

Only PDF/JPEG/PNG files inside `data/synthetic/{app_id}/` are reachable.  The route
rejects traversal, absolute paths, hidden files and every other file type.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..pipeline import is_valid_app_id

router = APIRouter(tags=["files"])

PREVIEWABLE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg"}
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
SAFE_NAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


def _safe_name(name: str) -> bool:
    if not name or name.startswith(".") or ".." in name:
        return False
    if len(name) > 128:
        return False
    return all(character in SAFE_NAME_CHARS for character in name)


@router.get("/files/{app_id}/{name}")
def serve_document(request: Request, app_id: str, name: str) -> FileResponse:
    if not is_valid_app_id(app_id) or not _safe_name(name):
        raise HTTPException(status_code=400, detail="Invalid application or document name")

    suffix = Path(name).suffix.lower()
    if suffix not in PREVIEWABLE_SUFFIXES:
        raise HTTPException(status_code=404, detail="Document not found")

    settings = request.app.state.settings
    base = settings.synthetic_dir / app_id
    if not base.is_dir():
        raise HTTPException(status_code=404, detail="Document not found")

    candidate = base / name
    try:
        if not candidate.is_file():
            raise HTTPException(status_code=404, detail="Document not found")
        resolved_base = base.resolve(strict=True)
        resolved_file = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        raise HTTPException(status_code=404, detail="Document not found") from None

    if not resolved_file.is_relative_to(resolved_base):
        raise HTTPException(status_code=404, detail="Document not found")

    return FileResponse(
        resolved_file,
        media_type=MEDIA_TYPES[suffix],
        headers={
            "Content-Disposition": f'inline; filename="{name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=0, must-revalidate",
        },
    )
