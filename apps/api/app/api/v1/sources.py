"""API endpoints for news source management."""

import uuid
from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin, require_user
from app.models.models import Source, User
from app.schemas.source import SourceCreate, SourceResponse, SourceUpdate
from app.workers.tasks import ingest_news_task

router = APIRouter()


@router.get("", response_model=List[SourceResponse])
async def list_sources(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve news sources."""
    stmt = select(Source)
    if active_only:
        stmt = stmt.where(Source.active == True)
    
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(require_admin),
):
    """Create a new news source (Admin only)."""
    # Check if slug exists
    stmt = select(Source).where(Source.slug == payload.slug)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source with this slug already exists.",
        )

    source = Source(
        id=uuid.uuid4(),
        **payload.model_dump()
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get source by ID."""
    stmt = select(Source).where(Source.id == source_id)
    res = await db.execute(stmt)
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )
    return source


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: uuid.UUID,
    payload: SourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(require_admin),
):
    """Update a news source (Admin only)."""
    stmt = select(Source).where(Source.id == source_id)
    res = await db.execute(stmt)
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, val)

    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(require_admin),
):
    """Deactivate or delete a news source (Admin only)."""
    stmt = select(Source).where(Source.id == source_id)
    res = await db.execute(stmt)
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source not found.",
        )

    # Instead of deleting raw, deactivate the source to preserve article integrity
    source.active = False
    await db.commit()


@router.post("/trigger-ingestion", status_code=status.HTTP_202_ACCEPTED)
async def trigger_ingestion(
    current_user: Any = Depends(require_user),
):
    """Manually trigger the news ingestion task.
    
    Can be run by any authenticated user for testing purposes.
    """
    task = ingest_news_task.delay()
    return {"message": "Ingestion task queued.", "task_id": task.id}
