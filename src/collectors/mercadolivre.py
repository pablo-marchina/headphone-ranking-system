"""Mercado Livre price collector.

Uses the official Mercado Livre API (developers.mercadolivre.com.br).
The collector reads only the fixed environment variables:

- MERCADOLIVRE_ACCESS_TOKEN
- MERCADOLIVRE_REFRESH_TOKEN
- MERCADOLIVRE_CLIENT_ID
- MERCADOLIVRE_CLIENT_SECRET

When an access token is expired, the collector attempts a one-time refresh and
keeps the renewed token in memory for the current process only.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from .base import BaseCollector

log = logging.getLogger(__name__)

ML_API_URL = "https://api.mercadolibre.com/sites/MLB/search"
ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"


class MercadoLivrePriceCollector(BaseCollector):
    source_name = "mercadolivre"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._runtime_access_token: Optional[str] = None
        self.last_api_status: Optional[int] = None
        self.last_failure_reason: Optional[str] = None
        self.last_failure_payload: Optional[str] = None
        self.last_refresh_status: Optional[str] = None

    def is_available(self) -> bool:
        return True

    @staticmethod
    def _env(name: str) -> str:
        return os.getenv(name, "").strip()

    def _credentials(self) -> dict[str, str]:
        return {
            "access_token": self._runtime_access_token or self._env("MERCADOLIVRE_ACCESS_TOKEN"),
            "refresh_token": self._env("MERCADOLIVRE_REFRESH_TOKEN"),
            "client_id": self._env("MERCADOLIVRE_CLIENT_ID"),
            "client_secret": self._env("MERCADOLIVRE_CLIENT_SECRET"),
        }

    def _auth_headers(self) -> dict[str, str]:
        token = self._credentials()["access_token"]
        return {"Authorization": f"Bearer {token}"} if token else {}

    def _classify_failure(self, response, payload: Any = None) -> str:
        if response is None:
            return "sem_resposta"
        status = getattr(response, "status_code", None)
        if status == 401:
            return "401"
        if status == 403:
            return "403"
        if status == 404:
            return "404"
        if payload is None:
            return "payload_invalido"
        if not isinstance(payload, dict):
            return "payload_invalido"
        if "results" not in payload:
            return "payload_invalido"
        return "unknown"

    def _log_failure(self, name: str, reason: str, response=None, payload: Any = None) -> None:
        self.last_api_status = getattr(response, "status_code", None)
        self.last_failure_reason = reason
        if payload is None:
            self.last_failure_payload = None
        else:
            text = str(payload)
            self.last_failure_payload = text[:500]
        log.warning(
            "[mercadolivre] event=fetch_failed query=%s reason=%s status=%s",
            name,
            reason,
            self.last_api_status,
        )

    def _log_attempt(self, name: str, stage: str) -> None:
        log.debug("[mercadolivre] event=search_attempt query=%s stage=%s", name, stage)

    def _refresh_access_token(self) -> bool:
        creds = self._credentials()
        if not creds["refresh_token"] or not creds["client_id"] or not creds["client_secret"]:
            self.last_refresh_status = "missing_credentials"
            log.warning("[mercadolivre] event=token_refresh_failed reason=missing_credentials")
            return False

        log.info("[mercadolivre] event=token_refresh_attempt status=start")
        response = self._request(
            ML_TOKEN_URL,
            method="POST",
            headers={},
            data={
                "grant_type": "refresh_token",
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
                "refresh_token": creds["refresh_token"],
            },
        )
        if response is None:
            self.last_refresh_status = "sem_resposta"
            log.warning("[mercadolivre] event=token_refresh_failed reason=sem_resposta")
            return False

        try:
            payload = response.json()
        except Exception:
            self.last_refresh_status = "payload_invalido"
            log.warning("[mercadolivre] event=token_refresh_failed reason=payload_invalido status=%s", getattr(response, "status_code", None))
            return False

        access_token = str(payload.get("access_token", "")).strip()
        if not access_token:
            self.last_refresh_status = "payload_invalido"
            log.warning("[mercadolivre] event=token_refresh_failed reason=payload_invalido status=%s", getattr(response, "status_code", None))
            return False

        self._runtime_access_token = access_token
        self.last_refresh_status = "refreshed"
        log.info("[mercadolivre] event=token_refreshed status=success")
        return True

    def _search(self, name: str, limit: int, *, use_auth: bool = True) -> tuple[Optional[list[dict[str, Any]]], Optional[str]]:
        params = {
            "q": name,
            "limit": max(1, min(limit, 50)),
            "offset": 0,
        }
        self._log_attempt(name, "initial")
        headers = self._auth_headers() if use_auth else {}
        response = self._request(ML_API_URL, params=params, headers=headers)
        if response is None:
            reason = self._classify_failure(None)
            self._log_failure(name, reason)
            return None, reason

        self.last_api_status = response.status_code
        try:
            payload = response.json()
        except Exception:
            try:
                payload = None if not response.text else {"raw": response.text}
            except Exception:
                payload = None

        if not payload or not isinstance(payload, dict) or "results" not in payload:
            reason = self._classify_failure(response, payload)
            self._log_failure(name, reason, response=response, payload=payload)
            return None, reason

        results: list[dict[str, Any]] = []
        for item in payload.get("results", []):
            price = self._safe_float(item.get("price"))
            if price is None or price <= 0:
                continue
            title = str(item.get("title", ""))
            results.append(self.build_price_candidate(
                name,
                price_brl=float(price),
                title=title,
                url=item.get("permalink", ""),
                seller=str(item.get("seller", {}).get("nickname", "")),
                availability="available" if item.get("available_quantity", 0) else "unknown",
                condition=str(item.get("condition", "unknown")),
                source_name="mercadolivre_api" if use_auth else "mercadolivre_public",
                source_type="official_api" if use_auth else "structured_search",
            ))

        self.last_failure_reason = None
        self.last_failure_payload = None
        return results if results else None, None

    def fetch(self, name: str, **kwargs) -> list[dict[str, Any]] | None:
        try:
            limit = int(kwargs.get("limit", 10))
        except Exception:
            limit = 10

        self.last_api_status = None
        self.last_failure_reason = None
        self.last_failure_payload = None
        self.last_refresh_status = None

        results, reason = self._search(name, limit, use_auth=True)
        if results is not None:
            log.debug("[mercadolivre] %s: %d results", name, len(results))
            return results

        if reason == "401":
            log.info("[mercadolivre] event=auth_retry query=%s status=401", name)
            log.warning("[mercadolivre] event=auth_invalid_or_expired query=%s", name)
        if reason == "403":
            log.warning("[mercadolivre] event=auth_blocked query=%s status=403", name)
            return None
        if reason == "401" and self._refresh_access_token():
            self._log_attempt(name, "retry_after_refresh")
            results, reason = self._search(name, limit, use_auth=True)
            if results is not None:
                log.debug("[mercadolivre] %s: %d results after refresh", name, len(results))
                return results
            log.warning(
                "[mercadolivre] event=auth_retry_failed query=%s reason=%s status=%s",
                name,
                reason,
                self.last_api_status,
            )
        return None

    def diagnose(self, query: str = "Sennheiser HD 600", limit: int = 5) -> dict[str, Any]:
        creds = self._credentials()
        response = self._request(ML_API_URL, params={"q": query, "limit": limit, "offset": 0}, headers=self._auth_headers())
        status = getattr(response, "status_code", None)
        snippet = ""
        search_failure_reason = None
        if response is not None:
            try:
                snippet = response.text[:300]
            except Exception:
                snippet = ""
            try:
                payload = response.json()
            except Exception:
                payload = None
            if not isinstance(payload, dict) or "results" not in payload:
                search_failure_reason = self._classify_failure(response, payload)
        else:
            search_failure_reason = self._classify_failure(response)
        refresh_ok = None
        if creds["refresh_token"] and creds["client_id"] and creds["client_secret"]:
            refresh_ok = self._refresh_access_token()
        return {
            "variables": {
                "MERCADOLIVRE_ACCESS_TOKEN": bool(creds["access_token"]),
                "MERCADOLIVRE_REFRESH_TOKEN": bool(creds["refresh_token"]),
                "MERCADOLIVRE_CLIENT_ID": bool(creds["client_id"]),
                "MERCADOLIVRE_CLIENT_SECRET": bool(creds["client_secret"]),
            },
            "search_status": status,
            "search_failure_reason": search_failure_reason,
            "search_snippet": snippet,
            "refresh_status": self.last_refresh_status if refresh_ok is not None else "missing_credentials",
            "refresh_ok": refresh_ok,
        }


def fetch_br_prices_list(headphone_name, **kwargs):
    collector = MercadoLivrePriceCollector()
    try:
        data = collector.fetch(headphone_name, **kwargs)
        if data is None:
            return None
        return [float(item["price_brl"]) for item in data]
    except Exception as exc:
        log.debug("[mercadolivre] fetch_br_prices_list error for '%s': %s", headphone_name, exc)
        return None
