# DURC Batch

Strumento per la **verifica massiva della regolarità contributiva (DURC)** tramite gli
e-service pubblicati sulla **PDND** (Piattaforma Digitale Nazionale Dati).

Pensato per gli uffici di una pubblica amministrazione che devono controllare
periodicamente il DURC di molti fornitori: prima di un pagamento, di un affidamento o di
una liquidazione. Invece di cercare le imprese una per una, carichi un elenco di codici
fiscali o partite IVA. Il programma interroga l'e-service, scarica i documenti e tiene
traccia dell'esito di ogni richiesta.

## Funzionalità

- **Interfaccia web locale** (Streamlit): pannello di configurazione con stato verde/rosso,
  generazione della coppia di chiavi, caricamento dell'elenco CSV, avvio del controllo,
  tabella degli esiti con contatori per stato e download dei documenti.
- **Riga di comando**: stesso motore dell'interfaccia, da lanciare a mano o da pianificare
  (es. Utilità di pianificazione di Windows o cron).
- **Autenticazione PDND completa**: *client assertion* firmata RS256 e voucher con cache
  per finalità, rinnovato solo alla scadenza.
- **Esiti sincroni e asincroni**:

  | Risposta dell'e-service | Cosa fa il programma |
  |---|---|
  | `200` | Salva il documento (esito `COMPLETED`) |
  | `202` | Mette la pratica in coda e la interroga a intervalli regolari (`SUBMITTED`) |
  | `429` | Attende e riprova con backoff (`RATE_LIMITED`) |
  | altri errori | Registra l'errore (`FAILED`) |

- **Rispetto delle quote**: rate limiter configurabile (richieste al secondo e picco), con
  retry e backoff esponenziale.
- **Ripresa automatica**: lo stato di ogni pratica è salvato in un database SQLite locale.
  Le pratiche già completate vengono saltate alle esecuzioni successive.
- **Diagnostica** (`doctor`): controlla configurazione e chiave privata e dice cosa manca.

## Stato del progetto

Il motore (autenticazione PDND, rate limiting, coda, polling, persistenza, interfaccia) è
completo. **I percorsi delle chiamate all'e-service DURC sono generici** (`POST /durc`,
`GET /durc/{id}`). Prima dell'uso vanno allineati alla specifica OpenAPI dell'e-service
scelto: sono i punti marcati `TODO` in
[`src/durc_batch/api/durc_client.py`](src/durc_batch/api/durc_client.py).

---

## 1. Ottenere l'accesso all'e-service DURC sulla PDND

Serve un ente **aderente alla PDND Interoperabilità**. Tutti i passi si fanno dal
back-office PDND: in produzione dall'Area Riservata PagoPA (prodotto *Interoperabilità*), in
collaudo da `selfcare.uat.interop.pagopa.it`. Collaudo e produzione sono ambienti separati,
con client, chiavi e finalità diversi: conviene provare prima in collaudo.

Alla fine di questa parte avrai **5 valori e un file**:

| Valore | Dove si ottiene | Variabile nel programma |
|---|---|---|
| Client ID | Passo 1.4 | `PDND_CLIENT_ID` |
| Key ID (`kid`) | Passo 1.4 | `PDND_KID` |
| Chiave privata (`private_key.pem`) | Passo 1.4, resta sul tuo PC | `PDND_PRIVATE_KEY_PATH` |
| Purpose ID | Passo 1.3 | `PDND_DURC_PURPOSE_ID` |
| Base URL dell'e-service | Passo 1.2 | `PDND_DURC_BASE_URL` |
| Audience dell'e-service | Passo 1.2 | `PDND_DURC_AUDIENCE` |

### 1.1 Adesione e ruoli

L'adesione alla PDND la fa il legale rappresentante dell'ente (o un delegato) con SPID o CIE.
Per i passi successivi servono utenti con il ruolo di **Amministratore** o **Operatore API**
(creano fruizioni, finalità e client). Per caricare le chiavi serve anche l'**Operatore di
sicurezza**.

### 1.2 Trovare l'e-service e richiedere la fruizione

1. Apri il **Catalogo e-service** e cerca `DURC`. Scegli l'e-service di verifica della
   regolarità contributiva adatto al tuo ente e controlla nella scheda gli **attributi
   richiesti** e le **soglie** di chiamate al giorno.
2. Dalla scheda annota il **Base URL** del server e l'**audience** dichiarata
   dall'e-service, e scarica la **specifica OpenAPI**: serve per allineare i percorsi delle
   chiamate (vedi *Stato del progetto*).
3. Premi **Richiedi fruizione**. A seconda dell'e-service la richiesta si attiva subito o
   resta in attesa di approvazione dell'erogatore.

### 1.3 Creare la finalità

1. **Le tue finalità → Crea nuova finalità** e scegli l'e-service DURC.
2. Compila nome, descrizione e base giuridica (es. verifica della regolarità contributiva
   dei fornitori prevista dal codice dei contratti pubblici), poi l'**analisi del rischio**.
3. Indica la **stima di carico** (chiamate al giorno): sopra la soglia dell'e-service serve
   l'approvazione dell'erogatore.
4. Quando la finalità è attiva, annota il **Purpose ID** (UUID).

### 1.4 Creare il client e caricare la chiave pubblica

1. **I tuoi client → Crea nuovo client**, di tipo **API/e-service** (machine-to-machine), e
   annota il **Client ID**.
2. **Associa al client la finalità** creata al passo 1.3.
3. Genera la coppia di chiavi RSA, direttamente dal programma (§2.2) oppure con OpenSSL:

   ```bash
   openssl genrsa -out keys/private_key.pem 2048
   openssl rsa -in keys/private_key.pem -pubout -out keys/public_key.pem
   ```

4. Nel client, **Chiavi pubbliche → Aggiungi**, carica **solo** `public_key.pem` e annota il
   **`kid`** assegnato. La chiave privata non si carica mai: resta sul tuo PC e serve al
   programma per firmare.

### 1.5 Endpoint di autenticazione

Sono già impostati sui valori di **produzione**. In **collaudo** vanno cambiati nel `.env`:

| Variabile | Produzione (predefinito) | Collaudo |
|---|---|---|
| `PDND_TOKEN_ENDPOINT` | `https://auth.interop.pagopa.it/token.oauth2` | `https://auth.uat.interop.pagopa.it/token.oauth2` |
| `PDND_AUTH_AUDIENCE` | `auth.interop.pagopa.it/client-assertion` | `auth.uat.interop.pagopa.it/client-assertion` |

Nota: l'audience della client assertion si scrive **senza** `https://`, come indicato nel
manuale operativo PDND. In caso di differenze valgono i valori mostrati nella pagina del
client sul back-office.

> **Suggerimento:** nella pagina di ogni client il back-office ha il pulsante **«Simula
> l'ottenimento del voucher»**. Prova l'intera catena (client assertion → voucher) senza
> scrivere codice e porta allo strumento **«Debug client assertion»**, che restituisce un
> esito dettagliato. È il modo più rapido per verificare `client_id`, `kid` e chiave prima
> di avviare il programma.

---

## 2. Installazione

Requisiti: **Python 3.11 o superiore** (oppure Docker).

### 2.1 Installazione con Python

```bash
git clone <url-della-repo> durc
cd durc
python -m venv .venv
```

Attiva l'ambiente virtuale:

```bash
.venv\Scripts\activate
```

(su Linux o macOS: `source .venv/bin/activate`)

Installa le dipendenze e il pacchetto:

```bash
pip install -r requirements.txt
pip install -e .
```

### 2.2 Configurazione

Crea il file `.env` a partire dall'esempio:

```bash
python -m durc_batch.doctor --init
```

Se non hai ancora una chiave, generala. Crea `keys/private_key.pem` e `keys/public_key.pem`;
la pubblica va caricata sulla PDND (passo 1.4):

```bash
python -m durc_batch.doctor --gen-key
```

Apri `.env` e compila i cinque campi obbligatori con i valori della parte 1:

```ini
PDND_CLIENT_ID=
PDND_KID=
PDND_DURC_BASE_URL=
PDND_DURC_PURPOSE_ID=
PDND_DURC_AUDIENCE=
```

Il file contiene anche i parametri operativi, già impostati: richieste al secondo, picco,
tentativi, intervallo e numero massimo di interrogazioni per le pratiche in coda. Infine
verifica:

```bash
python -m durc_batch.doctor
```

Deve terminare con **PRONTO**. In alternativa, tutti questi passi si possono fare dalla
sezione **Impostazioni** dell'interfaccia web.

### 2.3 Installazione con Docker

L'immagine avvia l'interfaccia web. Prima dell'avvio crea `.env` (vedi §2.2, anche copiando
`.env.example`) e metti la chiave in `keys/`: se `.env` non esiste, Docker crea al suo posto
una cartella vuota.

```bash
docker compose up -d --build
```

L'interfaccia è su `http://localhost:8501`. `.env`, `keys/`, `data/` e `logs/` sono
montati dalla cartella del progetto.

---

## 3. Uso

### Interfaccia web (consigliata)

```bash
streamlit run streamlit_app.py
```

Si apre il browser su `http://localhost:8501`:

1. **Impostazioni**: verifica che tutte le voci siano verdi.
2. **Lista codici fiscali**: carica un CSV con una colonna `codice_fiscale`
   (vedi `data/input/codici_fiscali.example.csv`).
3. **Esecuzione**: avvia il controllo.
4. **Esiti**: stato di ogni pratica e download dei documenti.

### Riga di comando

```bash
python -m durc_batch.main
```

Legge `data/input/codici_fiscali.csv` e salva i risultati:

| Cosa | Dove |
|---|---|
| Documenti DURC | `data/output/` |
| Stato delle pratiche | `data/state.db` |
| Log | `logs/durc_batch.log` |

Il comando si può pianificare: le pratiche già completate non vengono ripetute.

## Sicurezza

- `.env`, chiavi, elenchi di codici fiscali, database e log sono esclusi da git (vedi
  `.gitignore`): non vanno mai condivisi né versionati.
- Sulla PDND si carica solo la chiave pubblica.
- Voucher e JWT firmati non vengono mai scritti nei log.

## Struttura

```
src/durc_batch/
├── auth/       # client assertion e voucher PDND
├── api/        # chiamate all'e-service DURC
├── batch/      # lettura elenco, coda, stato, polling
├── core/       # rate limiter, retry, eccezioni, logging
├── config.py   # configurazione letta da .env (pydantic-settings)
├── doctor.py   # diagnostica della configurazione
└── main.py     # esecuzione da riga di comando
streamlit_app.py  # interfaccia web
GUIDA.md          # guida operativa passo passo (anche in PDF)
```

## Riferimenti

- [PDND Interoperabilità: documentazione per sviluppatori](https://developer.pagopa.it/pdnd-interoperabilita)
- [Guida operativa del progetto](GUIDA.md)
