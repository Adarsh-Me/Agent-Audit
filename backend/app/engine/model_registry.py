"""Model registry — loads and boot-validates engine/models.yaml (SCHEMA §4.1)."""
from pathlib import Path

import yaml
from pydantic import BaseModel

from app.constants import BULK_MODEL_COUNT, FLAGSHIP_MODEL_COUNT


class ModelEntry(BaseModel):
    id: str
    openrouter_id: str
    version: str
    json_mode: bool = True
    seed_supported: bool = False


class ModelRegistry(BaseModel):
    bulk: list[ModelEntry]
    flagship: list[ModelEntry]

    def snapshot(self) -> dict:
        """runs.models payload — SCHEMA §3.4."""
        return {
            "bulk": [m.model_dump() for m in self.bulk],
            "flagship": [m.model_dump() for m in self.flagship],
        }

    def by_id(self, model_id: str) -> ModelEntry:
        for m in self.bulk + self.flagship:
            if m.id == model_id:
                return m
        raise KeyError(f"unknown model id: {model_id}")


def load_model_registry(path: Path | None = None) -> ModelRegistry:
    path = path or Path(__file__).parent / "models.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    reg = ModelRegistry(**data)
    if len(reg.bulk) != BULK_MODEL_COUNT:
        raise ValueError(f"models.yaml must define exactly {BULK_MODEL_COUNT} bulk models")
    if len(reg.flagship) != FLAGSHIP_MODEL_COUNT:
        raise ValueError(f"models.yaml must define exactly {FLAGSHIP_MODEL_COUNT} flagship models")
    ids = [m.id for m in reg.bulk + reg.flagship]
    if len(set(ids)) != len(ids):
        raise ValueError("models.yaml contains duplicate engine ids")
    return reg
