"""models.yaml boot validation (TECHSPEC §3.2 / SCHEMA §4.1)."""
import pytest

from app.constants import BULK_MODEL_IDS, FLAGSHIP_MODEL_IDS
from app.engine.model_registry import load_model_registry


def test_registry_loads_with_exact_counts():
    reg = load_model_registry()
    assert [m.id for m in reg.bulk] == list(BULK_MODEL_IDS)
    assert [m.id for m in reg.flagship] == list(FLAGSHIP_MODEL_IDS)


def test_registry_snapshot_shape():
    snap = load_model_registry().snapshot()
    assert set(snap) == {"bulk", "flagship"}
    assert len(snap["bulk"]) == 3 and len(snap["flagship"]) == 2
    for entry in snap["bulk"] + snap["flagship"]:
        assert {"id", "openrouter_id", "version"} <= set(entry)
        assert entry["version"] and not entry["version"].startswith("<")


def test_duplicate_ids_rejected(tmp_path):
    bad = tmp_path / "models.yaml"
    bad.write_text(
        """
bulk:
  - id: a
    openrouter_id: x/a
    version: "1"
  - id: a
    openrouter_id: x/a2
    version: "2"
  - id: b
    openrouter_id: x/b
    version: "3"
flagship:
  - id: c
    openrouter_id: x/c
    version: "4"
  - id: d
    openrouter_id: x/d
    version: "5"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_model_registry(bad)
