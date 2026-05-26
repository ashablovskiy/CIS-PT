"""Admin API routes for managing prompt templates.

GET  /api/prompts               — list all prompts (latest active version per name)
GET  /api/prompts/{name}        — get full version history for a prompt
GET  /api/prompts/{name}/active — get the active version text
PUT  /api/prompts/{name}        — publish a new version and set it active
POST /api/prompts/{name}/rollback/{version} — roll back to a previous version
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from apps.api.db.models import PromptTemplate
from apps.api.db.session import async_session_factory
from apps.api.prompts.registry import registry

router = APIRouter()


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class PromptSummary(BaseModel):
    name: str
    version: int
    description: str | None
    model_hint: str | None
    is_active: bool
    created_by: str
    created_at: datetime


class PromptDetail(PromptSummary):
    system_text: str
    metrics: dict[str, Any] | None


class PromptUpdateRequest(BaseModel):
    system_text: str
    description: str | None = None
    created_by: str = "admin"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[PromptSummary])
async def list_prompts():
    """List all prompt names with their currently active version."""
    async with async_session_factory() as session:
        rows = await session.execute(
            select(PromptTemplate)
            .where(PromptTemplate.is_active == True)  # noqa: E712
            .order_by(PromptTemplate.name)
        )
        templates = rows.scalars().all()

    return [
        PromptSummary(
            name=t.name,
            version=t.version,
            description=t.description,
            model_hint=t.model_hint,
            is_active=t.is_active,
            created_by=t.created_by,
            created_at=t.created_at,
        )
        for t in templates
    ]


@router.get("/{name}", response_model=list[PromptDetail])
async def get_prompt_history(name: str):
    """Return all versions of a prompt, newest first."""
    async with async_session_factory() as session:
        rows = await session.execute(
            select(PromptTemplate)
            .where(PromptTemplate.name == name)
            .order_by(PromptTemplate.version.desc())
        )
        templates = rows.scalars().all()

    if not templates:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")

    return [
        PromptDetail(
            name=t.name,
            version=t.version,
            system_text=t.system_text,
            description=t.description,
            model_hint=t.model_hint,
            is_active=t.is_active,
            metrics=t.metrics,
            created_by=t.created_by,
            created_at=t.created_at,
        )
        for t in templates
    ]


@router.get("/{name}/active", response_model=PromptDetail)
async def get_active_prompt(name: str):
    """Return the currently active version of a prompt."""
    async with async_session_factory() as session:
        row = await session.execute(
            select(PromptTemplate)
            .where(PromptTemplate.name == name, PromptTemplate.is_active == True)  # noqa: E712
        )
        template = row.scalar_one_or_none()

    if not template:
        raise HTTPException(status_code=404, detail=f"No active prompt for '{name}'")

    return PromptDetail(
        name=template.name,
        version=template.version,
        system_text=template.system_text,
        description=template.description,
        model_hint=template.model_hint,
        is_active=template.is_active,
        metrics=template.metrics,
        created_by=template.created_by,
        created_at=template.created_at,
    )


@router.put("/{name}", response_model=PromptDetail)
async def update_prompt(name: str, body: PromptUpdateRequest):
    """Publish a new version of a prompt and set it as active.

    The previous active version is deactivated but preserved for rollback.
    The in-memory registry is force-reloaded immediately.
    """
    async with async_session_factory() as session:
        # Deactivate current active version
        current = await session.execute(
            select(PromptTemplate)
            .where(PromptTemplate.name == name, PromptTemplate.is_active == True)  # noqa: E712
        )
        for t in current.scalars():
            t.is_active = False

        # Find the highest version number
        latest = await session.execute(
            select(PromptTemplate)
            .where(PromptTemplate.name == name)
            .order_by(PromptTemplate.version.desc())
            .limit(1)
        )
        latest_row = latest.scalar_one_or_none()
        next_version = (latest_row.version + 1) if latest_row else 1

        # Get model_hint from existing row or leave None
        model_hint = latest_row.model_hint if latest_row else None
        description = body.description or (latest_row.description if latest_row else None)

        new_template = PromptTemplate(
            name=name,
            version=next_version,
            system_text=body.system_text,
            description=description,
            model_hint=model_hint,
            is_active=True,
            created_by=body.created_by,
        )
        session.add(new_template)
        await session.commit()
        await session.refresh(new_template)

    # Reload cache so next LLM call picks up the new text immediately
    await registry.areload()

    return PromptDetail(
        name=new_template.name,
        version=new_template.version,
        system_text=new_template.system_text,
        description=new_template.description,
        model_hint=new_template.model_hint,
        is_active=new_template.is_active,
        metrics=new_template.metrics,
        created_by=new_template.created_by,
        created_at=new_template.created_at,
    )


@router.post("/{name}/rollback/{version}", response_model=PromptDetail)
async def rollback_prompt(name: str, version: int):
    """Roll back to a previous version by setting it as active.

    The currently active version is deactivated. Registry is reloaded.
    """
    async with async_session_factory() as session:
        # Find the target version
        target = await session.execute(
            select(PromptTemplate)
            .where(PromptTemplate.name == name, PromptTemplate.version == version)
        )
        target_row = target.scalar_one_or_none()
        if not target_row:
            raise HTTPException(
                status_code=404,
                detail=f"Prompt '{name}' version {version} not found",
            )

        # Deactivate all versions for this name
        all_versions = await session.execute(
            select(PromptTemplate).where(PromptTemplate.name == name)
        )
        for t in all_versions.scalars():
            t.is_active = False

        # Activate the target
        target_row.is_active = True
        await session.commit()
        await session.refresh(target_row)

    await registry.areload()

    return PromptDetail(
        name=target_row.name,
        version=target_row.version,
        system_text=target_row.system_text,
        description=target_row.description,
        model_hint=target_row.model_hint,
        is_active=target_row.is_active,
        metrics=target_row.metrics,
        created_by=target_row.created_by,
        created_at=target_row.created_at,
    )
