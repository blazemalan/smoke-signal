"""Data models for transcription results."""

from datetime import datetime

from pydantic import BaseModel


class Word(BaseModel):
    text: str
    start: float
    end: float
    confidence: float | None = None
    speaker: str | None = None


class Segment(BaseModel):
    text: str
    start: float
    end: float
    speaker: str | None = None
    words: list[Word] = []


class TranscriptResult(BaseModel):
    segments: list[Segment]
    speakers: list[str]
    language: str
    duration: float
    model: str
    pipeline: str
    processing_time: float
    audio_file: str
    date: datetime
