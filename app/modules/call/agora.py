import logging
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)

ROLE_UIDS = {
    "USER": 1,
    "DRIVER": 2,
}


def agora_uid_for_role(role: str) -> int:
    return ROLE_UIDS[role]


def generate_rtc_token(channel_name: str, role: str) -> tuple[str, datetime, int, str]:
    settings = get_settings()
    if not settings.agora_app_id:
        raise ServiceUnavailableError(message="Agora app id is not configured")

    uid = agora_uid_for_role(role)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.agora_token_ttl_seconds)
    privilege_expired_ts = int(expires_at.timestamp())

    if settings.agora_app_certificate:
        try:
            from agora_token_builder import RtcTokenBuilder

            token = RtcTokenBuilder.buildTokenWithUid(
                settings.agora_app_id,
                settings.agora_app_certificate,
                channel_name,
                uid,
                1,
                privilege_expired_ts,
            )
            return token, expires_at, uid, settings.agora_app_id
        except Exception as exc:
            if settings.is_production:
                raise ServiceUnavailableError(message="Could not generate Agora token") from exc
            logger.warning("agora.token_builder_failed using dev token: %s", exc)

    if settings.is_production:
        raise ServiceUnavailableError(message="Agora app certificate is not configured")

    return f"dev-token-{channel_name}-{uid}-{privilege_expired_ts}", expires_at, uid, settings.agora_app_id
