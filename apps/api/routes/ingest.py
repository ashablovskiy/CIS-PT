"""Manual signal ingestion — URL scrape and file upload.

Accepts a URL or a file (PDF, DOCX, image, plain text), extracts the text
content, and runs it through the full relevance-scoring + persist pipeline.

POST /api/ingest/url   {"url": "https://..."}
POST /api/ingest/file  multipart/form-data  field: file
"""
from __future__ import annotations

import hashlib
import io
import logging
import re
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi import File as FastFile
from pydantic import BaseModel

from apps.api.ingest.base import RawItem, ScoredItem
from apps.api.ingest.runner import BaseIngestionAgent, IngestionState

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Minimal agent subclass (reuses scorer + persist; no pull needed) ──────────

class _ManualAgent(BaseIngestionAgent):
    """Thin subclass that gives us access to _score_batch and _persist_signals."""

    @property
    def agent_name(self) -> str:            # type: ignore[override]
        return "manual"

    def keyword_rules(self) -> list[str]:
        # Accept everything the user manually adds — no pre-filter
        return []

    async def pull(self, window):
        return []

    async def run_on_items(self, items: list[RawItem]) -> list[ScoredItem]:
        """Score a list of pre-built RawItems and persist the ones that pass."""
        scored = await self._score_batch(items)
        # Apply routing threshold (same as BaseIngestionAgent._route_and_persist)
        to_persist = [s for s in scored if (s.llm_score or 0) >= 0.3]
        if to_persist:
            # Set decision field before persisting
            for s in to_persist:
                s.decision = "escalate" if (s.llm_score or 0) >= 0.6 else "review"
            await self._persist_signals(to_persist)
        return scored


_agent = _ManualAgent()


# ── Content extractors ────────────────────────────────────────────────────────

async def _extract_url(url: str) -> tuple[str, str]:
    """Fetch a URL and return (title, body_text)."""
    async with httpx.AsyncClient(
        headers={"User-Agent": "cis-research/0.1 a.shablovskiy@gmail.com"},
        follow_redirects=True,
        timeout=20,
    ) as client:
        r = await client.get(url)
        r.raise_for_status()
        ct = r.headers.get("content-type", "")
        if "text/html" not in ct and "text/plain" not in ct:
            raise HTTPException(400, f"Unsupported content-type: {ct}")
        html = r.text

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    # Remove script/style noise
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else url
    body = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
    return title, body[:8000]


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages[:30]]
    return re.sub(r"\s+", " ", " ".join(pages)).strip()[:8000]


def _extract_docx(data: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(data))
    text = " ".join(p.text for p in doc.paragraphs if p.text.strip())
    return re.sub(r"\s+", " ", text).strip()[:8000]


async def _extract_image(data: bytes, filename: str) -> str:
    """Use Claude Vision to describe an image."""
    import base64

    from apps.api.budget import budgeted_client

    ext = filename.rsplit(".", 1)[-1].lower()
    media_type = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif", "webp": "image/webp",
    }.get(ext, "image/jpeg")

    b64 = base64.standard_b64encode(data).decode()
    response = await budgeted_client.messages_create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64},
                },
                {
                    "type": "text",
                    "text": (
                        "You are extracting information from a document image for a "
                        "power transformer procurement intelligence system. "
                        "Describe what this image/document shows, focusing on any "
                        "information relevant to: supply chains, prices, logistics, "
                        "OEM manufacturers (Siemens Energy, Hitachi Energy, GE Vernova, "
                        "Hyundai Electric), steel/materials, grid infrastructure, or "
                        "demand signals. Be concise and factual."
                    ),
                },
            ],
        }],
    )
    return response.content[0].text.strip()


def _build_raw_item(source_url: str | None, title: str, body: str, filename: str | None = None) -> RawItem:
    payload: dict = {"title": title, "summary": body[:500], "full_text": body}
    if filename:
        payload["filename"] = filename
    source_id = hashlib.sha256((source_url or title or body[:64]).encode()).hexdigest()[:32]
    return RawItem(
        source="manual",
        source_id=f"manual:{source_id}",
        url=source_url,
        occurred_at=datetime.now(UTC),
        raw_payload=payload,
        content_hash=hashlib.sha256(body.encode()).hexdigest()[:32],
    )


def _format_scored(s: ScoredItem) -> dict:
    return {
        "relevance": round(s.llm_score or 0, 3),
        "tier": s.impact_tier,
        "impact_type": s.impact_type,
        "what_changed": s.what_changed,
        "mechanism": s.mechanism,
        "decision": s.decision,
        "persisted": s.decision in ("review", "escalate"),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

class UrlRequest(BaseModel):
    url: str


@router.post("/url")
async def ingest_url(body: UrlRequest) -> dict:
    """Fetch a URL, extract text, score and optionally persist as a signal."""
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    try:
        title, text = await _extract_url(url)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Failed to fetch URL: {e}") from e

    if len(text) < 50:
        raise HTTPException(422, "Page content too short to analyse")

    item = _build_raw_item(url, title, text)
    scored = await _agent.run_on_items([item])

    return {
        "source": "url",
        "url": url,
        "title": title,
        "excerpt": text[:300],
        "result": _format_scored(scored[0]) if scored else None,
    }


@router.post("/file")
async def ingest_file(file: UploadFile = FastFile(...)) -> dict:
    """Upload a file (PDF, DOCX, image, TXT), extract text, score as a signal."""
    MAX_SIZE = 20 * 1024 * 1024  # 20 MB
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(413, "File too large (max 20 MB)")

    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    ct = (file.content_type or "").lower()

    try:
        if ext == "pdf" or "pdf" in ct:
            text = _extract_pdf(data)
            title = filename
        elif ext in ("docx",) or "word" in ct or "openxmlformats" in ct:
            text = _extract_docx(data)
            title = filename
        elif ext in ("doc",):
            raise HTTPException(415, "Legacy .doc format not supported — please save as .docx")
        elif ext in ("txt", "md", "csv") or "text/plain" in ct:
            text = data.decode("utf-8", errors="replace")
            title = filename
        elif ext in ("jpg", "jpeg", "png", "gif", "webp") or "image/" in ct:
            text = await _extract_image(data, filename)
            title = f"Image: {filename}"
        else:
            raise HTTPException(415, f"Unsupported file type: {ext or ct}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("File extraction failed: %s", filename)
        raise HTTPException(422, f"Could not extract text: {e}") from e

    text = text.strip()
    if len(text) < 30:
        raise HTTPException(422, "Could not extract enough text from this file")

    item = _build_raw_item(None, title, text, filename=filename)
    scored = await _agent.run_on_items([item])

    return {
        "source": "file",
        "filename": filename,
        "title": title,
        "excerpt": text[:300],
        "result": _format_scored(scored[0]) if scored else None,
    }
