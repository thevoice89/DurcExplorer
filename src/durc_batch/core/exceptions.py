"""Gerarchia di eccezioni di dominio."""


class DurcBatchError(Exception):
    """Base per tutte le eccezioni applicative."""


class AuthenticationError(DurcBatchError):
    """Fallimento generazione client assertion o richiesta voucher."""


class RateLimitExceeded(DurcBatchError):
    """HTTP 429 dall'e-service; trasporta l'eventuale Retry-After."""

    def __init__(self, retry_after: float | None = None) -> None:
        """Memorizza il valore di Retry-After (secondi) per il backoff a monte."""
        self.retry_after = retry_after
        super().__init__(f"Rate limit 429 (retry_after={retry_after})")


class DurcApiError(DurcBatchError):
    """Errore non recuperabile dall'e-service DURC (4xx/5xx)."""
