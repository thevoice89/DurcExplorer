"""Interfaccia web locale (Streamlit) per il PDND DURC Batch.

Avvio:
    .\\.venv\\Scripts\\python.exe -m streamlit run streamlit_app.py

NB: e' solo un "guscio" grafico. Tutta la logica resta nel package durc_batch
(BatchProcessor); qui non c'e' alcuna regola di business duplicata.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Rende importabile il package con layout "src" senza installazione.
PROJECT_ROOT = Path(__file__).resolve().parent
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from durc_batch.config import PROJECT_ROOT as PKG_ROOT, Settings  # noqa: E402
from durc_batch.core.logging_conf import setup_logging  # noqa: E402
from durc_batch.batch.repository import StateRepository  # noqa: E402
from durc_batch.doctor import (  # noqa: E402
    check_config, generate_key_pair, inspect_private_key,
)
from durc_batch.main import build_processor  # noqa: E402
from durc_batch.models import RequestStatus  # noqa: E402

ENV_FILE = PKG_ROOT / ".env"
# Campi modificabili dal pannello (la chiave privata si gestisce a parte).
EDITABLE_FIELDS = [
    ("PDND_CLIENT_ID", "client_id", "Client ID (UUID)"),
    ("PDND_KID", "kid", "Key ID (kid)"),
    ("PDND_DURC_BASE_URL", "durc_base_url", "DURC base URL"),
    ("PDND_DURC_PURPOSE_ID", "durc_purpose_id", "Purpose ID"),
    ("PDND_DURC_AUDIENCE", "durc_audience", "DURC audience"),
    ("PDND_TOKEN_ENDPOINT", "token_endpoint", "Token endpoint PDND"),
    ("PDND_AUTH_AUDIENCE", "auth_audience", "Auth audience (aud assertion)"),
]


# --------------------------------------------------------------------------- #
#  Helper .env
# --------------------------------------------------------------------------- #
def _read_env() -> dict[str, str]:
    """Legge le coppie KEY=VALUE dal .env (se esiste)."""
    values: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    return values


def _write_env(updates: dict[str, str]) -> None:
    """Aggiorna le chiavi indicate nel .env preservando il resto del file."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    remaining = dict(updates)
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                continue
        out.append(line)
    for key, val in remaining.items():        # chiavi non ancora presenti
        out.append(f"{key}={val}")
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")


def _tail_log(settings: Settings, n: int = 60) -> str:
    """Ritorna le ultime n righe del log applicativo."""
    log_file = settings.log_dir / "durc_batch.log"
    if not log_file.exists():
        return "(nessun log ancora)"
    return "\n".join(log_file.read_text(encoding="utf-8").splitlines()[-n:])


# --------------------------------------------------------------------------- #
#  Pagina Impostazioni (separata dalla pagina di consultazione)
# --------------------------------------------------------------------------- #
def render_settings(settings: Settings, ready: bool) -> None:
    """Pagina completa di configurazione: parametri PDND + chiave privata RSA."""
    badge_class = "pdnd-badge--ok" if ready else "pdnd-badge--warn"
    badge_text = "Configurato" if ready else "Da completare"
    st.markdown(
        f'<div class="pdnd-page-title">'
        f'<h2>Impostazioni PDND</h2>'
        f'<span class="pdnd-badge {badge_class}">{badge_text}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # --- Credenziali / parametri PDND -> .env ---
    with st.expander("Credenziali e parametri PDND", expanded=not ready):
        st.caption("Vengono salvati nel file `.env`. `client_id` e `kid` arrivano "
                   "dalla PDND dopo aver caricato la chiave pubblica.")
        current = _read_env()
        with st.form("env_form"):
            new_values: dict[str, str] = {}
            for env_key, attr, label in EDITABLE_FIELDS:
                default = current.get(env_key, getattr(settings, attr, "") or "")
                new_values[env_key] = st.text_input(label, value=str(default))
            if st.form_submit_button("💾 Salva parametri"):
                _write_env(new_values)
                st.success("Parametri salvati nel .env.")
                st.rerun()

    # --- Chiave privata RSA ---
    key_path = settings.private_key_path
    key_valid, key_desc = inspect_private_key(key_path)
    with st.expander("Chiave privata RSA", expanded=not key_valid):
        if key_valid:
            st.success(key_desc)
        else:
            st.error(key_desc)
        st.caption(f"Percorso atteso: `{key_path}` (configurabile con "
                   "`PDND_PRIVATE_KEY_PATH`).")

        col_up, col_gen = st.columns(2)

        with col_up:
            st.markdown("**Opzione A — Carica la tua chiave**")
            uploaded_key = st.file_uploader(
                "File PEM della chiave privata RSA", type=["pem", "key"],
                key="key_upload")
            if uploaded_key is not None and st.button("Salva chiave caricata"):
                key_path.parent.mkdir(parents=True, exist_ok=True)
                key_path.write_bytes(uploaded_key.getvalue())
                ok, msg = inspect_private_key(key_path)
                if ok:
                    st.success("Chiave salvata e validata.")
                    st.rerun()
                else:
                    st.error(f"File non valido: {msg}")

        with col_gen:
            st.markdown("**Opzione B — Generala qui**")
            st.caption("Crea una nuova coppia. Carica poi la PUBBLICA su PDND.")
            if st.button("🔑 Genera coppia di chiavi RSA"):
                generate_key_pair(force=True)
                st.success("Coppia generata in keys/.")
                st.rerun()

        # Download della chiave pubblica (da caricare sul portale PDND)
        pub_path = PKG_ROOT / "keys" / "public_key.pem"
        if pub_path.exists():
            st.download_button(
                "⬇️ Scarica chiave pubblica (da caricare su PDND)",
                data=pub_path.read_bytes(), file_name="public_key.pem")


# --------------------------------------------------------------------------- #
#  Sidebar: stato configurazione
# --------------------------------------------------------------------------- #
def render_sidebar(settings: Settings, ready: bool) -> None:
    """Pannello laterale: checklist di stato della configurazione (read-only)."""
    report = check_config(settings)
    with st.sidebar.expander("Stato configurazione", expanded=not ready):
        for line in report.lines:
            text = line.strip()
            if text.startswith("[ OK ]"):
                st.success(text)
            elif text.startswith("[FAIL]"):
                st.error(text)
            else:
                st.warning(text)
        st.caption("Le impostazioni si modificano nella pagina "
                   "⚙️ Impostazioni qui sopra.")


# --------------------------------------------------------------------------- #
#  Tema grafico (stile Bootstrap Italia / design-react-kit, come in ANPR Explorer)
# --------------------------------------------------------------------------- #
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Titillium Web', 'Segoe UI', Tahoma, sans-serif;
}

.pdnd-header {
    background-color: #0052A3;
    color: #ffffff;
    padding: 0.9rem 1.5rem;
    margin: -1rem -1rem 1rem -1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
}
.pdnd-header h1 {
    color: #ffffff;
    font-size: 1.25rem;
    font-weight: 700;
    margin: 0;
}

.pdnd-page-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}
.pdnd-page-title h2 {
    font-size: 1.1rem;
    font-weight: 700;
    margin: 0;
}

.pdnd-badge {
    display: inline-block;
    padding: 0.25rem 0.7rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
}
.pdnd-badge--ok { background-color: #006644; color: #fff; }
.pdnd-badge--warn { background-color: #7A4F00; color: #fff; }

.pdnd-footer {
    border-top: 1px solid #dee2e6;
    color: #6c757d;
    font-size: 0.85rem;
    text-align: center;
    padding: 1rem 0 0.5rem 0;
    margin-top: 2rem;
}
</style>
"""


def _inject_theme() -> None:
    """Inietta il CSS del tema (palette/font coerenti con Bootstrap Italia)."""
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def _render_header(ready: bool) -> None:
    """Barra superiore in stile Bootstrap Italia (bg-primary), con badge di stato."""
    badge_class = "pdnd-badge--ok" if ready else "pdnd-badge--warn"
    badge_text = "Configurato" if ready else "Da completare"
    st.markdown(
        f'<div class="pdnd-header">'
        f'<h1>📄 PDND DURC Batch</h1>'
        f'<span class="pdnd-badge {badge_class}">{badge_text}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.caption("Controllo e download massivo dei DURC tramite e-service INPS/ANAC su PDND.")


def _render_footer() -> None:
    """Piè di pagina in stile Bootstrap Italia (bordo + testo muted)."""
    st.markdown(
        '<div class="pdnd-footer">PDND DURC Batch — uso riservato agli operatori autorizzati</div>',
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
#  Esiti
# --------------------------------------------------------------------------- #
def render_results(settings: Settings) -> None:
    """Tabella degli esiti dallo stato persistito + download dei documenti."""
    repo = StateRepository(settings.state_db_url)
    rows = []
    counts: dict[str, int] = {}
    for status in RequestStatus:
        items = list(repo.get_by_status(status))
        counts[status.value] = len(items)
        for req in items:
            rows.append({
                "codice_fiscale": req.codice_fiscale,
                "stato": req.status.value,
                "request_id": req.request_id or "",
                "tentativi": req.attempts,
                "errore": req.last_error or "",
            })

    cols = st.columns(len(RequestStatus))
    for col, status in zip(cols, RequestStatus):
        col.metric(status.value, counts.get(status.value, 0))

    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("Nessun esito ancora. Avvia un controllo.")

    out_files = sorted(settings.output_dir.glob("durc_*")) if settings.output_dir.exists() else []
    if out_files:
        st.subheader("Documenti scaricati")
        for path in out_files:
            st.download_button(path.name, data=path.read_bytes(), file_name=path.name,
                               key=f"dl_{path.name}")


# --------------------------------------------------------------------------- #
#  App
# --------------------------------------------------------------------------- #
def main() -> None:
    """Punto di ingresso dell'app Streamlit.

    L'interfaccia e' divisa in due pagine separate (Consultazione / Impostazioni),
    come nel layout di ANPR Explorer: le chiavi/credenziali si compilano in una
    pagina dedicata, distinta dal flusso operativo di tutti i giorni.
    """
    st.set_page_config(page_title="PDND DURC Batch", page_icon="📄", layout="wide")
    _inject_theme()

    settings = Settings()                     # rilettura fresca del .env a ogni run
    setup_logging(settings.log_level, settings.log_dir)
    ready = settings.is_ready() and inspect_private_key(settings.private_key_path)[0]

    _render_header(ready)
    render_sidebar(settings, ready)

    def _page_consultazione() -> None:
        if not ready:
            st.warning("Configurazione incompleta: completa la pagina "
                       "⚙️ Impostazioni (parametri + chiave) prima di avviare.")

        st.subheader("1. Lista codici fiscali")
        uploaded = st.file_uploader("Carica un CSV (colonna 'codice_fiscale')", type=["csv"])
        if uploaded is not None:
            settings.input_csv.parent.mkdir(parents=True, exist_ok=True)
            settings.input_csv.write_bytes(uploaded.getvalue())
            st.success(f"CSV caricato in {settings.input_csv}")
        elif settings.input_csv.exists():
            st.info(f"Uso il CSV esistente: {settings.input_csv}")
        else:
            st.info("Nessun CSV: caricane uno qui sopra.")

        st.subheader("2. Esecuzione")
        can_run = ready and settings.input_csv.exists()
        if st.button("▶ Avvia controllo DURC", type="primary", disabled=not can_run):
            try:
                with st.spinner("Elaborazione in corso (auth PDND, chiamate e-service, polling)..."):
                    processor = build_processor(settings)
                    processor.run()
                st.success("Elaborazione completata.")
            except Exception as exc:  # noqa: BLE001 - mostra l'errore all'utente
                st.error(f"Errore durante l'elaborazione: {exc}")
                st.exception(exc)

        st.subheader("3. Esiti")
        render_results(settings)

        with st.expander("Log applicativo (ultime righe)"):
            st.code(_tail_log(settings), language="text")

    def _page_impostazioni() -> None:
        render_settings(settings, ready)

    pages = [
        st.Page(_page_consultazione, title="Consultazione", icon="📄", default=True),
        st.Page(_page_impostazioni, title="Impostazioni", icon="⚙️"),
    ]
    nav = st.navigation(pages, position="sidebar")
    nav.run()

    _render_footer()


if __name__ == "__main__":
    main()
