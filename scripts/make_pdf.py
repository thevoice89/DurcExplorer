"""Genera GUIDA.pdf (guida operativa + checklist) a partire da contenuto strutturato.

Uso:  python scripts/make_pdf.py
"""
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "GUIDA.pdf"

# Palette sobria
NAVY = (31, 59, 92)
GREY = (90, 90, 90)
LIGHT = (235, 239, 245)
CODE_BG = (244, 244, 244)


class Guide(FPDF):
    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 6, "PDND DURC Batch - Guida operativa", align="L")
        self.ln(8)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 6, f"Pag. {self.page_no()}", align="C")


def txt(s: str) -> str:
    """Rende il testo compatibile con i font core (latin-1)."""
    repl = {"→": "->", "←": "<-", "–": "-", "—": "-",
            "’": "'", "“": '"', "”": '"', "…": "...",
            "è": "è"}
    for a, b in repl.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def h1(pdf: Guide, s: str) -> None:
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(0, 8, txt(s))
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.5)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(3)


def h2(pdf: Guide, s: str) -> None:
    pdf.ln(2)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(0, 6, txt(s))
    pdf.ln(1)


def para(pdf: Guide, s: str) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(20, 20, 20)
    pdf.multi_cell(0, 5, txt(s))
    pdf.ln(1)


def bullet(pdf: Guide, s: str, indent: int = 0) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(20, 20, 20)
    x0 = pdf.l_margin + 3 + indent
    pdf.set_x(x0)
    pdf.cell(4, 5, txt("-"))
    pdf.set_x(x0 + 4)
    pdf.multi_cell(0, 5, txt(s))


def code(pdf: Guide, lines: list[str]) -> None:
    pdf.ln(1)
    pdf.set_font("Courier", "", 9)
    pdf.set_fill_color(*CODE_BG)
    pdf.set_text_color(20, 20, 20)
    for ln in lines:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5, txt("  " + ln), fill=True)
    pdf.ln(1)


def table(pdf: Guide, rows: list[tuple[str, str]], headers: tuple[str, str]) -> None:
    pdf.ln(1)
    pdf.set_x(pdf.l_margin)
    w1, w2 = 95, 80
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(w1, 7, txt(headers[0]), border=0, fill=True)
    pdf.cell(w2, 7, txt(headers[1]), border=0, fill=True)
    pdf.ln(7)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(20, 20, 20)
    fill = False
    for a, b in rows:
        pdf.set_fill_color(*LIGHT)
        x, y = pdf.get_x(), pdf.get_y()
        pdf.multi_cell(w1, 6, txt(a), border=0, fill=fill, max_line_height=6)
        y2 = pdf.get_y()
        pdf.set_xy(x + w1, y)
        pdf.multi_cell(w2, 6, txt(b), border=0, fill=fill, max_line_height=6)
        pdf.set_y(max(y2, pdf.get_y()))
        fill = not fill
    pdf.ln(2)


def checkbox(pdf: Guide, s: str) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(20, 20, 20)
    x0 = pdf.l_margin + 2
    pdf.set_x(x0)
    pdf.set_draw_color(*NAVY)
    y = pdf.get_y()
    pdf.rect(x0, y + 0.6, 3.5, 3.5)
    pdf.set_x(x0 + 7)
    pdf.multi_cell(0, 5, txt(s))
    pdf.ln(1)


def build() -> None:
    pdf = Guide()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Copertina leggera
    pdf.ln(6)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(0, 10, txt("PDND DURC Batch"))
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*GREY)
    pdf.multi_cell(0, 7, txt("Guida operativa - configurazione PDND e configurazione del programma"))
    pdf.ln(4)

    para(pdf, "Questa guida e' divisa in due parti. Dalla PDND si ottengono 5 valori "
              "+ 1 file (chiave privata) che poi si inseriscono nel programma.")
    table(pdf, [
        ("Client ID (UUID del client)", "PDND_CLIENT_ID"),
        ("Key ID (kid della chiave)", "PDND_KID"),
        ("Chiave privata RSA (file .pem)", "PDND_PRIVATE_KEY_PATH"),
        ("Purpose ID (id finalita')", "PDND_DURC_PURPOSE_ID"),
        ("Base URL e-service DURC", "PDND_DURC_BASE_URL"),
        ("Audience e-service DURC", "PDND_DURC_AUDIENCE"),
    ], ("Valore ottenuto dalla PDND", "Campo nel programma"))
    para(pdf, "Nota: gli endpoint di autenticazione sono gia' impostati sui valori di "
              "produzione; si cambiano solo per l'ambiente di collaudo (UAT).")

    # PARTE 1
    pdf.add_page()
    h1(pdf, "PARTE 1 - Configurazione su PDND")
    para(pdf, "Accesso dal portale PDND Interoperabilita' (area riservata, SPID/CIE). "
              "I nomi delle voci di menu possono variare nel tempo. "
              "Riferimento: developer.pagopa.it/pdnd-interoperabilita")

    h2(pdf, "1.1 Adesione dell'ente (se non gia' fatto)")
    bullet(pdf, "L'ente deve aver aderito alla PDND: l'adesione la fa il legale "
                "rappresentante (o delegato) con SPID/CIE.")
    bullet(pdf, "Vengono nominati un Amministratore e uno o piu' Operatori API: sono "
                "i ruoli che creano client e gestiscono le fruizioni.")

    h2(pdf, "1.2 Crea il client di fruizione e il materiale crittografico")
    bullet(pdf, "Crea un Client di fruizione (machine-to-machine).")
    bullet(pdf, "Annota il Client ID (UUID) -> PDND_CLIENT_ID.")
    bullet(pdf, "Genera la coppia di chiavi RSA (anche dal programma stesso).")
    bullet(pdf, "Carica la chiave PUBBLICA sul client: la PDND assegna un kid -> PDND_KID.")
    bullet(pdf, "La chiave PRIVATA non si carica mai: resta sulla tua macchina e serve "
                "a firmare le richieste.")

    h2(pdf, "1.3 Trova l'e-service DURC nel catalogo")
    bullet(pdf, "Nel Catalogo e-service cerca il servizio DURC dell'erogatore (es. INPS/ANAC).")
    bullet(pdf, "Dal descrittore annota il Base URL del server -> PDND_DURC_BASE_URL.")
    bullet(pdf, "Annota l'Audience dichiarata -> PDND_DURC_AUDIENCE.")

    h2(pdf, "1.4 Richiedi la fruizione e crea la finalita' (purpose)")
    bullet(pdf, "Avvia la Richiesta di fruizione (iscrizione al servizio) col tuo client.")
    bullet(pdf, "Crea una Finalita' (purpose) che descrive l'uso del servizio e collegala al client.")
    bullet(pdf, "La fruizione/finalita' va approvata dall'erogatore. Quando e' attiva "
                "ottieni il Purpose ID -> PDND_DURC_PURPOSE_ID.")

    h2(pdf, "1.5 (Opzionale) Ambiente di collaudo")
    bullet(pdf, "Prima della produzione, ripeti i passi in collaudo (UAT) e nel programma "
                "sovrascrivi PDND_TOKEN_ENDPOINT e PDND_AUTH_AUDIENCE con gli URL UAT.")
    pdf.ln(1)
    para(pdf, "Al termine della Parte 1 devi avere: Client ID, kid, file private_key.pem, "
              "Purpose ID, Base URL e Audience dell'e-service.")

    # PARTE 2
    pdf.add_page()
    h1(pdf, "PARTE 2 - Configurazione del programma")
    para(pdf, "Due modi equivalenti: interfaccia grafica (consigliata) o file di testo .env.")

    h2(pdf, "Prerequisiti (una sola volta)")
    code(pdf, [
        "cd C:\\Users\\dgrioni\\Desktop\\pdnd",
        ".\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt",
    ])

    h2(pdf, "Modo A - Interfaccia grafica (consigliato)")
    code(pdf, [".\\.venv\\Scripts\\python.exe -m streamlit run streamlit_app.py"])
    bullet(pdf, "Si apre il browser su http://localhost:8501.")
    bullet(pdf, "Apri la sezione Impostazioni (gia' aperta se la config e' incompleta).")
    bullet(pdf, "In 'Credenziali e parametri PDND' inserisci i 5 valori e premi Salva parametri.")
    bullet(pdf, "In 'Chiave privata RSA': carica il tuo file .pem, oppure genera la coppia "
                "e scarica la pubblica da caricare su PDND.")
    bullet(pdf, "Controlla che la sidebar sia tutta verde [ OK ].")
    bullet(pdf, "Carica il CSV (colonna codice_fiscale) e premi Avvia controllo DURC.")

    h2(pdf, "Modo B - File di configurazione (.env)")
    code(pdf, [
        ".\\.venv\\Scripts\\python.exe -m durc_batch.doctor --init",
        ".\\.venv\\Scripts\\python.exe -m durc_batch.doctor --gen-key",
        "# compila i 5 campi nel file .env, poi:",
        ".\\.venv\\Scripts\\python.exe -m durc_batch.doctor",
        ".\\.venv\\Scripts\\python.exe -m durc_batch.main",
    ])
    bullet(pdf, "doctor --init crea il .env; doctor --gen-key crea la coppia di chiavi.")
    bullet(pdf, "Compila PDND_CLIENT_ID, PDND_KID, PDND_DURC_BASE_URL, "
                "PDND_DURC_PURPOSE_ID, PDND_DURC_AUDIENCE.")
    bullet(pdf, "doctor deve stampare PRONTO prima di lanciare main.")

    h2(pdf, "Dove finiscono i risultati")
    bullet(pdf, "Documenti DURC -> data\\output\\ (es. durc_<codicefiscale>.pdf)")
    bullet(pdf, "Stato richieste -> data\\state.db (le pratiche gia' completate vengono saltate)")
    bullet(pdf, "Log -> logs\\durc_batch.log")

    h2(pdf, "Sicurezza")
    bullet(pdf, "Non condividere/versionare private_key.pem ne' .env (gia' esclusi da git).")
    bullet(pdf, "Sul portale PDND carichi solo la chiave pubblica.")

    # CHECKLIST
    pdf.add_page()
    h1(pdf, "Checklist - dati da raccogliere dalla PDND")
    para(pdf, "Spunta ogni voce man mano che la ottieni dal portale. Quando sono tutte "
              "spuntate, hai tutto per configurare il programma.")
    pdf.ln(2)
    h2(pdf, "Credenziali del client")
    checkbox(pdf, "Client ID (UUID) ................... PDND_CLIENT_ID:  ______________________")
    checkbox(pdf, "Key ID (kid) ....................... PDND_KID:        ______________________")
    checkbox(pdf, "Chiave privata RSA salvata in keys\\private_key.pem")
    checkbox(pdf, "Chiave pubblica caricata sul portale PDND")
    pdf.ln(2)
    h2(pdf, "E-service DURC")
    checkbox(pdf, "Base URL ........................... PDND_DURC_BASE_URL: __________________")
    checkbox(pdf, "Audience ........................... PDND_DURC_AUDIENCE: __________________")
    checkbox(pdf, "Purpose ID (finalita' approvata) ... PDND_DURC_PURPOSE_ID: ________________")
    pdf.ln(2)
    h2(pdf, "Verifica finale")
    checkbox(pdf, "doctor stampa 'PRONTO' / sidebar tutta verde")
    checkbox(pdf, "CSV con i codici fiscali pronto (colonna codice_fiscale)")

    pdf.output(str(OUT))
    print(f"PDF generato: {OUT} ({OUT.stat().st_size // 1024} KB, {pdf.page_no()} pagine)")


if __name__ == "__main__":
    build()
