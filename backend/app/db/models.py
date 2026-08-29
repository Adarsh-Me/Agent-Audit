"""SQLAlchemy ORM models — portable mirror of SCHEMA §6 (authoritative DDL).

Postgres deployments apply backend/db/init.sql verbatim; this ORM is the dev/SQLite
shape and must stay column-for-column in sync (enforced by tests/test_db_models.py).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

from app.constants import TRIALS_PER_FULL_RUN


class Base(DeclarativeBase):
    pass


def JSONType():
    return JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(Text)
    gmv_monthly_inr: Mapped[int | None] = mapped_column(Integer)
    aov_inr: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Catalog(Base):
    __tablename__ = "catalogs"
    __table_args__ = (
        CheckConstraint(
            "source IN ('demo','upload','mirror')", name="ck_catalogs_source"
        ),  # SC-2: 'mirror' required by the remediation flow
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"))
    source: Mapped[str] = mapped_column(Text)
    parent_catalog_id: Mapped[str | None] = mapped_column(
        ForeignKey("catalogs.id")
    )  # SC-2: mirror → original
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint(
            "tier IN ('rich','medium','starved','unknown')", name="ck_products_tier"
        ),
        UniqueConstraint("catalog_id", "sku", name="uq_products_catalog_sku"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    catalog_id: Mapped[str] = mapped_column(ForeignKey("catalogs.id"))
    sku: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    price_inr: Mapped[int | None] = mapped_column(Integer)  # true price; null only for malformed uploads
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    page_url: Mapped[str | None] = mapped_column(Text)
    tier: Mapped[str] = mapped_column(Text)
    structured_data: Mapped[dict] = mapped_column(JSONType(), default=dict)
    legibility_composite: Mapped[float | None] = mapped_column(Float)


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint("type IN ('audit','rerun')", name="ck_runs_type"),
        CheckConstraint(
            "status IN ('queued','running','done','failed','partial')", name="ck_runs_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    catalog_id: Mapped[str] = mapped_column(ForeignKey("catalogs.id"))
    parent_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("runs.id")
    )  # SC-4: links a rerun to its original
    type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    models: Mapped[dict] = mapped_column(JSONType())  # §3.4 snapshot of models.yaml at run time
    seeds: Mapped[dict] = mapped_column(JSONType())  # §3.4 snapshot
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    trials_total: Mapped[int] = mapped_column(Integer, default=TRIALS_PER_FULL_RUN)  # SC-6
    abort_reason: Mapped[str | None] = mapped_column(Text)  # partial/failed cause, human-readable
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Trial(Base):
    __tablename__ = "trials"
    __table_args__ = (
        CheckConstraint("tier IN ('bulk','flagship')", name="ck_trials_tier"),  # SC-6
        # C-2 choice semantics: a parsed trial with no choice is only legal when null was allowed.
        # Boolean-literal form is portable across SQLite AND Postgres — the old
        # `parse_ok = 0 … null_allowed = 1` DDL passed locally but made Postgres
        # reject CREATE TABLE (operator boolean = integer), which silently stranded
        # every production boot on the ephemeral-SQLite fallback (2026-08-26).
        CheckConstraint(
            "NOT parse_ok OR choice IS NOT NULL OR null_allowed",
            name="ck_trials_choice_semantics",
        ),
        Index("idx_trials_run", "run_id"),
        Index("idx_trials_hash", "prompt_hash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    model: Mapped[str] = mapped_column(Text)  # engine id (SCHEMA §2.3)
    model_version: Mapped[str] = mapped_column(Text)  # pinned snapshot
    tier: Mapped[str] = mapped_column(Text, default="bulk")
    persona_id: Mapped[str] = mapped_column(Text)
    condition: Mapped[str] = mapped_column(Text)
    seed: Mapped[int] = mapped_column(Integer)
    presented_order: Mapped[list] = mapped_column(JSONType())
    choice: Mapped[str | None] = mapped_column(Text)  # sku | NULL; semantics §3.3.2
    reason: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_hash: Mapped[str] = mapped_column(Text)
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False)  # SC-6
    # 2026-08-29: head of the failing response / provider error — parse_ok=0
    # runs were undiagnosable without it. Populated only on failed trials.
    raw_head: Mapped[str | None] = mapped_column(Text)
    null_allowed: Mapped[bool] = mapped_column(Boolean)
    parse_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResponseCache(Base):
    __tablename__ = "response_cache"

    prompt_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_version: Mapped[str] = mapped_column(String(120), primary_key=True)
    response: Mapped[dict] = mapped_column(JSONType())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (UniqueConstraint("run_id", "key", name="uq_metrics_run_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    key: Mapped[str] = mapped_column(Text)  # SCHEMA §2.4 namespace
    value: Mapped[float | None] = mapped_column(Float)
    ci_low: Mapped[float | None] = mapped_column(Float)
    ci_high: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict | None] = mapped_column(JSONType())


class Remediation(Base):
    __tablename__ = "remediations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected')", name="ck_remediations_status"
        ),  # SC-6
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))  # original catalog's product
    fixes: Mapped[list] = mapped_column(JSONType())  # array of §3.8 Fix objects
    status: Mapped[str] = mapped_column(Text, default="pending")
    reviewed_by: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created','captured','failed')", name="ck_payments_status"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    razorpay_link_id: Mapped[str | None] = mapped_column(Text, unique=True)
    amount_inr: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default="created")
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True)  # "agentaudit:{run_id}:{sku}"


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        CheckConstraint(
            "source IN ('razorpay','merchant_onboarding')", name="ck_webhook_events_source"
        ),
        UniqueConstraint("source", "type", "entity_key", name="uq_webhook_events_entity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    entity_key: Mapped[str] = mapped_column(Text)  # SC-1: extractor-defined dedupe key
    payload: Mapped[dict] = mapped_column(JSONType())
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
