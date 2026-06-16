"""NVIDIA NIM client with automatic key rotation."""
import json
import logging
import time
from typing import Dict, List, Optional, Tuple

import requests
from sqlalchemy.orm import Session

from src.models.database import APIKey
from src.services.key_vault import KeyVault
from src.services.usage_tracker import UsageTracker
from src.utils.config import settings

logger = logging.getLogger(__name__)


class NIMClientError(Exception):
    pass


class NIMClient:
    def __init__(self, db: Session):
        self.db = db
        self.vault = KeyVault(db)
        self.tracker = UsageTracker(db)
        self.base_url = settings.nvidia_nim_base_url
        self.timeout = settings.nim_timeout_seconds

    def _headers(self, api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _active_key_records(self) -> List[APIKey]:
        return self.vault.get_active_keys()

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        top_p: float = 1.0,
        endpoint_label: str = "chat_completion",
    ) -> Tuple[Dict, str]:
        """
        Send a chat completion request to NVIDIA NIM, rotating keys on failure.
        Returns (response_data, api_key_id_used).
        """
        records = self._active_key_records()
        if not records:
            raise NIMClientError("No active NVIDIA API keys in vault. Add a key first.")

        model = model or settings.nim_default_model
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": False,
        }

        last_error = None
        for record in records:
            start = time.time()
            try:
                key = self.vault.get_decrypted_key(record.id)
                if not key:
                    continue

                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(key),
                    json=payload,
                    timeout=self.timeout,
                )
                latency_ms = round((time.time() - start) * 1000, 2)

                if resp.status_code == 200:
                    data = resp.json()
                    usage = data.get("usage", {})
                    self.vault.record_usage(
                        record.id,
                        usage.get("prompt_tokens", 0),
                        usage.get("completion_tokens", 0),
                    )
                    self.tracker.log_event(
                        api_key_id=record.id,
                        endpoint=endpoint_label,
                        model=model,
                        status="success",
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        total_tokens=usage.get("total_tokens", 0),
                        latency_ms=latency_ms,
                    )
                    return data, record.id

                # Handle auth / quota / rate-limit errors by rotating
                if resp.status_code == 401:
                    logger.warning(f"Key {record.id} unauthorized; deactivating.")
                    self.vault.deactivate_key(record.id)
                    self.tracker.log_event(
                        api_key_id=record.id,
                        endpoint=endpoint_label,
                        model=model,
                        status="unauthorized",
                        latency_ms=latency_ms,
                        error_message="401 Unauthorized",
                    )
                    last_error = NIMClientError("NVIDIA NIM: Invalid API key (401 Unauthorized)")
                elif resp.status_code == 402:
                    logger.warning(f"Key {record.id} payment required; deactivating.")
                    self.vault.deactivate_key(record.id)
                    self.tracker.log_event(
                        api_key_id=record.id,
                        endpoint=endpoint_label,
                        model=model,
                        status="payment_required",
                        latency_ms=latency_ms,
                        error_message="402 Payment required",
                    )
                    last_error = NIMClientError("NVIDIA NIM: Payment required — check API credits")
                elif resp.status_code == 429:
                    retry_after = 60
                    try:
                        retry_after = int(resp.headers.get("Retry-After", 60))
                    except Exception:
                        pass
                    logger.warning(f"Key {record.id} rate limited; placing on cool-down for {retry_after}s.")
                    self.vault.cooldown_key(record.id, retry_after)
                    self.tracker.log_event(
                        api_key_id=record.id,
                        endpoint=endpoint_label,
                        model=model,
                        status="rate_limited",
                        latency_ms=latency_ms,
                        error_message=f"429 Rate limited (Retry-After: {retry_after}s)",
                    )
                    last_error = NIMClientError(f"NVIDIA NIM: Rate limited (Retry-After: {retry_after}s) — try again later")
                else:
                    text = resp.text
                    self.tracker.log_event(
                        api_key_id=record.id,
                        endpoint=endpoint_label,
                        model=model,
                        status="error",
                        latency_ms=latency_ms,
                        error_message=f"{resp.status_code}: {text[:500]}",
                    )
                    last_error = NIMClientError(f"NVIDIA NIM API error {resp.status_code}: {text}")

            except requests.exceptions.Timeout:
                latency_ms = round((time.time() - start) * 1000, 2)
                self.tracker.log_event(
                    api_key_id=record.id,
                    endpoint=endpoint_label,
                    model=model,
                    status="timeout",
                    latency_ms=latency_ms,
                    error_message=f"Timeout after {self.timeout}s",
                )
                last_error = NIMClientError(f"NVIDIA NIM API request timed out ({self.timeout}s)")
            except requests.exceptions.ConnectionError as exc:
                latency_ms = round((time.time() - start) * 1000, 2)
                self.tracker.log_event(
                    api_key_id=record.id,
                    endpoint=endpoint_label,
                    model=model,
                    status="connection_error",
                    latency_ms=latency_ms,
                    error_message=str(exc),
                )
                last_error = NIMClientError(f"Cannot connect to NVIDIA NIM API at {self.base_url}")
            except Exception as exc:
                latency_ms = round((time.time() - start) * 1000, 2)
                self.tracker.log_event(
                    api_key_id=record.id,
                    endpoint=endpoint_label,
                    model=model,
                    status="error",
                    latency_ms=latency_ms,
                    error_message=str(exc),
                )
                last_error = NIMClientError(f"Unexpected NIM client error: {exc}")

        raise last_error or NIMClientError("All active NVIDIA API keys failed.")
