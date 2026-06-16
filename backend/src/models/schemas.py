"""Pydantic schemas for API requests and responses."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── API Key schemas ──────────────────────────────────────────────────────────

class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    key: str = Field(..., min_length=10)
    is_active: bool = True
    is_default: bool = False


class APIKeyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class APIKeyPublic(BaseModel):
    id: str
    name: str
    masked_key: str
    is_active: bool
    is_default: bool
    usage_total_tokens: int
    usage_total_requests: int
    last_used_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class APIKeyList(BaseModel):
    keys: List[APIKeyPublic]


# ── Summarization schemas ────────────────────────────────────────────────────

class SummarizeRequest(BaseModel):
    table_text: str = Field(..., min_length=1)
    model: Optional[str] = None
    max_tokens: int = Field(1024, ge=1, le=8192)
    temperature: float = Field(0.0, ge=0.0, le=2.0)


class SummarizeResponse(BaseModel):
    summary: str
    model_used: str
    verified: bool
    numeric_accuracy: float
    inference_time_ms: float
    warnings: List[str]
    tokens_generated: Optional[int] = None
    extracted_facts: List[Dict[str, Any]] = []


# ── CSR schemas ──────────────────────────────────────────────────────────────

class CSRTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class CSRProgress(BaseModel):
    status: str
    stage: str
    progress: float
    current: int
    total: int
    message: str
    elapsed_seconds: float
    eta_seconds: float
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    active_keys: int
    total_keys: int
    default_model: str


# ── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


class UserResponse(BaseModel):
    id: str
    username: str

    class Config:
        from_attributes = True
