"""Test d'integrazione end-to-end con PDND/e-service DURC SIMULATI (no rete reale).

Verifica l'intera pipeline (assertion -> voucher -> chiamata DURC -> state machine
-> persistenza -> polling) intercettando le chiamate HTTP della requests.Session.
Scenari:
  CF1 -> 200 (DURC pronto)            => COMPLETED
  CF2 -> 202 e poi polling 200        => COMPLETED
  CF3 -> 429 (SLA superati)           => RATE_LIMITED
"""
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Config minima via env PRIMA di importare il package (pydantic-settings la legge).
os.environ.update({
    "PDND_CLIENT_ID": "client-test",
    "PDND_KID": "kid-test",
    "PDND_PRIVATE_KEY_PATH": str(ROOT / "keys" / "private_key.pem"),
    "PDND_DURC_BASE_URL": "https://durc.example.test/v1",
    "PDND_DURC_PURPOSE_ID": "purpose-test",
    "PDND_DURC_AUDIENCE": "durc-aud-test",
    "PDND_TOKEN_ENDPOINT": "https://auth.example.test/token",
    "PDND_POLL_INTERVAL_SECONDS": "0",
    "PDND_POLL_MAX_ATTEMPTS": "3",
})

import sys
sys.path.insert(0, str(ROOT / "src"))

from durc_batch.api.durc_client import DurcApiClient          # noqa: E402
from durc_batch.auth.client_assertion import ClientAssertionGenerator  # noqa: E402
from durc_batch.auth.voucher_manager import VoucherManager    # noqa: E402
from durc_batch.batch.processor import BatchProcessor         # noqa: E402
from durc_batch.batch.reader import CsvCodiceFiscaleReader    # noqa: E402
from durc_batch.batch.repository import StateRepository       # noqa: E402
from durc_batch.config import Settings                        # noqa: E402
from durc_batch.core.rate_limiter import RateLimiter          # noqa: E402
from durc_batch.models import RequestStatus                   # noqa: E402


class MockResponse:
    """Risposta HTTP fittizia compatibile con l'uso che ne fa il codice."""
    def __init__(self, status_code, *, json_data=None, content=b"", headers=None):
        self.status_code = status_code
        self._json = json_data
        self.content = content if content else (
            json.dumps(json_data).encode() if json_data is not None else b"")
        self.headers = headers or {}
        self.text = self.content.decode(errors="replace")

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class MockSession:
    """Session che instrada token endpoint e e-service DURC verso risposte finte."""
    def __init__(self):
        self.poll_calls = 0

    def post(self, url, **kwargs):
        if "token" in url:                                   # token endpoint PDND
            return MockResponse(200, json_data={
                "access_token": "voucher-abc", "token_type": "Bearer",
                "expires_in": 600})
        cf = (kwargs.get("params") or {}).get("codiceFiscale")
        if cf == "CF1":                                      # pronto subito
            return MockResponse(200, json_data={"esito": "REGOLARE"},
                                headers={"Content-Type": "application/json"})
        if cf == "CF2":                                      # istruttoria avviata
            return MockResponse(202, json_data={"requestId": "REQ-CF2"})
        if cf == "CF3":                                      # rate limited
            return MockResponse(429, headers={"Retry-After": "1"})
        return MockResponse(500)

    def get(self, url, **kwargs):                            # polling istruttoria
        self.poll_calls += 1
        return MockResponse(200, json_data={"esito": "REGOLARE"},
                            headers={"Content-Type": "application/json"})


def main():
    settings = Settings()
    session = MockSession()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # CSV di input con i 3 CF di test
        csv_path = tmp_path / "cf.csv"
        csv_path.write_text("codice_fiscale\nCF1\nCF2\nCF3\n", encoding="utf-8")
        settings.input_csv = csv_path
        settings.output_dir = tmp_path / "out"

        generator = ClientAssertionGenerator(
            settings.client_id, settings.kid, settings.private_key_path,
            settings.auth_audience, settings.assertion_ttl_seconds)
        voucher_manager = VoucherManager(
            generator, settings.token_endpoint, settings.client_id, session)
        rate_limiter = RateLimiter(50, 50)
        durc_client = DurcApiClient(settings.durc_base_url, session, rate_limiter)
        reader = CsvCodiceFiscaleReader(csv_path)
        repo = StateRepository(f"sqlite:///{tmp_path / 'state.db'}")
        processor = BatchProcessor(
            settings, reader, voucher_manager, durc_client, repo)

        processor.run()

        completed = {r.codice_fiscale for r in repo.get_by_status(RequestStatus.COMPLETED)}
        rate_limited = {r.codice_fiscale for r in repo.get_by_status(RequestStatus.RATE_LIMITED)}

        assert completed == {"CF1", "CF2"}, f"COMPLETED inatteso: {completed}"
        assert rate_limited == {"CF3"}, f"RATE_LIMITED inatteso: {rate_limited}"
        assert session.poll_calls >= 1, "il polling del 202 non e' avvenuto"
        out_files = sorted(p.name for p in (settings.output_dir).glob("durc_*"))
        assert out_files == ["durc_CF1.json", "durc_CF2.json"], out_files
        repo._engine.dispose()

        print("OK  CF1 -> COMPLETED (200 diretto)")
        print("OK  CF2 -> COMPLETED (202 -> polling -> 200)")
        print("OK  CF3 -> RATE_LIMITED (429 gestito, non fallito)")
        print(f"OK  documenti salvati: {out_files}")
        print(f"OK  chiamate di polling effettuate: {session.poll_calls}")
        print("\nTEST D'INTEGRAZIONE END-TO-END SUPERATO")


if __name__ == "__main__":
    main()
