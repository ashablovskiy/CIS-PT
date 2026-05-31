"""Per-source ingestion agents."""

from apps.api.ingest.sources.demand_agent import DemandAgent
from apps.api.ingest.sources.gdelt_agent import GdeltAgent
from apps.api.ingest.sources.ir_agent import IrAgent
from apps.api.ingest.sources.logistics_agent import LogisticsAgent
from apps.api.ingest.sources.press_agent import PressAgent
from apps.api.ingest.sources.prices_agent import PricesAgent
from apps.api.ingest.sources.sec_agent import SecAgent

__all__ = [
    "DemandAgent",
    "GdeltAgent",
    "IrAgent",
    "LogisticsAgent",
    "PressAgent",
    "PricesAgent",
    "SecAgent",
]
