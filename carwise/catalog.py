from __future__ import annotations

import json
from pathlib import Path
import re

from .models import VehicleVariant


class Catalog:
    def __init__(self, variants: list[VehicleVariant]):
        ids = [variant.id for variant in variants]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate vehicle variant ID")
        self._by_id = {variant.id: variant for variant in variants}

    @classmethod
    def from_file(cls, path: Path) -> "Catalog":
        if not path.exists():
            return cls([])
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Catalog must be a JSON array")
        return cls([VehicleVariant.model_validate(item) for item in data])

    def list(self) -> list[VehicleVariant]:
        return sorted(self._by_id.values(), key=lambda v: (v.market, v.make, v.model, v.year, v.trim))

    def get(self, vehicle_id: str) -> VehicleVariant:
        try:
            return self._by_id[vehicle_id]
        except KeyError as exc:
            raise ValueError(f"Unknown vehicle variant: {vehicle_id}") from exc

    def compare(self, vehicle_ids: list[str]) -> list[VehicleVariant]:
        if len(vehicle_ids) < 2 or len(vehicle_ids) > 3 or len(set(vehicle_ids)) != len(vehicle_ids):
            raise ValueError("Select 2 or 3 distinct variants")
        vehicles = [self.get(vehicle_id) for vehicle_id in vehicle_ids]
        if len({vehicle.market for vehicle in vehicles}) != 1:
            raise ValueError("Variants from different markets cannot be compared")
        return vehicles

    def scope_for_question(self, question: str, selected_ids: list[str]) -> list[str]:
        variants = [self.get(vehicle_id) for vehicle_id in selected_ids] if selected_ids else self.list()
        normalized = re.sub(r"[\s\-]", "", question).upper()
        models = {variant.model for variant in self._by_id.values()}
        mentioned_models = {
            model for model in models
            if re.sub(r"[\s\-]", "", model.split(" DM-")[0]).upper() in normalized
        }
        if mentioned_models:
            variants = [variant for variant in variants if variant.model in mentioned_models]
        years = {int(year) for year in re.findall(r"(20\d{2})\s*款", question)}
        if years:
            variants = [variant for variant in variants if variant.year in years]
        known_trims = {variant.trim for variant in self._by_id.values()}
        mentioned_trims = {trim for trim in known_trims if re.sub(r"\s", "", trim).upper() in normalized}
        if mentioned_trims:
            variants = [variant for variant in variants if variant.trim in mentioned_trims]
        return [variant.id for variant in variants]

