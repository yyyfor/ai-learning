"""Lab 7 endpoints: pure computation over the posted records, nothing is stored."""
from fastapi import APIRouter

from app.dto.refinement import ContradictionsRequest, DuplicatesRequest, ResolveRequest
from app.refinement.entity_resolution import (Claim, EntityRecord, find_conflicts,
                                              near_duplicates, resolve)

router = APIRouter(prefix="/refinement", tags=["Lab 7 Refinement"])


@router.post("/entities/resolve")
async def resolve_entities(payload: ResolveRequest):
    records = [EntityRecord(**record.model_dump()) for record in payload.records]
    return resolve(records, payload.aliases)


@router.post("/duplicates")
async def duplicates(payload: DuplicatesRequest):
    return near_duplicates(payload.documents, payload.threshold)


@router.post("/contradictions")
async def contradictions(payload: ContradictionsRequest):
    return find_conflicts([Claim(**claim.model_dump()) for claim in payload.claims])
