"""Entrypoint CLI: compone le dipendenze (wiring) e avvia il batch."""
import sys

import requests

from durc_batch.api.durc_client import DurcApiClient
from durc_batch.auth.client_assertion import ClientAssertionGenerator
from durc_batch.auth.voucher_manager import VoucherManager
from durc_batch.batch.processor import BatchProcessor
from durc_batch.batch.reader import CsvCodiceFiscaleReader
from durc_batch.batch.repository import StateRepository
from durc_batch.config import Settings, get_settings
from durc_batch.core.logging_conf import get_logger, setup_logging
from durc_batch.core.rate_limiter import RateLimiter


def build_processor(settings: Settings) -> BatchProcessor:
    """Compone (dependency injection manuale) tutte le dipendenze e ritorna il
    BatchProcessor pronto all'uso. Condiviso da CLI (`main`) e interfaccia web."""
    session = requests.Session()
    generator = ClientAssertionGenerator(
        client_id=settings.client_id,
        kid=settings.kid,
        private_key_path=settings.private_key_path,
        audience=settings.auth_audience,
        ttl_seconds=settings.assertion_ttl_seconds,
    )
    voucher_manager = VoucherManager(
        generator, settings.token_endpoint, settings.client_id, session)
    rate_limiter = RateLimiter(
        settings.rate_limit_per_second, settings.rate_limit_burst)
    durc_client = DurcApiClient(settings.durc_base_url, session, rate_limiter)
    reader = CsvCodiceFiscaleReader(settings.input_csv)
    repository = StateRepository(settings.state_db_url)
    return BatchProcessor(
        settings, reader, voucher_manager, durc_client, repository)


def main() -> None:
    """Configura il logging, istanzia Settings, costruisce il BatchProcessor
    (via `build_processor`) e invoca processor.run()."""
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_dir)
    logger = get_logger(__name__)

    if not settings.is_ready():
        logger.error(
            "Configurazione incompleta: %s. Esegui 'python -m durc_batch.doctor'.",
            ", ".join(settings.missing_user_fields()),
        )
        sys.exit(1)

    processor = build_processor(settings)

    logger.info("Avvio batch DURC (input=%s)", settings.input_csv)
    try:
        processor.run()
    except Exception:
        logger.exception("Errore fatale durante l'esecuzione del batch")
        sys.exit(1)
    logger.info("Batch DURC terminato")


if __name__ == "__main__":
    main()
