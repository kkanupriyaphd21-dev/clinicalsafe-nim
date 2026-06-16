"""Per-key usage event tracking."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.database import UsageEvent


class UsageTracker:
    def __init__(self, db: Session):
        self.db = db

    def log_event(
        self,
        api_key_id: str,
        endpoint: str,
        model: Optional[str],
        status: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: float = 0.0,
        error_message: Optional[str] = None,
    ) -> UsageEvent:
        event = UsageEvent(
            api_key_id=api_key_id,
            endpoint=endpoint,
            model=model,
            status=status,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            error_message=error_message,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_usage_for_key(
        self,
        key_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        query = self.db.query(UsageEvent).filter(UsageEvent.api_key_id == key_id)
        if start:
            query = query.filter(UsageEvent.created_at >= start)
        if end:
            query = query.filter(UsageEvent.created_at <= end)
        events = query.order_by(UsageEvent.created_at.desc()).all()
        return [
            {
                "id": e.id,
                "endpoint": e.endpoint,
                "model": e.model,
                "status": e.status,
                "prompt_tokens": e.prompt_tokens,
                "completion_tokens": e.completion_tokens,
                "total_tokens": e.total_tokens,
                "latency_ms": e.latency_ms,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ]

    def get_aggregates_for_key(self, key_id: str) -> Dict[str, Any]:
        result = self.db.query(
            func.count(UsageEvent.id).label("total_requests"),
            func.sum(UsageEvent.total_tokens).label("total_tokens"),
            func.sum(UsageEvent.prompt_tokens).label("prompt_tokens"),
            func.sum(UsageEvent.completion_tokens).label("completion_tokens"),
        ).filter(UsageEvent.api_key_id == key_id).first()

        return {
            "total_requests": result.total_requests or 0,
            "total_tokens": result.total_tokens or 0,
            "prompt_tokens": result.prompt_tokens or 0,
            "completion_tokens": result.completion_tokens or 0,
        }
