"""Remediation endpoints — generate · list · review · mirror (APPFLOW F5)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product, Remediation
from app.db.session import get_session
from app.errors import AppError
from app.remediate.fixes import build_mirror_catalog, generate_remediations

router = APIRouter()


class ReviewBody(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    reviewed_by: str = "merchant"


@router.post("/api/remediations/{run_id}/generate", status_code=201)
async def post_generate(run_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    return await generate_remediations(session, run_id)


@router.get("/api/remediations")
async def list_remediations(run_id: str,
                            session: AsyncSession = Depends(get_session)) -> dict:
    rows = (
        (await session.execute(
            select(Remediation).where(Remediation.run_id == run_id).order_by(Remediation.id)
        ))
        .scalars()
        .all()
    )
    out = []
    for r in rows:
        p = await session.get(Product, r.product_id)
        out.append({
            "id": r.id,
            "product_id": r.product_id,
            "sku": p.sku if p else None,
            "title": p.title if p else None,
            "status": r.status,
            "reviewed_by": r.reviewed_by,
            "applied_at": r.applied_at.isoformat() if r.applied_at else None,
            "fixes": r.fixes,
        })
    counts = {"pending": 0, "approved": 0, "rejected": 0}
    for o in out:
        counts[o["status"]] += 1
    return {"run_id": run_id, "counts": counts, "remediations": out}


@router.patch("/api/remediations/{rem_id}")
async def review_remediation(rem_id: str, body: ReviewBody,
                             session: AsyncSession = Depends(get_session)) -> dict:
    rem = await session.get(Remediation, rem_id)
    if rem is None:
        raise AppError("E601", "remediation not found", status_code=404)
    rem.status = body.status
    rem.reviewed_by = body.reviewed_by
    await session.commit()
    return {"id": rem.id, "status": rem.status}


@router.post("/api/remediations/{run_id}/mirror", status_code=201)
async def post_mirror(run_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    mirror_id = await build_mirror_catalog(session, run_id)
    return {"mirror_catalog_id": mirror_id, "parent_run_id": run_id}
