import asyncio
import os
import time
from pathlib import Path
from typing import Any

import httpx
from google import genai
from mubit import Client
from tavily import TavilyClient

from app.config import get_settings
from app.constants.integrations import (
    INTEGRATION_AIKIDO,
    INTEGRATION_GEMINI,
    INTEGRATION_HEALTH_CACHE_TTL_SEC,
    INTEGRATION_MUBIT,
    INTEGRATION_SLNG,
    INTEGRATION_STATUS_CI_ONLY,
    INTEGRATION_STATUS_ERROR,
    INTEGRATION_STATUS_MISSING_KEY,
    INTEGRATION_STATUS_OK,
    INTEGRATION_TAVILY,
)
from app.constants.slng import SLNG_DEFAULT_TTS_MODEL, SLNG_TTS_ENDPOINT
from app.schemas import IntegrationHealthItem
from app.services.demo_pack_loader import is_demo_mode_active

_HEALTH_CACHE: dict[str, Any] | None = None
_HEALTH_CACHE_AT: float = 0.0


def _sanitize_error_message(error: Exception) -> str:
    message = str(error).strip() or error.__class__.__name__
    if len(message) > 180:
        return f"{message[:177]}..."
    return message


def _aikido_workflow_present() -> bool:
    workflow_path = (
        Path(__file__).resolve().parents[3]
        / ".github"
        / "workflows"
        / "aikido-security.yml"
    )
    return workflow_path.exists()


async def _probe_gemini(api_key: str) -> tuple[bool, str]:
    def list_models() -> str:
        client = genai.Client(api_key=api_key)
        model_names = [model.name for model in client.models.list() if model.name]
        if not model_names:
            raise RuntimeError("Gemini returned no models for this API key")
        return f"Connected — {len(model_names)} models available"

    message = await asyncio.to_thread(list_models)
    return True, message


async def _probe_tavily(api_key: str) -> tuple[bool, str]:
    def search_once() -> str:
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query="EditDNA integration health check",
            search_depth="basic",
            max_results=1,
        )
        result_count = len(response.get("results", []))
        return f"Connected — search returned {result_count} result(s)"

    message = await asyncio.to_thread(search_once)
    return True, message


async def _probe_slng(api_key: str, base_url: str) -> tuple[bool, str]:
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}{SLNG_TTS_ENDPOINT}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"text": "Integration check.", "model": SLNG_DEFAULT_TTS_MODEL},
        )
        response.raise_for_status()
        if not response.content:
            raise RuntimeError("SLNG TTS returned an empty response body")
        return True, f"Connected — TTS returned {len(response.content)} bytes"


async def _probe_mubit(api_key: str, endpoint: str, transport: str) -> tuple[bool, str]:
    def write_probe() -> str:
        client = Client(
            api_key=api_key,
            run_id="integration-health-check",
            endpoint=endpoint,
            transport=transport,
        )
        result = client.remember(
            session_id="integration-health-check",
            agent_id="integration_health",
            user_id="integration-health-check",
            content="EditDNA integration health probe",
            intent="fact",
            lesson_scope="session",
            metadata={"probe": True, "source": "integration_health_service"},
        )
        if isinstance(result, dict) and result.get("job_id"):
            return "Connected — memory write accepted"
        return "Connected — memory client responded"

    message = await asyncio.to_thread(write_probe)
    return True, message


async def _build_integration_health_items(*, skip_live_probes: bool) -> list[IntegrationHealthItem]:
    settings = get_settings()
    demo_active = is_demo_mode_active()
    items: list[IntegrationHealthItem] = []

    key_by_integration = {
        INTEGRATION_GEMINI: settings.gemini_api_key,
        INTEGRATION_TAVILY: settings.tavily_api_key,
        INTEGRATION_SLNG: settings.slng_api_key,
        INTEGRATION_MUBIT: settings.mubit_api_key,
    }
    labels = {
        INTEGRATION_GEMINI: "Gemini (DeepMind)",
        INTEGRATION_TAVILY: "Tavily",
        INTEGRATION_SLNG: "SLNG",
        INTEGRATION_MUBIT: "Mubit",
        INTEGRATION_AIKIDO: "Aikido Security",
    }

    probes = {
        INTEGRATION_GEMINI: lambda key: _probe_gemini(key),
        INTEGRATION_TAVILY: lambda key: _probe_tavily(key),
        INTEGRATION_SLNG: lambda key: _probe_slng(key, settings.slng_base_url),
        INTEGRATION_MUBIT: lambda key: _probe_mubit(
            key,
            settings.mubit_endpoint,
            settings.mubit_transport,
        ),
    }

    for integration_id in (
        INTEGRATION_GEMINI,
        INTEGRATION_TAVILY,
        INTEGRATION_SLNG,
        INTEGRATION_MUBIT,
    ):
        api_key = key_by_integration[integration_id]
        configured = bool(api_key)
        if not configured:
            items.append(
                IntegrationHealthItem(
                    id=integration_id,
                    label=labels[integration_id],
                    configured=False,
                    reachable=False,
                    status=INTEGRATION_STATUS_MISSING_KEY,
                    message="API key not configured in .env",
                    optional_in_demo=demo_active,
                )
            )
            continue

        if skip_live_probes:
            items.append(
                IntegrationHealthItem(
                    id=integration_id,
                    configured=True,
                    label=labels[integration_id],
                    reachable=None,
                    status=INTEGRATION_STATUS_OK,
                    message="Configured — run with ?probe=true for live check",
                    optional_in_demo=demo_active,
                )
            )
            continue

        try:
            reachable, message = await probes[integration_id](api_key)
            probe_message = (
                f"{message} (optional while demo mode is active)"
                if demo_active
                else message
            )
            items.append(
                IntegrationHealthItem(
                    id=integration_id,
                    label=labels[integration_id],
                    configured=True,
                    reachable=reachable,
                    status=INTEGRATION_STATUS_OK,
                    message=probe_message,
                    optional_in_demo=demo_active,
                )
            )
        except Exception as error:
            items.append(
                IntegrationHealthItem(
                    id=integration_id,
                    label=labels[integration_id],
                    configured=True,
                    reachable=False,
                    status=INTEGRATION_STATUS_ERROR,
                    message=_sanitize_error_message(error),
                    optional_in_demo=demo_active,
                )
            )

    aikido_secret_present = bool(os.getenv("AIKIDO_SECRET_KEY"))
    aikido_workflow_present = _aikido_workflow_present()
    if aikido_workflow_present:
        aikido_message = (
            "GitHub Actions workflow ready — AIKIDO_SECRET_KEY is set"
            if aikido_secret_present
            else "GitHub Actions workflow ready — add AIKIDO_SECRET_KEY repository secret"
        )
        items.append(
            IntegrationHealthItem(
                id=INTEGRATION_AIKIDO,
                label=labels[INTEGRATION_AIKIDO],
                configured=aikido_secret_present,
                reachable=aikido_secret_present,
                status=INTEGRATION_STATUS_CI_ONLY,
                message=aikido_message,
                optional_in_demo=False,
            )
        )

    return items


async def get_integration_health(*, probe: bool = False, force_refresh: bool = False) -> list[IntegrationHealthItem]:
    global _HEALTH_CACHE, _HEALTH_CACHE_AT

    cache_key = "probe" if probe else "configured"
    now = time.monotonic()
    if (
        not force_refresh
        and _HEALTH_CACHE is not None
        and _HEALTH_CACHE.get("key") == cache_key
        and now - _HEALTH_CACHE_AT < INTEGRATION_HEALTH_CACHE_TTL_SEC
    ):
        return list(_HEALTH_CACHE["items"])

    items = await _build_integration_health_items(skip_live_probes=not probe)
    _HEALTH_CACHE = {"key": cache_key, "items": items}
    _HEALTH_CACHE_AT = now
    return items
