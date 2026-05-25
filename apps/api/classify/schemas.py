"""Pydantic schemas for signal classification outputs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class EventClass(StrEnum):
    COMMODITY_PRICE_MOVE = "commodity_price_move"
    GEOPOLITICAL_DISRUPTION = "geopolitical_disruption"
    SUPPLIER_CAPACITY = "supplier_capacity"
    LOGISTICS_DISRUPTION = "logistics_disruption"
    REGULATORY_TRADE = "regulatory_trade"
    DEMAND_SURGE = "demand_surge"
    FINANCIAL_DISCLOSURE = "financial_disclosure"
    NATURAL_DISASTER = "natural_disaster"
    OTHER = "other"


class ImpactDimension(StrEnum):
    PRICE = "price"
    AVAILABILITY = "availability"
    LEAD_TIME = "lead_time"
    LOGISTICS = "logistics"
    REGULATORY = "regulatory"
    DEMAND = "demand"


class ClassificationResult(BaseModel):
    event_class: EventClass
    geo_tags: list[str] = Field(default_factory=list)
    graph_entities: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Map of entity type → list of entity names found in the signal",
    )
    commodities: list[str] = Field(default_factory=list)
    impact_dimensions: list[ImpactDimension] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class RelevanceScore(BaseModel):
    relevance: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
