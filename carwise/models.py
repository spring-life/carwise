from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Source(BaseModel):
    title: str
    url: HttpUrl
    observed_on: date


class VehicleVariant(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    market: str
    make: str
    model: str
    year: int = Field(ge=1990, le=2100)
    trim: str
    image_url: HttpUrl | None = None
    powertrain: str | None = None
    msrp: int | None = Field(default=None, ge=0)
    currency: str | None = None
    fuel_consumption: float | None = Field(default=None, ge=0)
    fuel_unit: str | None = None
    fuel_standard: str | None = None
    features: dict[str, str | float | bool | None] = Field(default_factory=dict)
    sources: dict[str, Source] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_provenance(self) -> "VehicleVariant":
        if "specs" not in self.sources:
            raise ValueError("A vehicle variant requires an official specs source")
        if self.msrp is not None and (not self.currency or "price" not in self.sources):
            raise ValueError("MSRP requires currency and price source")
        if self.fuel_consumption is not None and (
            not self.fuel_unit or not self.fuel_standard or "fuel" not in self.sources
        ):
            raise ValueError("Fuel consumption requires unit, standard, and source")
        return self

    @property
    def label(self) -> str:
        return f"{self.make} {self.model} {self.year} {self.trim}"


class DocumentRecord(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str
    source_url: HttpUrl
    source_type: Literal["official", "recall", "review", "owner_report"]
    published_on: date | None = None
    market: str
    vehicle_ids: list[str] = Field(default_factory=list)
    applies_to_make: str | None = None
    path: str
    page_ranges: list[tuple[int, int]] = Field(default_factory=list)
    content_selector: str | None = None

    @model_validator(mode="after")
    def validate_page_ranges(self) -> "DocumentRecord":
        if any(start < 1 or end < start for start, end in self.page_ranges):
            raise ValueError("Page ranges must use positive, increasing PDF page numbers")
        return self


class CompareRequest(BaseModel):
    vehicle_ids: list[str] = Field(min_length=2, max_length=3)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    vehicle_ids: list[str] = Field(default_factory=list, max_length=3)


class Citation(BaseModel):
    id: str
    document_id: str
    title: str
    url: HttpUrl
    source_type: str
    published_on: date | None
    location: str | None
    excerpt: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    mode: Literal["evidence_selected", "retrieval_only", "no_evidence"]


class ExtractRequest(BaseModel):
    document_id: str
    page_number: int = Field(ge=1)


class ExtractedFact(BaseModel):
    fact_type: Literal["故障信号", "风险", "建议操作", "保养周期", "配置说明"]
    quote: str


class ExtractResponse(BaseModel):
    document_id: str
    title: str
    page_number: int
    source_url: HttpUrl
    facts: list[ExtractedFact]
    mode: Literal["extracted", "no_facts", "model_unavailable"]

