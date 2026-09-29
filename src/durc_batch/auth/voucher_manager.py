"""Richiesta e caching del Voucher PDND (OAuth2 client_credentials)."""
from datetime import datetime, timedelta, timezone

import requests

from durc_batch.auth.client_assertion import ClientAssertionGenerator
from durc_batch.core.exceptions import AuthenticationError
from durc_batch.core.logging_conf import get_logger
from durc_batch.models import Voucher

logger = get_logger(__name__)


class VoucherManager:
    """Ottiene il voucher dal token endpoint PDND e lo cacheha per purposeId."""

    CLIENT_ASSERTION_TYPE = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
    GRANT_TYPE = "client_credentials"

    def __init__(self, generator: ClientAssertionGenerator, token_endpoint: str,
                 client_id: str, session: requests.Session) -> None:
        """Inizializza il manager con il generatore di assertion e la sessione HTTP."""
        self._generator = generator
        self._token_endpoint = token_endpoint
        self._client_id = client_id
        self._session = session
        self._cache: dict[str, Voucher] = {}

    def get_voucher(self, purpose_id: str) -> Voucher:
        """Ritorna un voucher valido per il purpose: usa la cache se non scaduto,
        altrimenti ne richiede uno nuovo via `_request_voucher`."""
        cached = self._cache.get(purpose_id)
        if cached is not None and not cached.is_expired():
            logger.debug("Voucher cache hit (purposeId=%s)", purpose_id)
            return cached
        logger.info("Voucher cache miss/refresh (purposeId=%s)", purpose_id)
        voucher = self._request_voucher(purpose_id)
        self._cache[purpose_id] = voucher
        return voucher

    def _request_voucher(self, purpose_id: str) -> Voucher:
        """POST application/x-www-form-urlencoded al token endpoint con:
        client_id, client_assertion, client_assertion_type, grant_type.
        Mappa la risposta JSON (access_token/expires_in) su un Voucher."""
        assertion = self._generator.build(purpose_id)
        data = {
            "grant_type": self.GRANT_TYPE,
            "client_assertion_type": self.CLIENT_ASSERTION_TYPE,
            "client_assertion": assertion,
            "client_id": self._client_id,
        }
        try:
            response = self._session.post(
                self._token_endpoint, data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.error("Richiesta voucher fallita (purposeId=%s): %s",
                         purpose_id, exc)
            raise AuthenticationError(f"Richiesta voucher fallita: {exc}") from exc
        except ValueError as exc:
            raise AuthenticationError(f"Risposta voucher non JSON: {exc}") from exc

        try:
            expires_in = int(payload["expires_in"])
            voucher = Voucher(
                access_token=payload["access_token"],
                token_type=payload.get("token_type", "Bearer"),
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError(
                f"Risposta voucher priva dei campi attesi: {exc}") from exc

        logger.info("Voucher ottenuto (scade tra %ss, voucher=***)", expires_in)
        return voucher
