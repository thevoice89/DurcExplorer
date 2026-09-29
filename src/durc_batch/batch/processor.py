"""Orchestratore del batch: coordina auth, API, rate limiting e persistenza."""
import time

import requests

from durc_batch.api.durc_client import DurcApiClient
from durc_batch.auth.voucher_manager import VoucherManager
from durc_batch.batch.reader import CodiceFiscaleReader
from durc_batch.batch.repository import StateRepository
from durc_batch.config import Settings
from durc_batch.core.logging_conf import get_logger
from durc_batch.core.retry import with_backoff
from durc_batch.models import DurcRequest, RequestStatus

logger = get_logger(__name__)


class BatchProcessor:
    """Cuore applicativo: legge i CF, li elabora e gestisce la coda asincrona."""

    def __init__(self, settings: Settings, reader: CodiceFiscaleReader,
                 voucher_manager: VoucherManager, durc_client: DurcApiClient,
                 repository: StateRepository) -> None:
        """Inietta tutte le dipendenze necessarie all'orchestrazione."""
        self._settings = settings
        self._reader = reader
        self._voucher_manager = voucher_manager
        self._durc_client = durc_client
        self._repository = repository
        # Richiesta DURC avvolta dalla policy di retry/backoff (transitori/429).
        self._request_durc = with_backoff(settings.max_retries)(
            durc_client.request_durc)

    def run(self) -> None:
        """Primo passaggio: itera i CF, per ciascuno ottiene il voucher, chiama
        l'e-service e instrada l'esito via `_handle_response`. Poi invoca
        `poll_pending` per chiudere le istruttorie 202."""
        completed = {
            req.codice_fiscale
            for req in self._repository.get_by_status(RequestStatus.COMPLETED)
        }
        processed = 0
        for codice_fiscale in self._reader.read():
            if codice_fiscale in completed:
                logger.info("Salto CF=%s (gia' COMPLETED)", codice_fiscale)
                continue

            request = DurcRequest(codice_fiscale=codice_fiscale)
            try:
                voucher = self._voucher_manager.get_voucher(
                    self._settings.durc_purpose_id)
                response = self._request_durc(codice_fiscale, voucher)
            except Exception as exc:  # noqa: BLE001 - tracciamo qualsiasi errore
                logger.error("Errore richiesta DURC CF=%s: %s", codice_fiscale,
                             exc, exc_info=True)
                request.status = RequestStatus.FAILED
                request.attempts += 1
                request.last_error = str(exc)
                self._repository.upsert(request)
                continue

            self._handle_response(request, response)
            processed += 1

        logger.info("Primo passaggio completato (%d CF elaborati)", processed)
        self.poll_pending()

    def _handle_response(self, request: DurcRequest,
                         response: requests.Response) -> None:
        """State machine sul codice HTTP:
        200->COMPLETED (+download), 202->SUBMITTED (+request_id),
        429->RATE_LIMITED (+backoff Retry-After), altro->FAILED.
        Persiste sempre lo stato aggiornato via repository."""
        codice_fiscale = request.codice_fiscale
        status_code = response.status_code

        if status_code == 200:
            result = self._durc_client.download_document(
                response, codice_fiscale, str(self._settings.output_dir))
            request.status = RequestStatus.COMPLETED
            logger.info("CF=%s -> COMPLETED (esito=%s)", codice_fiscale,
                        result.esito)
        elif status_code == 202:
            request.request_id = self._extract_request_id(response)
            request.status = RequestStatus.SUBMITTED
            logger.info("CF=%s -> SUBMITTED (request_id=%s)", codice_fiscale,
                        request.request_id)
        elif status_code == 429:
            retry_after = response.headers.get("Retry-After")
            request.status = RequestStatus.RATE_LIMITED
            logger.warning("CF=%s -> RATE_LIMITED (Retry-After=%s)",
                           codice_fiscale, retry_after)
        else:
            request.status = RequestStatus.FAILED
            request.attempts += 1
            request.last_error = f"HTTP {status_code}: {response.text[:500]}"
            logger.error("CF=%s -> FAILED (status=%s)", codice_fiscale,
                         status_code)

        self._repository.upsert(request)

    @staticmethod
    def _extract_request_id(response: requests.Response) -> str | None:
        """Estrae l'identificativo dell'istruttoria da header o body del 202."""
        request_id = response.headers.get("Location") or response.headers.get(
            "X-Request-Id")
        if request_id:
            return request_id
        try:
            body = response.json()
        except ValueError:
            return None
        # TODO: verificare su OpenAPI e-service il nome del campo dell'id istruttoria.
        return body.get("requestId") or body.get("id")

    def poll_pending(self) -> None:
        """Secondo passaggio: per ogni richiesta SUBMITTED esegue polling
        (poll_interval/poll_max_attempts) finché COMPLETED o timeout->FAILED."""
        pending = list(self._repository.get_by_status(RequestStatus.SUBMITTED))
        if not pending:
            logger.info("Nessuna istruttoria in attesa di polling")
            return

        logger.info("Avvio polling di %d istruttorie", len(pending))
        for request in pending:
            self._poll_single(request)

    def _poll_single(self, request: DurcRequest) -> None:
        """Esegue il polling di una singola istruttoria fino a esito o timeout."""
        codice_fiscale = request.codice_fiscale
        for attempt in range(1, self._settings.poll_max_attempts + 1):
            voucher = self._voucher_manager.get_voucher(
                self._settings.durc_purpose_id)
            response = self._durc_client.poll_status(request.request_id, voucher)

            if response.status_code == 200:
                self._durc_client.download_document(
                    response, codice_fiscale, str(self._settings.output_dir))
                request.status = RequestStatus.COMPLETED
                self._repository.upsert(request)
                logger.info("CF=%s -> COMPLETED dopo polling", codice_fiscale)
                return

            logger.info("Polling CF=%s tentativo %d/%d status=%s", codice_fiscale,
                        attempt, self._settings.poll_max_attempts,
                        response.status_code)
            time.sleep(self._settings.poll_interval_seconds)

        request.status = RequestStatus.FAILED
        request.last_error = "Polling timeout: istruttoria non conclusa"
        self._repository.upsert(request)
        logger.error("CF=%s -> FAILED (timeout polling)", codice_fiscale)
