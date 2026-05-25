"""Regenerate scripts/seed_data/contracts.json from scratch using Claude.

By default we use the STATIC seed file at scripts/seed_data/contracts.json
(see ADR-0001: deterministic demos, zero API cost). This script is an escape
hatch — only run it if you intentionally want to refresh the seed.

Run (will OVERWRITE contracts.json):
    uv run python scripts/generate_contracts.py --confirm

Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("generate_contracts")

CONTRACTS_JSON = Path(__file__).resolve().parent / "seed_data" / "contracts.json"

GENERATION_MODEL = "claude-opus-4-7"

SUPPLIERS_TO_GENERATE = [
    {"supplier": "GE Vernova", "category": "Power_Transformer_Large", "pricing": "fully_indexed"},
    {"supplier": "Siemens Energy", "category": "Power_Transformer_GSU", "pricing": "hybrid_cap_floor"},
    {"supplier": "Hitachi Energy", "category": "Power_Transformer_HVDC_Converter", "pricing": "fully_indexed_steel_heavy"},
    {"supplier": "Hyundai Electric", "category": "Power_Transformer_Large", "pricing": "fixed_with_escalation"},
    {"supplier": "Hyosung Heavy Industries", "category": "Power_Transformer_Spot_OneOff", "pricing": "fixed_spot_premium"},
    {"supplier": "Eaton", "category": "Power_Transformer_Distribution", "pricing": "indexed_cu_al"},
    {"supplier": "Mitsubishi Electric", "category": "Power_Transformer_Large", "pricing": "option_reservation"},
    {"supplier": "WEG", "category": "Power_Transformer_Large", "pricing": "indexed_with_fx"},
]

PROMPT_TEMPLATE = """You are a senior procurement counsel drafting a power transformer supply contract.

Generate a JSON object representing ONE contract with realistic clause prose AND structured parsed_params.

Required clause types (include 4-6): indexation, escalation, force_majeure, ld, slot, incoterms,
delivery_obligation, heavy_lift.

Each clause must include:
- clause_type (one of the above)
- references_commodities (array; can be empty)
- text (1-2 paragraphs of realistic contract prose)
- parsed_params (machine-readable structured params used by the contract scanner)

Contract context:
  Supplier: {supplier}
  Category: {category}
  Pricing model: {pricing}

Return ONLY valid JSON matching this shape (no markdown fences):
{{
  "external_id": "CIS-2026-XXX",
  "supplier_name": "...",
  "category": "...",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "total_value_usd": NUMBER,
  "metadata": {{"voltage_classes": [...], "annual_volume_units": N, "pricing_model": "...", "currency": "USD"}},
  "clauses": [...]
}}
"""


async def generate_one(idx: int, spec: dict) -> dict:
    # Lazy-import so --help / --confirm check works without env vars set.
    from apps.api.budget import budgeted_client

    prompt = PROMPT_TEMPLATE.format(**spec)
    response = await budgeted_client.messages_create(
        model=GENERATION_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    obj = json.loads(text)
    obj["external_id"] = f"CIS-2026-{idx:03d}"
    obj["supplier_name"] = spec["supplier"]
    logger.info("Generated contract %s — %s", obj["external_id"], spec["supplier"])
    return obj


async def main_async() -> int:
    contracts = []
    for i, spec in enumerate(SUPPLIERS_TO_GENERATE, start=1):
        contracts.append(await generate_one(i, spec))

    payload = {
        "_meta": {
            "generated": "regenerated via generate_contracts.py",
            "generator": GENERATION_MODEL,
            "count": len(contracts),
            "note": "Auto-generated. Review carefully before committing.",
        },
        "contracts": contracts,
    }
    CONTRACTS_JSON.write_text(json.dumps(payload, indent=2))
    logger.info("Wrote %d contracts to %s", len(contracts), CONTRACTS_JSON)
    return 0


def main() -> int:
    if "--confirm" not in sys.argv:
        print(__doc__)
        print("Refusing to overwrite contracts.json without --confirm flag.")
        print("Per ADR-0001 the static file is the source of truth.")
        return 2
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
