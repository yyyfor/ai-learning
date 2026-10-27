"""Voice APIs share the application's authentication; no database credentials in UI."""
import logging
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.dto.voice import TranscriptionResponse, VoiceSummaryRequest, VoiceSummaryResponse
from app.services.voice import VoiceService, VoiceUnavailable

router = APIRouter(prefix="/voice", tags=["Lab 13 · Local voice"])
logger = logging.getLogger("knowledge_api")


def get_voice(request: Request) -> VoiceService:
    return request.app.state.voice


@router.get("/status")
async def status(service: VoiceService = Depends(get_voice)):
    return await service.status()


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(file: UploadFile = File(...), language: Literal["auto", "en", "zh"] = Form("auto"),
                     service: VoiceService = Depends(get_voice)):
    try:
        data = await file.read(3 * 1024 * 1024 + 1)
    finally:
        await file.close()
    if len(data) > 3 * 1024 * 1024:
        raise HTTPException(413, "Audio chunk must be at most 3 MiB and 30 seconds.")
    try:
        return await run_in_threadpool(service.transcribe, data, language)
    except VoiceUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.warning("voice_transcription_failed type=%s", type(exc).__name__)
        raise HTTPException(503, "Local transcription failed. Retry the pending audio chunk.") from exc


@router.post("/summary", response_model=VoiceSummaryResponse)
async def summarize(payload: VoiceSummaryRequest, service: VoiceService = Depends(get_voice)):
    try:
        return await service.summarize(payload.transcript, payload.language)
    except VoiceUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Summary model unavailable. Check local Ollama and VOICE_SUMMARY_MODEL.") from exc
    except (ValidationError, KeyError, ValueError) as exc:
        raise HTTPException(502, "The local model returned incomplete notes. Try again or shorten the transcript.") from exc
