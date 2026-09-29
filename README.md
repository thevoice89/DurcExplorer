# PDND DURC Batch

Applicativo backend Python per il **controllo e il download massivo dei DURC**
(Documento Unico di Regolarità Contributiva) interrogando gli e-service INPS/ANAC
esposti sul catalogo **PDND** (Piattaforma Digitale Nazionale Dati).

> Stato: **Fase 1 completata** (architettura + scheletro). I corpi dei metodi sono
> stub (`raise NotImplementedError("Fase 2: Coder")`) da implementare in Fase 2.

## Architettura

Tre layer nettamente separati + concern trasversali:

| Layer | Package | Responsabilità |
|---|---|---|
| Autenticazione PDND | `auth/` | Client Assertion JWT (RFC 7521/7523), richiesta e cache del Voucher |
| Fruizione DURC | `api/` | Chiamate all'e-service, dispatch 200/202/429, download documento |
| Orchestrazione | `batch/` | Lettura CF (CSV/DB), state machine, persistenza coda, polling |
| Cross-cutting | `core/` | Rate limiter (token bucket), retry/backoff, eccezioni, logging |

### Flusso

```
CSV/DB ─▶ BatchProcessor
   ├─ VoucherManager.get_voucher(purposeId)  →  ClientAssertion (JWT RS256)  →  Token Endpoint  →  Voucher (cache TTL)
   ├─ RateLimiter.acquire()
   ├─ DurcApiClient.request_durc(cf, voucher)
   └─ dispatch HTTP:  200→COMPLETED · 202→SUBMITTED(coda) · 429→RATE_LIMITED(backoff) · 4xx/5xx→FAILED
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
pip install -r requirements.txt
```

## Configurazione (il tuo "pannello")

**Tutta la configurazione vive nel file `.env`. Il codice non si tocca mai.**
I parametri si impostano lì; il modulo `config.py` li legge e li valida.

1. Crea il file di configurazione:
   ```bash
   python -m durc_batch.doctor --init      # copia .env.example -> .env
   ```
2. (Se non le hai) genera la coppia di chiavi RSA:
   ```bash
   python -m durc_batch.doctor --gen-key   # crea keys/private_key.pem + keys/public_key.pem
   ```
   Carica **`keys/public_key.pem`** sul portale PDND: otterrai `kid` e `client_id`.
3. Apri `.env` e compila i 5 campi obbligatori:
   `PDND_CLIENT_ID`, `PDND_KID`, `PDND_DURC_BASE_URL`, `PDND_DURC_PURPOSE_ID`,
   `PDND_DURC_AUDIENCE`. (Gli endpoint PDND hanno già il default di produzione;
   per il collaudo sovrascrivi `PDND_TOKEN_ENDPOINT` / `PDND_AUTH_AUDIENCE` con gli URL UAT.)
4. Verifica che sia tutto a posto:
   ```bash
   python -m durc_batch.doctor             # checklist verde/rossa; exit 0 = pronto
   ```

Esempio di output a configurazione completa:

```
[ OK ]  client_id valorizzato
[ OK ]  chiave privata RSA valida (2048 bit): ...\keys\private_key.pem
[ OK ]  durc_base_url valorizzato
...
 PRONTO: configurazione completa.
```

## Esecuzione

Due modi, stessa logica sotto (`BatchProcessor`):

**A) Interfaccia web locale (consigliata)**
```bash
streamlit run streamlit_app.py
```
Si apre nel browser: pannello di configurazione a lato (stato + modifica `.env` +
generazione chiavi), upload del CSV, pulsante **Avvia controllo DURC**, tabella
degli esiti con contatori per stato e download dei documenti scaricati.

**B) Riga di comando (batch / schedulabile)**
```bash
python -m durc_batch.main
```
Legge `data/input/codici_fiscali.csv`, salva i DURC in `data/output/`, traccia lo
stato in `data/state.db`, logga in `logs/durc_batch.log`.

## Note di sicurezza

- La chiave privata RSA e il file `.env` **non vanno mai committati** (vedi `.gitignore`).
- Voucher e JWT firmati non devono comparire nei log in chiaro.

## Struttura

```
src/durc_batch/
├── main.py            # entrypoint / wiring
├── config.py          # Settings (pydantic-settings) — IMPLEMENTATO
├── doctor.py          # diagnostica configurazione — IMPLEMENTATO
├── models.py          # DTO + Enum di stato
├── auth/              # autenticazione PDND
├── api/               # e-service DURC
├── batch/             # orchestrazione & I/O
└── core/              # rate limiter, retry, eccezioni, logging
```
