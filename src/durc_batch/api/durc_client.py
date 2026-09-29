"""Client dell'e-service DURC (INPS/ANAC) esposto sul catalogo PDND."""
from pathlib import Path

import requests

from durc_batch.core.logging_conf import get_logger
from durc_batch.core.rate_limiter import RateLimiter
from durc_batch.models import DurcResult, Voucher

logger = get_logger(__name__)

# Mappa Content-Type -> estensione file per il documento DURC scaricato.
_EXT_BY_CONTENT_TYPE = {
    "application/pdf": ".pdf",
    "application/xml": ".xml",
    "text/xml": ".xml",
    "application/json": ".json",
}


class DurcApiClient:
    """Incapsula le chiamate all'e-service DURC. Gestisce 200/202/429 e download."""

    def __init__(self, base_url: str, session: requests.Session,
                 rate_limiter: RateLimiter) -> None:
        """Inizializza con base URL e-service, sessione HTTP e rate limiter."""
        self._base_url = base_url.rstrip("/")
        self._session = session
        self._rate_limiter = rate_limiter

    def _auth_headers(self, voucher: Voucher) -> dict[str, str]:
        """Header di autorizzazione col voucher (non viene mai loggato)."""
        return {
            "Authorization": f"Bearer {voucher.access_token}",
            "Accept": "application/json",
        }

    def request_durc(self, codice_fiscale: str, voucher: Voucher) -> requests.Response:
        """Invia la richiesta DURC per il CF passando 'Authorization: Bearer <voucher>'.
        Applica il rate limiting prima della chiamata. Ritorna la Response grezza
        (il dispatch su 200/202/429 è responsabilità del processor)."""
        self._rate_limiter.acquire()
        # TODO: verificare su OpenAPI e-service il path/metodo esatti della richiesta.
        url = f"{self._base_url}/durc"
        response = self._session.post(
            url, params={"codiceFiscale": codice_fiscale},
            headers=self._auth_headers(voucher), timeout=60,
        )
        logger.info("Richiesta DURC CF=%s status=%s", codice_fiscale,
                    response.status_code)
        return response

    def poll_status(self, request_id: str, voucher: Voucher) -> requests.Response:
        """Interroga lo stato di un'istruttoria avviata (flusso 202 -> polling)."""
        self._rate_limiter.acquire()
        # TODO: verificare su OpenAPI e-service il path/metodo esatti del polling.
        url = f"{self._base_url}/durc/{request_id}"
        response = self._session.get(
            url, headers=self._auth_headers(voucher), timeout=60,
        )
        logger.info("Polling request_id=%s status=%s", request_id,
                    response.status_code)
        return response

    def download_document(self, response: requests.Response,
                          codice_fiscale: str, output_dir: str) -> DurcResult:
        """Estrae/scarica il documento DURC dall'esito 200 e ne salva il file,
        ritornando un DurcResult con percorso, esito e payload."""
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        extension = _EXT_BY_CONTENT_TYPE.get(content_type, ".bin")

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        document_path = out_dir / f"durc_{codice_fiscale}{extension}"
        document_path.write_bytes(response.content)

        esito: str | None = None
        raw_payload: dict | None = None
        if extension == ".json":
            try:
                raw_payload = response.json()
                # TODO: verificare su OpenAPI e-service il nome del campo esito.
                esito = raw_payload.get("esito") or raw_payload.get("result")
            except ValueError:
                raw_payload = None

        logger.info("Documento DURC salvato CF=%s -> %s", codice_fiscale,
                    document_path)
        return DurcResult(
            codice_fiscale=codice_fiscale, esito=esito,
            document_path=str(document_path), raw_payload=raw_payload,
        )
