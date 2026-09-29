"""DTO di dominio ed enumerazioni di stato (state machine del batch)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum

from pydantic import BaseModel


class RequestStatus(str, Enum):
    """Stati possibili di una richiesta DURC nel ciclo di vita del batch."""
    PENDING = "PENDING"            # mai inviata
    SUBMITTED = "SUBMITTED"        # 202: istruttoria avviata, in coda polling
    COMPLETED = "COMPLETED"        # 200: esito disponibile e salvato
    RATE_LIMITED = "RATE_LIMITED"  # 429: da ritentare dopo backoff
    FAILED = "FAILED"              # errore non recuperabile


class Voucher(BaseModel):
    """Bearer token PDND con scadenza, cacheato per purposeId."""
    access_token: str
    token_type: str
    expires_at: datetime

    def is_expired(self, skew_seconds: int = 30) -> bool:
        """True se il voucher è scaduto (o entro lo skew di sicurezza)."""
        expires = self.expires_at
        if expires.tzinfo is None:                      # normalizza a UTC aware
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) >= expires - timedelta(seconds=skew_seconds)


class DurcRequest(BaseModel):
    """Unità di lavoro: un codice fiscale e il suo stato corrente."""
    codice_fiscale: str
    status: RequestStatus = RequestStatus.PENDING
    request_id: str | None = None        # id istruttoria restituito su 202
    attempts: int = 0
    last_error: str | None = None
    updated_at: datetime | None = None


class DurcResult(BaseModel):
    """Esito finale: metadati + riferimento al documento scaricato."""
    codice_fiscale: str
    esito: str | None = None             # es. REGOLARE / NON_REGOLARE
    document_path: str | None = None
    raw_payload: dict | None = None
