from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from .errors import Stage, ValidationError


class TokenProvider(Protocol):
    def id_token(self, audience: str) -> str: ...


class StaticTokenProvider:
    def __init__(self, token_factory: Callable[[str], str]):
        self.audiences: list[str] = []
        self._token_factory = token_factory

    def id_token(self, audience: str) -> str:
        self.audiences.append(audience)
        try:
            token = self._token_factory(audience)
        except Exception as error:
            raise ValidationError(Stage.TOKEN_GENERATION, "ID token generation failed") from error
        if not token or not isinstance(token, str):
            raise ValidationError(Stage.TOKEN_GENERATION, "ID token generation returned no token")
        return token


class GoogleIDTokenProvider:
    """Mint a short-lived audience-bound token without creating a key."""

    def __init__(self, caller_service_account: str | None = None):
        self.caller_service_account = caller_service_account

    def id_token(self, audience: str) -> str:
        try:
            import google.auth
            from google.auth.transport.requests import Request
            from google.oauth2 import id_token
            from google.auth import impersonated_credentials

            request = Request()
            if self.caller_service_account:
                source, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
                target_credentials = impersonated_credentials.Credentials(
                    source_credentials=source,
                    target_principal=self.caller_service_account,
                    target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
                )
                delegated = impersonated_credentials.IDTokenCredentials(
                    target_credentials=target_credentials,
                    target_audience=audience,
                    include_email=True,
                )
                delegated.refresh(request)
                if not delegated.token:
                    raise RuntimeError("empty delegated token")
                return delegated.token

            return id_token.fetch_id_token(request, audience)
        except Exception as error:
            raise ValidationError(Stage.TOKEN_GENERATION, "audience-bound ID token generation failed") from error
