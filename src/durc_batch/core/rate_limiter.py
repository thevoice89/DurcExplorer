"""Rate limiting interno (token bucket) per rispettare le quote PDND."""
from pyrate_limiter import Duration, Limiter, Rate


class RateLimiter:
    """Token bucket thread-safe: limita le chiamate uscenti verso l'e-service.

    Implementato con pyrate-limiter 4.x (API `Rate` + `Limiter.try_acquire`).
    """

    _BUCKET_NAME = "durc"

    def __init__(self, rate_per_second: float, burst: int) -> None:
        """Inizializza capienza (burst) e velocità di refill (rate_per_second)."""
        sustained = Rate(max(1, round(rate_per_second)), Duration.SECOND)
        # Il burst e' la massima raffica ammessa in una finestra di 1s: lo
        # esprimiamo come secondo Rate solo se piu' permissivo del sostenuto.
        rates = [sustained]
        if burst > sustained.limit:
            rates.append(Rate(burst, Duration.SECOND))
        self._limiter = Limiter(rates)

    def acquire(self, tokens: int = 1, block: bool = True) -> bool:
        """Consuma `tokens`; se block=True attende che si liberino, altrimenti
        ritorna False quando non disponibili."""
        return bool(self._limiter.try_acquire(
            self._BUCKET_NAME, weight=tokens, blocking=block,
        ))
