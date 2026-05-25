"""Seed the Postgres database with mocked contracts and clauses.

Reads scripts/seed_data/contracts.json and inserts into the `contracts` and
`contract_clauses` tables. Idempotent on `contracts.external_id` — re-runs
update existing rows and re-create their clauses.

Run (after applying migrations):
    uv run python scripts/seed_db.py

Requires DATABASE_URL (or DATABASE_SYNC_URL) in .env.
Per PROJECT_SPEC.md §7.2 / §7.3 and ADR-0001.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from decimal import Decimal
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from apps.api.db.models import Contract, ContractClause
from apps.api.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed_db")

CONTRACTS_JSON = Path(__file__).resolve().parent / "seed_data" / "contracts.json"


def _parse_date(s: str | None) -> dt.date | None:
    return dt.date.fromisoformat(s) if s else None


def upsert_contract(session: Session, payload: dict) -> Contract:
    """Insert or update a contract + replace its clauses."""
    ext_id = payload["external_id"]

    existing = session.execute(
        select(Contract).where(Contract.external_id == ext_id)
    ).scalar_one_or_none()

    contract_attrs = {
        "external_id": ext_id,
        "supplier_name": payload.get("supplier_name"),
        "category": payload.get("category"),
        "start_date": _parse_date(payload.get("start_date")),
        "end_date": _parse_date(payload.get("end_date")),
        "total_value_usd": (
            Decimal(str(payload["total_value_usd"]))
            if payload.get("total_value_usd") is not None
            else None
        ),
        "full_text": None,  # Composed-clauses model — no monolithic body.
        "metadata_": payload.get("metadata"),
    }

    if existing is None:
        contract = Contract(**contract_attrs)
        session.add(contract)
        session.flush()
        action = "INSERT"
    else:
        for k, v in contract_attrs.items():
            setattr(existing, k, v)
        contract = existing
        # Wipe existing clauses to fully replace.
        session.execute(
            delete(ContractClause).where(ContractClause.contract_id == contract.id)
        )
        session.flush()
        action = "UPDATE"

    for clause_payload in payload.get("clauses", []):
        clause = ContractClause(
            contract_id=contract.id,
            clause_type=clause_payload.get("clause_type"),
            text=clause_payload.get("text"),
            references_commodities=clause_payload.get("references_commodities") or [],
            parsed_params=clause_payload.get("parsed_params"),
            embedding=None,  # Filled in by classifier in Week 3.
        )
        session.add(clause)

    logger.info(
        "%s %s — %s — %d clauses",
        action,
        ext_id,
        payload.get("supplier_name"),
        len(payload.get("clauses", [])),
    )
    return contract


def main() -> int:
    if not CONTRACTS_JSON.exists():
        logger.error("contracts.json not found at %s", CONTRACTS_JSON)
        return 1

    data = json.loads(CONTRACTS_JSON.read_text())
    contracts_payload = data.get("contracts", [])
    if not contracts_payload:
        logger.error("No contracts in payload.")
        return 1

    # Use the SYNC URL for this script (asyncpg URL won't work with sync engine).
    engine = create_engine(settings.database_sync_url, future=True)
    try:
        with Session(engine) as session:
            for payload in contracts_payload:
                upsert_contract(session, payload)
            session.commit()
    except Exception as exc:
        logger.error("Seed failed: %s", exc)
        raise
    finally:
        engine.dispose()

    logger.info("══ Seeded %d contracts ══", len(contracts_payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
