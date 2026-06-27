from app.config import get_settings
from app.schemas import ApiStatusResponse
from app.services.demo_pack_loader import is_demo_mode_active
from app.services.integration_health_service import get_integration_health


async def build_api_status_response(*, probe: bool = False) -> ApiStatusResponse:
    settings = get_settings()
    demo_active = is_demo_mode_active()
    missing = settings.missing_keys()
    integrations = await get_integration_health(probe=probe)

    return ApiStatusResponse(
        gemini=bool(settings.gemini_api_key),
        tavily=bool(settings.tavily_api_key),
        slng=bool(settings.slng_api_key),
        mubit=bool(settings.mubit_api_key),
        missing_keys=[] if demo_active else missing,
        allow_demo_fallback=settings.allow_demo_fallback or demo_active,
        demo_mode=settings.demo_mode or None,
        integrations=integrations,
    )
