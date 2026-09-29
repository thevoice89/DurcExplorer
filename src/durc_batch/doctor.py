"""Pannello di verifica della configurazione ("doctor").

Comando di diagnostica gia' implementato (Fase 1): NON va modificato dal Coder.
Permette di verificare, senza leggere il codice, se il sistema e' pronto a girare.

Uso:
    python -m durc_batch.doctor              # mostra la checklist di configurazione
    python -m durc_batch.doctor --init       # crea .env da .env.example (se assente)
    python -m durc_batch.doctor --gen-key    # genera la coppia di chiavi RSA in keys/

Codice di uscita: 0 se tutto e' pronto, 1 se manca qualcosa.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from durc_batch.config import PROJECT_ROOT, Settings

OK = "[ OK ]"
MISSING = "[FAIL]"
WARN = "[WARN]"


@dataclass
class CheckReport:
    """Esito della diagnostica: linee di checklist + flag di prontezza."""
    lines: list[str] = field(default_factory=list)
    ready: bool = True

    def add(self, status: str, message: str) -> None:
        """Aggiunge una riga alla checklist; un FAIL marca il report non pronto."""
        self.lines.append(f"  {status}  {message}")
        if status == MISSING:
            self.ready = False


def _dir_writable(path: Path) -> bool:
    """True se la cartella esiste (o e' creabile) ed e' scrivibile."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def inspect_private_key(path: Path) -> tuple[bool, str]:
    """Verifica che il file sia una chiave privata RSA in PEM leggibile.

    Ritorna (valida, descrizione) senza mai stampare/loggare il contenuto.
    """
    if not path.exists():
        return False, f"chiave privata assente: {path}"
    try:
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    except (ValueError, TypeError) as exc:
        return False, f"chiave privata non leggibile come PEM: {exc}"
    if not isinstance(key, rsa.RSAPrivateKey):
        return False, "la chiave non e' RSA (richiesta RSA per la firma RS256)"
    return True, f"chiave privata RSA valida ({key.key_size} bit): {path}"


def check_config(settings: Settings) -> CheckReport:
    """Esegue tutti i controlli di configurazione e ritorna la checklist."""
    report = CheckReport()

    # 1) File .env
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        report.add(OK, f"file .env presente: {env_file}")
    else:
        report.add(WARN, "file .env assente (uso default + variabili d'ambiente). "
                          "Crealo con: python -m durc_batch.doctor --init")

    # 2) Campi identita' PDND obbligatori
    for name in ("client_id", "kid"):
        if getattr(settings, name):
            report.add(OK, f"{name} valorizzato")
        else:
            report.add(MISSING, f"{name} non valorizzato nel .env (PDND_{name.upper()})")

    # 3) Chiave privata RSA
    valid, desc = inspect_private_key(settings.private_key_path)
    report.add(OK if valid else MISSING, desc)

    # 4) Parametri e-service DURC
    for name in ("durc_base_url", "durc_purpose_id", "durc_audience"):
        if getattr(settings, name):
            report.add(OK, f"{name} valorizzato")
        else:
            report.add(MISSING, f"{name} non valorizzato nel .env (PDND_{name.upper()})")

    # 5) Endpoint PDND (informativo: hanno default di produzione)
    report.add(OK, f"token_endpoint = {settings.token_endpoint}")
    report.add(OK, f"auth_audience  = {settings.auth_audience}")

    # 6) Cartelle scrivibili
    for label, path in (("output", settings.output_dir), ("logs", settings.log_dir)):
        if _dir_writable(path):
            report.add(OK, f"cartella {label} scrivibile: {path}")
        else:
            report.add(MISSING, f"cartella {label} NON scrivibile: {path}")

    # 7) CSV di input (warning: potrebbe non esserci ancora)
    if settings.input_csv.exists():
        report.add(OK, f"CSV input presente: {settings.input_csv}")
    else:
        report.add(WARN, f"CSV input assente (atteso in {settings.input_csv})")

    return report


def init_env_file() -> None:
    """Crea `.env` copiando `.env.example`, se non gia' presente."""
    env_file = PROJECT_ROOT / ".env"
    example = PROJECT_ROOT / ".env.example"
    if env_file.exists():
        print(f"{WARN}  .env gia' presente, non sovrascritto: {env_file}")
        return
    if not example.exists():
        print(f"{MISSING}  .env.example non trovato: {example}")
        return
    shutil.copyfile(example, env_file)
    print(f"{OK}  creato {env_file} da .env.example -- ora compila i campi richiesti.")


def generate_key_pair(force: bool = False) -> None:
    """Genera una coppia di chiavi RSA 2048 in keys/ (privata PKCS8 + pubblica SPKI).

    La PUBBLICA va caricata sul portale PDND (da cui otterrai `kid` e `client_id`);
    la PRIVATA resta solo sulla tua macchina e non va mai condivisa/committata.
    """
    keys_dir = PROJECT_ROOT / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    priv_path = keys_dir / "private_key.pem"
    pub_path = keys_dir / "public_key.pem"

    if priv_path.exists() and not force:
        print(f"{WARN}  {priv_path} esiste gia'. Usa --gen-key --force per rigenerarla.")
        return

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_path.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    pub_path.write_bytes(key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    print(f"{OK}  chiave privata: {priv_path}")
    print(f"{OK}  chiave pubblica: {pub_path}  <-- carica QUESTA su PDND")


def main() -> None:
    """Entry point CLI del doctor."""
    parser = argparse.ArgumentParser(
        prog="durc-doctor",
        description="Verifica la configurazione del PDND DURC Batch.",
    )
    parser.add_argument("--init", action="store_true",
                        help="crea .env da .env.example se assente")
    parser.add_argument("--gen-key", action="store_true",
                        help="genera la coppia di chiavi RSA in keys/")
    parser.add_argument("--force", action="store_true",
                        help="con --gen-key, sovrascrive una chiave esistente")
    args = parser.parse_args()

    if args.init:
        init_env_file()
        print()
    if args.gen_key:
        generate_key_pair(force=args.force)
        print()

    settings = Settings()
    report = check_config(settings)

    print("=" * 70)
    print(" DIAGNOSTICA CONFIGURAZIONE -- PDND DURC Batch")
    print("=" * 70)
    for line in report.lines:
        print(line)
    print("-" * 70)
    if report.ready:
        print(" PRONTO: configurazione completa. Manca solo l'implementazione Fase 2.")
        sys.exit(0)
    else:
        missing = ", ".join(settings.missing_user_fields()) or "vedi righe [FAIL]"
        print(f" NON PRONTO: completa gli elementi [FAIL] ({missing}).")
        sys.exit(1)


if __name__ == "__main__":
    main()
