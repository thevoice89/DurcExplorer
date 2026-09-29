"""Configurazione del logging applicativo (file + console, formato strutturato)."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_CONFIGURED = False


def setup_logging(level: str = "INFO", log_dir: Path = Path("logs")) -> None:
    """Configura i logger root: handler su file (in `log_dir`) e su console, con
    formato strutturato (timestamp, livello, modulo, messaggio). NON deve mai
    emettere in chiaro chiavi private, JWT firmati o access_token."""
    global _CONFIGURED
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level.upper())

    # Evita handler duplicati se setup_logging viene invocato piu' volte.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = RotatingFileHandler(
        log_dir / "durc_batch.log", maxBytes=5_000_000, backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Ritorna un logger applicativo coerente con la configurazione globale."""
    return logging.getLogger(name)
