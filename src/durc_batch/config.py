"""Configurazione centralizzata e tipata (pydantic-settings).

>>> Questo file E' IL PANNELLO DI CONFIGURAZIONE dell'applicativo. <<<

Tutti i parametri si impostano nel file `.env` (vedi `.env.example`), SENZA mai
toccare il codice. Questo modulo e' gia' implementato in Fase 1 (infrastruttura):
la Fase 2 (Coder) NON deve modificarlo, deve solo leggere i valori da qui.

Per verificare cosa e' configurato e cosa manca, eseguire:  python -m durc_batch.doctor
"""
from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Radice del progetto (...\pdnd), usata per risolvere i percorsi relativi del .env.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Carica e valida la configurazione dal file `.env` (prefisso `PDND_`).

    I campi senza default vanno valorizzati nel .env perche' il sistema funzioni;
    quelli con default (endpoint di produzione, parametri operativi) sono gia'
    pronti e si sovrascrivono solo se necessario (es. per l'ambiente di collaudo).
    """
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="PDND_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Campi che l'utente DEVE compilare a mano nel .env (usati dal `doctor`).
    REQUIRED_USER_FIELDS: ClassVar[tuple[str, ...]] = (
        "client_id", "kid", "durc_base_url", "durc_purpose_id", "durc_audience",
    )

    # --- Identita' client PDND (DA COMPILARE) ---
    client_id: str = ""                  # UUID del client registrato su PDND
    kid: str = ""                        # Key ID della chiave pubblica caricata su PDND
    private_key_path: Path = Path("keys/private_key.pem")  # basta posizionare il file qui

    # --- Endpoint PDND (default = PRODUZIONE; sovrascrivere per UAT/collaudo) ---
    token_endpoint: str = "https://auth.interop.pagopa.it/token.oauth2"
    auth_audience: str = "auth.interop.pagopa.it/client-assertion"

    # --- E-service DURC (DA COMPILARE: specifici dell'e-service sul catalogo) ---
    durc_base_url: str = ""              # base URL e-service esposto sul catalogo
    durc_purpose_id: str = ""            # UUID della finalita' (purpose) abilitata
    durc_audience: str = ""              # audience dichiarata nel descrittore e-service

    # --- Parametri operativi (default sensati) ---
    rate_limit_per_second: float = 5.0
    rate_limit_burst: int = 10
    assertion_ttl_seconds: int = 600
    max_retries: int = 5
    poll_interval_seconds: int = 60
    poll_max_attempts: int = 20

    # --- I/O e logging ---
    input_csv: Path = Path("data/input/codici_fiscali.csv")
    output_dir: Path = Path("data/output")
    log_dir: Path = Path("logs")
    log_level: str = "INFO"
    state_db_url: str = "sqlite:///data/state.db"

    @field_validator("private_key_path", "input_csv", "output_dir", "log_dir",
                     mode="after")
    @classmethod
    def _resolve_relative(cls, value: Path) -> Path:
        """Risolve i percorsi relativi rispetto alla radice del progetto, cosi'
        l'app funziona da qualunque working directory (locale o container)."""
        return value if value.is_absolute() else (PROJECT_ROOT / value)

    def missing_user_fields(self) -> list[str]:
        """Elenco dei campi obbligatori ancora vuoti nel .env (vuoto = tutto ok)."""
        return [name for name in self.REQUIRED_USER_FIELDS if not getattr(self, name)]

    def is_ready(self) -> bool:
        """True se tutti i campi obbligatori sono valorizzati."""
        return not self.missing_user_fields()


@lru_cache
def get_settings() -> Settings:
    """Factory singleton: carica (una sola volta) le impostazioni dal `.env`."""
    return Settings()
