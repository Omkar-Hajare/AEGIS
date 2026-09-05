"""Pydantic response models for adaptive routes."""

from __future__ import annotations

from pydantic import BaseModel, Field

from contracts.schemas import Decision


class DecisionHistoryResponse(BaseModel):
    """Response envelope for recent adaptive decisions history."""

    decisions: list[Decision] = Field(
        default_factory=list,
        description="Array of recent adaptive Decision contracts, newest first",
    )
    count: int = Field(
        default=0,
        description="Total number of decisions returned in this response",
    )
