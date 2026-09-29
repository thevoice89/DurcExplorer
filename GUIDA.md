# Guida operativa — PDND DURC Batch

Guida in due parti:
1. **Configurazione su PDND** — cosa fare sul portale per ottenere le credenziali.
2. **Configurazione del programma** — dove inserire quelle credenziali per farlo funzionare.

Il legame tra le due parti è questo: dalla PDND ricavi 5 valori + 1 file, che poi
incolli nel programma.

| Valore ottenuto dalla PDND | Campo nel programma |
|---|---|
| Client ID (UUID del client) | `PDND_CLIENT_ID` |
| Key ID (kid della chiave) | `PDND_KID` |
| Chiave privata RSA (file `.pem`, resta a te) | `PDND_PRIVATE_KEY_PATH` |
| Purpose ID (id della finalità) | `PDND_DURC_PURPOSE_ID` |
| Base URL dell'e-service DURC | `PDND_DURC_BASE_URL` |
| Audience dell'e-service DURC | `PDND_DURC_AUDIENCE` |

> Gli endpoint di autenticazione (`PDND_TOKEN_ENDPOINT`, `PDND_AUTH_AUDIENCE`) sono
> già preimpostati sui valori di **produzione**: li cambi solo se usi l'ambiente di
> **collaudo (UAT)**.

---

## PARTE 1 — Configurazione su PDND

> I nomi esatti delle voci di menu possono cambiare nel tempo: l'accesso avviene dal
> portale **PDND Interoperabilità** (area riservata, tramite SPID/CIE).
> Riferimento ufficiale: https://developer.pagopa.it/pdnd-interoperabilita

### 1.1 Adesione dell'ente (se non già fatto)
- L'ente deve aver **aderito** alla PDND. L'adesione la effettua il **legale
  rappresentante** (o un delegato) con SPID/CIE.
- Vengono nominati un **Amministratore** e uno o più **Operatori API**: sono i ruoli
  che possono creare client e gestire le fruizioni.

### 1.2 Crea il client di fruizione e il materiale crittografico
1. Nell'area Interoperabilità, vai su **Client → Client di fruizione** (client
   "machine-to-machine", per *consumare* e-service) e creane uno nuovo.
2. Annota il **Client ID** (è un UUID): sarà `PDND_CLIENT_ID`.
3. **Genera la coppia di chiavi RSA** (puoi farlo direttamente dal programma —
   vedi Parte 2 — oppure con OpenSSL).
4. **Carica la chiave PUBBLICA** (`public_key.pem`) sul client. La PDND la registra e
   le assegna un **kid (Key ID)**: sarà `PDND_KID`.
5. La **chiave PRIVATA** (`private_key.pem`) **non si carica mai**: resta solo sulla
   tua macchina e serve al programma per firmare le richieste.

### 1.3 Trova l'e-service DURC nel catalogo
1. Vai nel **Catalogo e-service** e cerca il servizio DURC dell'erogatore (es. INPS
   o ANAC, a seconda dell'e-service che ti serve).
2. Apri la scheda dell'e-service e annota, dal **descrittore/versione** pubblicato:
   - il **Base URL** del server (l'indirizzo a cui si chiamano le API) → `PDND_DURC_BASE_URL`
   - l'**Audience** dichiarata → `PDND_DURC_AUDIENCE`

### 1.4 Richiedi la fruizione e crea la finalità (purpose)
1. Dalla scheda dell'e-service, avvia la **Richiesta di fruizione** (iscrizione al
   servizio) con il tuo client.
2. Crea una **Finalità (purpose)**: descrive *perché* utilizzi il servizio (la base
   giuridica/uso). Collega la finalità al client del punto 1.2.
3. La fruizione/finalità deve essere **approvata dall'erogatore**. Quando è attiva,
   ottieni il **Purpose ID** → `PDND_DURC_PURPOSE_ID`.

### 1.5 (Opzionale) Ambiente di collaudo
- Prima della produzione conviene provare tutto in **collaudo (UAT)**: ripeti i passi
  sopra sull'ambiente di collaudo e, nel programma, sovrascrivi `PDND_TOKEN_ENDPOINT`
  e `PDND_AUTH_AUDIENCE` con i corrispondenti URL UAT.

**Al termine della Parte 1 devi avere in mano:**
`Client ID`, `kid`, il file `private_key.pem`, `Purpose ID`, `Base URL` e `Audience`
dell'e-service.

---

## PARTE 2 — Configurazione del programma

Hai due modi, equivalenti: **interfaccia grafica** (consigliata) o **file di testo**.

### Prerequisiti (una sola volta)
```powershell
cd C:\Users\dgrioni\Desktop\pdnd
.\.venv\Scripts\python.exe -m pip install -r requirements.txt   # se non già fatto
```

### Modo A — Interfaccia grafica (consigliato)

1. Avvia la UI:
   ```powershell
   cd C:\Users\dgrioni\Desktop\pdnd
   .\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
   ```
   Si apre il browser su `http://localhost:8501`.

2. Apri la sezione **⚙️ Impostazioni** (è già aperta se la config è incompleta).

3. In **Credenziali e parametri PDND** inserisci e premi **💾 Salva parametri**:
   - Client ID → dal punto 1.2
   - Key ID (kid) → dal punto 1.2
   - DURC base URL → dal punto 1.3
   - Purpose ID → dal punto 1.4
   - DURC audience → dal punto 1.3
   - (Token endpoint / Auth audience: lasciali così per la produzione)

4. In **Chiave privata RSA**, scegli una via:
   - **Opzione A** — carichi il tuo file `private_key.pem` (poi *Salva chiave caricata*);
     viene validato subito.
   - **Opzione B** — premi **🔑 Genera coppia di chiavi RSA**, poi
     **⬇️ Scarica chiave pubblica** e caricala su PDND (passo 1.2) per ottenere il kid.

5. Controlla la **sidebar**: tutte le voci devono diventare verdi `[ OK ]`.

6. In **1. Lista codici fiscali** carica un CSV con una colonna `codice_fiscale`.

7. Premi **▶ Avvia controllo DURC**. Gli esiti compaiono in **3. Esiti**, con i
   documenti scaricabili.

### Modo B — File di configurazione (`.env`)

1. Crea il file `.env` (se non esiste):
   ```powershell
   .\.venv\Scripts\python.exe -m durc_batch.doctor --init
   ```

2. (Se non hai una chiave) generala:
   ```powershell
   .\.venv\Scripts\python.exe -m durc_batch.doctor --gen-key
   ```
   Carica `keys\public_key.pem` su PDND (passo 1.2) per ottenere il kid.
   Se invece hai già la tua chiave, copiala in `keys\private_key.pem`.

3. Apri `.env` con un editor e compila i 5 campi:
   ```ini
   PDND_CLIENT_ID=<Client ID dal punto 1.2>
   PDND_KID=<kid dal punto 1.2>
   PDND_DURC_BASE_URL=<Base URL dal punto 1.3>
   PDND_DURC_PURPOSE_ID=<Purpose ID dal punto 1.4>
   PDND_DURC_AUDIENCE=<Audience dal punto 1.3>
   ```
   (Per il collaudo, sovrascrivi anche `PDND_TOKEN_ENDPOINT` e `PDND_AUTH_AUDIENCE`.)

4. Verifica che sia tutto a posto:
   ```powershell
   .\.venv\Scripts\python.exe -m durc_batch.doctor
   ```
   Deve stampare **PRONTO**.

5. Metti i codici fiscali in `data\input\codici_fiscali.csv` (colonna `codice_fiscale`)
   e lancia il batch:
   ```powershell
   .\.venv\Scripts\python.exe -m durc_batch.main
   ```

### Dove finiscono i risultati
- **Documenti DURC** → `data\output\` (es. `durc_<codicefiscale>.pdf`)
- **Stato delle richieste** → `data\state.db` (le pratiche già completate vengono
  saltate alle esecuzioni successive)
- **Log** → `logs\durc_batch.log`

### Sicurezza (importante)
- Non condividere e non versionare **`private_key.pem`** né il file **`.env`**:
  sono già esclusi da git tramite `.gitignore`.
- Sul portale PDND carichi **solo** la chiave pubblica.

---

## Promemoria rapido

| Passo | Comando |
|---|---|
| Verifica configurazione | `.\.venv\Scripts\python.exe -m durc_batch.doctor` |
| Avvia interfaccia grafica | `.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py` |
| Avvia batch da terminale | `.\.venv\Scripts\python.exe -m durc_batch.main` |
| Genera coppia di chiavi | `.\.venv\Scripts\python.exe -m durc_batch.doctor --gen-key` |
