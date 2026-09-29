"""Smoke test offline dei componenti critici (no rete)."""
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

from durc_batch.auth.client_assertion import ClientAssertionGenerator
from durc_batch.core.rate_limiter import RateLimiter
from durc_batch.batch.repository import StateRepository
from durc_batch.batch.reader import CsvCodiceFiscaleReader
from durc_batch.models import DurcRequest, RequestStatus, Voucher

ROOT = Path(__file__).resolve().parents[1]


def test_client_assertion() -> None:
    gen = ClientAssertionGenerator(
        client_id="client-123", kid="kid-abc",
        private_key_path=ROOT / "keys" / "private_key.pem",
        audience="auth.interop.pagopa.it/client-assertion",
        ttl_seconds=600,
    )
    token = gen.build("purpose-xyz")
    header = jwt.get_unverified_header(token)
    payload = jwt.decode(token, options={"verify_signature": False})
    assert header["alg"] == "RS256" and header["kid"] == "kid-abc" and header["typ"] == "JWT"
    assert payload["iss"] == payload["sub"] == "client-123"
    assert payload["purposeId"] == "purpose-xyz"
    assert payload["exp"] - payload["iat"] == 600
    assert "jti" in payload
    print("OK  client_assertion: header/claims corretti, JWT firmato")


def test_voucher_expiry() -> None:
    valido = Voucher(access_token="x", token_type="Bearer",
                     expires_at=datetime.now(timezone.utc) + timedelta(seconds=600))
    scaduto = Voucher(access_token="x", token_type="Bearer",
                      expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    assert valido.is_expired() is False and scaduto.is_expired() is True
    print("OK  voucher.is_expired: logica scadenza/skew corretta")


def test_rate_limiter() -> None:
    rl = RateLimiter(rate_per_second=50, burst=50)
    assert rl.acquire() is True
    print("OK  rate_limiter: acquire (pyrate-limiter 4.x) funziona")


def test_repository_roundtrip() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        repo = StateRepository(f"sqlite:///{tmp / 'state.db'}")
        repo.upsert(DurcRequest(codice_fiscale="CF1", status=RequestStatus.SUBMITTED,
                                request_id="req-1"))
        repo.upsert(DurcRequest(codice_fiscale="CF2", status=RequestStatus.COMPLETED))
        repo.upsert(DurcRequest(codice_fiscale="CF1", status=RequestStatus.COMPLETED))  # update
        completed = {r.codice_fiscale for r in repo.get_by_status(RequestStatus.COMPLETED)}
        assert completed == {"CF1", "CF2"}
        repo._engine.dispose()  # rilascia il lock sul file SQLite (Windows)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("OK  repository: upsert/update/get_by_status (idempotenza)")


def test_csv_reader() -> None:
    reader = CsvCodiceFiscaleReader(ROOT / "data" / "input" / "codici_fiscali.csv")
    cfs = list(reader.read())
    assert len(cfs) == len(set(cfs)) and all(cfs)
    print(f"OK  csv_reader: {len(cfs)} CF univoci letti")


if __name__ == "__main__":
    test_client_assertion()
    test_voucher_expiry()
    test_rate_limiter()
    test_repository_roundtrip()
    test_csv_reader()
    print("\nTUTTI GLI SMOKE TEST SUPERATI")
