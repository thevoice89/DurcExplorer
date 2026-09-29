"""Generazione della Client Assertion JWT firmata RSA (RFC 7521 / RFC 7523).

Pattern di riferimento: italia/pdnd-client-assertion-generator.
"""
import time
import uuid
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from durc_batch.core.logging_conf import get_logger

logger = get_logger(__name__)


class ClientAssertionGenerator:
    """Costruisce e firma il JWT (RS256) da inviare al token endpoint PDND."""

    def __init__(self, client_id: str, kid: str, private_key_path: Path,
                 audience: str, ttl_seconds: int) -> None:
        """Carica la chiave privata RSA (PEM) e memorizza i parametri di firma."""
        self._client_id = client_id
        self._kid = kid
        self._audience = audience
        self._ttl_seconds = ttl_seconds
        # La chiave privata resta in memoria; non viene mai loggata.
        self._private_key = load_pem_private_key(
            Path(private_key_path).read_bytes(), password=None,
        )

    def build(self, purpose_id: str) -> str:
        """Genera la client assertion firmata.

        Header:  {alg: RS256, kid: <kid>, typ: JWT}
        Claims:  iss=sub=<client_id>, aud=<audience>, jti=<uuid4 univoco>,
                 iat=now, exp=now+ttl, purposeId=<purpose_id>.
        Ritorna il JWT compatto (stringa) firmato con la chiave privata.
        """
        issued_at = int(time.time())
        jti = str(uuid.uuid4())
        payload = {
            "iss": self._client_id,
            "sub": self._client_id,
            "aud": self._audience,
            "jti": jti,
            "iat": issued_at,
            "exp": issued_at + self._ttl_seconds,
            "purposeId": purpose_id,
        }
        headers = {"kid": self._kid, "typ": "JWT"}
        token = jwt.encode(payload, self._private_key, algorithm="RS256",
                           headers=headers)
        logger.debug("Client assertion generata (jti=%s, purposeId=%s)",
                     jti, purpose_id)
        return token
