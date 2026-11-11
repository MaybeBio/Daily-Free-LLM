from __future__ import annotations

import time

from ..registry import provider_index


class Router:
    def __init__(
        self,
        registry: dict,
        aliases: dict | None = None,
        config: dict | None = None,
        status: dict | None = None,
        budgets=None,
    ) -> None:
        self.registry = registry
        self.providers = provider_index(registry)
        source = aliases or {}
        self.aliases = {**(source.get("aliases") or {}), **(source.get("manual") or {})}
        self.config = config or {}
        self.status = (status or {}).get("providers", {})
        self.budgets = budgets
        self.priority = {
            pid: index for index, pid in enumerate(self.config.get("priority", []))
        }
        self.max_candidates = int(self.config.get("max_candidates", 6))
        self.cooldown_seconds = float(self.config.get("cooldown_seconds", 60))
        self.cooldowns: dict[str, float] = {}

    def _cooldown_ok(self, provider_id: str) -> bool:
        until = self.cooldowns.get(provider_id, 0)
        return until <= time.monotonic()

    def _provider_healthy(self, provider_id: str) -> bool:
        entry = self.status.get(provider_id) or {}
        return entry.get("status") not in {"auth_error", "not_found"}

    def _model_status(self, provider_id: str, model_id: str) -> dict:
        entry = self.status.get(provider_id) or {}
        return (entry.get("models") or {}).get(model_id, {})

    def _provider_status(self, provider_id: str) -> str | None:
        return (self.status.get(provider_id) or {}).get("status")

    def _candidate(self, provider_id: str, model_id: str) -> dict | None:
        provider = self.providers.get(provider_id)
        if not provider or not provider.get("gateway"):
            return None
        if not self._cooldown_ok(provider_id) or not self._provider_healthy(provider_id):
            return None
        model = next((m for m in provider.get("models", []) if m["id"] == model_id), None)
        if not model:
            return None
        model_status = (self._model_status(provider_id, model_id) or {}).get("status")
        if model_status in {"auth_error", "not_found"}:
            return None
        provider_status = self._provider_status(provider_id)
        if self.budgets and not self.budgets.allow(provider_id, provider.get("limits")):
            return None
        return {
            "provider": provider_id,
            "provider_name": provider.get("name", provider_id),
            "model": model_id,
            "base_url": provider.get("base_url", "").rstrip("/"),
            "env": provider.get("env", ""),
            "keyless": bool(provider.get("keyless")),
            "headers": provider.get("headers") or {},
            "status": model_status or provider_status or provider.get("status") or "untested",
            "latency_ms": (self._model_status(provider_id, model_id) or {}).get("latency_ms"),
            "tools": model.get("tools"),
            "context": model.get("context"),
            "priority": self.priority.get(provider_id, 999),
        }

    def _best_model_for(self, provider: dict) -> str | None:
        models = [
            model for model in (provider.get("models") or [])
            if (self._model_status(provider["id"], model["id"]) or {}).get("status")
            not in {"auth_error", "not_found"}
        ]
        if not models:
            return None

        def score(model: dict) -> tuple:
            status = (self._model_status(provider["id"], model["id"]) or {}).get("status")
            return (
                1 if status == "ok" else 0,
                1 if model.get("tools") else 0,
                model.get("context") or 0,
            )

        return max(models, key=score)["id"]

    def candidates(self, requested: str | None = None) -> list[dict]:
        requested = (requested or self.config.get("default_model") or "auto").strip()
        found: list[dict] = []
        seen: set[tuple[str, str]] = set()

        def add(provider_id: str, model_id: str) -> None:
            key = (provider_id, model_id)
            if key in seen:
                return
            candidate = self._candidate(provider_id, model_id)
            if candidate:
                seen.add(key)
                found.append(candidate)

        if "/" in requested and not requested.startswith("auto"):
            provider_id, model_id = requested.split("/", 1)
            add(provider_id, model_id)
        elif requested == "auto":
            for provider in self.providers.values():
                if not provider.get("gateway"):
                    continue
                model_id = self._best_model_for(provider)
                if model_id:
                    add(provider["id"], model_id)
        elif requested in self.aliases:
            for item in self.aliases[requested]:
                add(item.get("provider"), item.get("model"))
        else:
            for provider in self.providers.values():
                if not provider.get("gateway"):
                    continue
                if any(m["id"] == requested for m in provider.get("models", [])):
                    add(provider["id"], requested)

        found.sort(
            key=lambda c: (
                0 if c["status"] == "ok" else 1,
                c["priority"],
                c["latency_ms"] if c["latency_ms"] is not None else 99999,
                -(c["context"] or 0),
            )
        )
        return found[: self.max_candidates]

    def mark(self, provider_id: str, status: str, retry_after: float | None = None) -> None:
        if status in {"ok"}:
            self.cooldowns.pop(provider_id, None)
            return
        if status in {"rate_limited", "server_error", "network_error", "auth_error"}:
            seconds = retry_after if retry_after and retry_after > 0 else self.cooldown_seconds
            self.cooldowns[provider_id] = time.monotonic() + float(seconds)

    def record(
        self,
        provider_id: str,
        model: str,
        status: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        if self.budgets:
            self.budgets.record(
                provider_id, model, status, prompt_tokens, completion_tokens
            )
