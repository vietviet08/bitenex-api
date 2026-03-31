import json
from functools import lru_cache
from typing import Any
import firebase_admin
from firebase_admin import credentials
from app.core.config import get_settings


@lru_cache
def get_firebase_app() -> Any:
    """
    Lazily initialize Firebase Admin.

    Supports either:
    - FIREBASE_CREDENTIALS_PATH
    - FIREBASE_CREDENTIALS_JSON
    - Application Default Credentials if neither is provided
    """
    settings = get_settings()

    if firebase_admin._apps:
        return firebase_admin.get_app()

    options: dict[str, Any] = {}
    if settings.firebase_project_id:
        options["projectId"] = settings.firebase_project_id

    if settings.firebase_credentials_json:
        certificate_payload = json.loads(settings.firebase_credentials_json)
        cred = credentials.Certificate(certificate_payload)
        return firebase_admin.initialize_app(cred, options=options or None)

    if settings.firebase_credentials_path:
        cred = credentials.Certificate(settings.firebase_credentials_path)
        return firebase_admin.initialize_app(cred, options=options or None)

    return firebase_admin.initialize_app(options=options or None)
