"""DB layer tests — ORM/DDL parity intent + choice-semantics CHECK (C-2)."""
import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from app.db.models import Catalog, Merchant, Product, Run, Trial


async def _mk_catalog(db) -> str:
    merchant_id = (await db.execute(
        insert(Merchant).values(name="Test Merchant").returning(Merchant.id)
    )).scalar_one()
    catalog_id = (await db.execute(
        insert(Catalog).values(
            merchant_id=merchant_id, source="demo"
        ).returning(Catalog.id)
    )).scalar_one()
    return catalog_id


async def test_choice_semantics_check_rejects_forced_null(db):
    catalog_id = await _mk_catalog(db)
    run_id = (await db.execute(
        insert(Run).values(
            catalog_id=catalog_id,
            type="audit",
            status="done",
            models={"bulk": [], "flagship": []},
            seeds={},
        ).returning(Run.id)
    )).scalar_one()

    # parse_ok=true, null_allowed=false, choice=NULL → must violate C-2 CHECK
    with pytest.raises(IntegrityError):
        db.add(Trial(
            run_id=run_id,
            model="gpt4o-mini",
            model_version="test",
            persona_id="P01",
            condition="C3-A-s1",
            seed=1,
            presented_order=["sku_001"],
            choice=None,
            prompt_hash="a" * 64,
            null_allowed=False,
            parse_ok=True,
        ))
        await db.commit()


async def test_valid_trials_pass(db):
    catalog_id = await _mk_catalog(db)
    run_id = (await db.execute(
        insert(Run).values(
            catalog_id=catalog_id,
            type="audit",
            status="done",
            models={"bulk": [], "flagship": []},
            seeds={},
        ).returning(Run.id)
    )).scalar_one()

    # forced trial with a choice → legal
    db.add(Trial(
        run_id=run_id, model="gpt4o-mini", model_version="test",
        persona_id="P01", condition="C3-A-s1", seed=1,
        presented_order=["sku_001"], choice="sku_001",
        prompt_hash="b" * 64, null_allowed=False, parse_ok=True,
    ))
    # null-allowed decline → legal
    db.add(Trial(
        run_id=run_id, model="gpt4o-mini", model_version="test",
        persona_id="P04", condition="C1-s1", seed=2,
        presented_order=["sku_001"], choice=None,
        prompt_hash="c" * 64, null_allowed=True, parse_ok=True,
    ))
    # parse failure → legal regardless of null_allowed
    db.add(Trial(
        run_id=run_id, model="gpt4o-mini", model_version="test",
        persona_id="P02", condition="C2-s1", seed=3,
        presented_order=["sku_001"], choice=None,
        prompt_hash="d" * 64, null_allowed=False, parse_ok=False,
    ))
    await db.commit()
    assert True


async def test_product_tier_check_enforced(db):
    catalog_id = await _mk_catalog(db)
    db.add(Product(
        catalog_id=catalog_id, sku="sku_001", title="X", tier="bogus"
    ))
    with pytest.raises(IntegrityError):
        await db.commit()
