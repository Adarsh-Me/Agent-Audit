"""Upload ingestion endpoint — POST /api/uploads (SCHEMA §7.1)."""

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.errors import AppError
from app.ingest.upload import (
    PayloadError,
    create_upload_catalog,
    parse_upload_body,
    validate_product_list,
)

router = APIRouter()


@router.post("/api/uploads", status_code=201)
async def create_upload(
    request: Request,
    session: AsyncSession = Depends(get_session),
    file: UploadFile | None = File(default=None),
) -> dict:
    if file is not None:
        raw = await file.read()
        name = (file.filename or "").lower()
        kind = "csv" if name.endswith(".csv") or "text/csv" in (file.content_type or "") else "json"
    else:
        raw = await request.body()
        kind = "csv" if "text/csv" in (request.headers.get("content-type") or "") else "json"

    try:
        items = parse_upload_body(raw, kind)
        result = validate_product_list(items)
    except PayloadError as exc:
        status = {"E102": 400}.get(exc.code, 400)
        raise AppError(exc.code, exc.message, status_code=status) from exc

    catalog_id = await create_upload_catalog(session, result.valid)
    return {
        "catalog_id": catalog_id,
        "valid": len(result.valid),
        "invalid": [
            {"row": e.row, "code": e.code, "message": e.message} for e in result.errors
        ],
    }
