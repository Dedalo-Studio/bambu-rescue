# -*- coding: utf-8 -*-
"""
Modulo: recupero_bambu_3mf_gui.py
Descrizione: Interfaccia Grafica Utente Moderna (CustomTkinter) per Bambu Rescue.
             Completamente ridisegnata con design a schede, schede informative,
             barra di avanzamento in tempo reale, diagnostica integrata e guida d'uso.

Autore originale: 小岛秀夫 (MakerWorld)
Supporto tecnico autore originale: 耀阳 (WeChat: d570565010)
Adattamento, UX Moderna e localizzazione italiana: 2026
"""

import contextlib
import ctypes
import io
import os
import subprocess
import sys
import threading
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import recupero_bambu_3mf as engine

# Attiva il supporto High-DPI per Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Configurazione stile CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# Palette colori Bambu Rescue
BG_DARK = "#0C1319"
CARD_BG = "#15202B"
CARD_BORDER = "#223344"
ACCENT_GREEN = "#00AE68"
ACCENT_GREEN_HOVER = "#10C87B"
ACCENT_AMBER = "#E09F3E"
ACCENT_AMBER_HOVER = "#F2B657"
ACCENT_RED = "#FF6B6B"
TEXT_MAIN = "#F1F7F5"
TEXT_MUTED = "#8EACB5"


def get_risorsa_path(rel_path):
    """Restituisce il percorso assoluto alla risorsa, supportando anche l'ambiente PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(os.path.abspath("."), rel_path)


class BambuRescueApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Bambu Rescue · Recupero Progetti 3MF da Crash")
        self.geometry("1060x860")
        self.minsize(880, 700)
        self.configure(fg_color=BG_DARK)

        # Imposta icona se disponibile
        icona = get_risorsa_path("app_icon.ico")
        if os.path.exists(icona):
            try:
                self.iconbitmap(icona)
            except Exception:
                pass

        # Variabili di stato
        self.tutte_sessioni_valide = []
        self.sessioni_trovate = []
        self.sessione_corrente = None
        self.file_output = ""
        self.file_fallback = ""
        self.ultimo_recuperato = None

        self._costruisci_ui()
        self._ricerca_sessioni()

    def _costruisci_ui(self):
        # 1. HEADER BAR
        header = ctk.CTkFrame(self, fg_color="#101820", corner_radius=0, height=72)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        header_content = ctk.CTkFrame(header, fg_color="transparent")
        header_content.pack(fill="both", expand=True, padx=24, pady=10)

        # Logo e titolo a sinistra
        left_box = ctk.CTkFrame(header_content, fg_color="transparent")
        left_box.pack(side="left", fill="y")

        brand_badge = ctk.CTkLabel(
            left_box,
            text=" BAMBU RESCUE ",
            fg_color=ACCENT_GREEN,
            text_color="#04150E",
            corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        )
        brand_badge.pack(side="left", padx=(0, 12))

        title_box = ctk.CTkFrame(left_box, fg_color="transparent")
        title_box.pack(side="left", fill="y")

        lbl_titolo = ctk.CTkLabel(
            title_box,
            text="Ripristino Progetti 3MF da Crash",
            text_color=TEXT_MAIN,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold")
        )
        lbl_titolo.pack(anchor="w")

        lbl_sub = ctk.CTkLabel(
            title_box,
            text="Estrae geometrie e modelli ZIP annidati dalla cache temporanea di Bambu Studio",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        lbl_sub.pack(anchor="w")

        # Pulsanti a destra
        right_box = ctk.CTkFrame(header_content, fg_color="transparent")
        right_box.pack(side="right", fill="y")

        btn_info = ctk.CTkButton(
            right_box,
            text="Info & Licenza",
            fg_color="#1F2E3D",
            hover_color="#2E4358",
            text_color=TEXT_MAIN,
            width=110,
            height=32,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._mostra_info_licenza
        )
        btn_info.pack(side="right", padx=(8, 0))

        btn_aggiorna = ctk.CTkButton(
            right_box,
            text="🔄 Riscansiona",
            fg_color="#1F2E3D",
            hover_color="#2E4358",
            text_color=TEXT_MAIN,
            width=110,
            height=32,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._ricerca_sessioni
        )
        btn_aggiorna.pack(side="right", padx=(0, 8))

        # 2. MAIN CONTAINER CON TABVIEW
        self.tabview = ctk.CTkTabview(
            self,
            fg_color="transparent",
            segmented_button_fg_color="#15202B",
            segmented_button_selected_color=ACCENT_GREEN,
            segmented_button_selected_hover_color=ACCENT_GREEN_HOVER,
            segmented_button_unselected_color="#1C2B3A",
            segmented_button_unselected_hover_color="#273C51",
            text_color=TEXT_MAIN
        )
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(6, 10))

        self.tab_recupero = self.tabview.add(" 🚀 Recupero Guidato ")
        self.tab_diagnostica = self.tabview.add(" 🔍 Diagnostica & Cache ")
        self.tab_guida = self.tabview.add(" 📖 Come Funziona ")

        self._costruisci_tab_recupero()
        self._costruisci_tab_diagnostica()
        self._costruisci_tab_guida()

    def _costruisci_tab_recupero(self):
        parent = self.tab_recupero

        # Layout a due colonne perfettamente bloccato (nessun ricalcolo o salto di larghezza)
        parent.columnconfigure(0, weight=5, uniform="tab_cols")
        parent.columnconfigure(1, weight=4, uniform="tab_cols")
        parent.rowconfigure(0, weight=1)

        left_col = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)

        right_col = ctk.CTkFrame(parent, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)


        # --- COLONNA SINISTRA: SCHEDE GUIDATE ---

        # 1. CARD SELEZIONE CRASH
        card_crash = ctk.CTkFrame(left_col, fg_color=CARD_BG, border_color=CARD_BORDER, border_width=1, corner_radius=12)
        card_crash.pack(fill="x", pady=(0, 12))

        c1_head = ctk.CTkFrame(card_crash, fg_color="transparent")
        c1_head.pack(fill="x", padx=16, pady=(14, 6))

        ctk.CTkLabel(
            c1_head,
            text="① Seleziona la Sessione del Crash",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_MAIN
        ).pack(side="left")

        self.lbl_crash_badge = ctk.CTkLabel(
            c1_head,
            text="0 sessioni",
            fg_color="#223344",
            text_color=ACCENT_GREEN,
            corner_radius=6,
            font=ctk.CTkFont(size=10, weight="bold"),
            padx=8,
            pady=2
        )
        self.lbl_crash_badge.pack(side="right")

        self.combo_sessioni = ctk.CTkOptionMenu(
            card_crash,
            values=["Ricerca in corso..."],
            fg_color="#1F2E3D",
            button_color="#273C51",
            button_hover_color=ACCENT_GREEN,
            dropdown_fg_color="#15202B",
            dropdown_hover_color="#223344",
            dropdown_text_color=TEXT_MAIN,
            text_color=TEXT_MAIN,
            font=ctk.CTkFont(size=12),
            height=36,
            command=self._su_cambio_sessione
        )
        self.combo_sessioni.pack(fill="x", padx=16, pady=6)

        # Dettagli rapidi sessione selezionata (Quick Info Card)
        self.info_box = ctk.CTkFrame(card_crash, fg_color="#0F171F", corner_radius=8)
        self.info_box.pack(fill="x", padx=16, pady=(6, 8))

        self.lbl_info_stato = ctk.CTkLabel(
            self.info_box,
            text="🟢 Stato: -",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=ACCENT_GREEN,
            wraplength=420,
            justify="left"
        )
        self.lbl_info_stato.pack(anchor="w", padx=12, pady=(8, 3))

        self.lbl_info_data = ctk.CTkLabel(self.info_box, text="📅 Data & Ora: -", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED)
        self.lbl_info_data.pack(anchor="w", padx=12, pady=2)

        self.lbl_info_oggetti = ctk.CTkLabel(self.info_box, text="🧩 Modelli 3D recuperabili: -", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED)
        self.lbl_info_oggetti.pack(anchor="w", padx=12, pady=2)

        self.lbl_info_origine = ctk.CTkLabel(
            self.info_box,
            text="🏷️ Progetto di origine: -",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
            wraplength=420,
            justify="left"
        )
        self.lbl_info_origine.pack(anchor="w", padx=12, pady=(2, 8))

        self.switch_mostra_gcode = ctk.CTkSwitch(
            card_crash,
            text="Mostra anche sessioni chiuse con solo G-code/slice in Metadata",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
            progress_color=ACCENT_AMBER,
            command=self._filtra_e_popola_sessioni
        )
        self.switch_mostra_gcode.pack(anchor="w", padx=16, pady=(2, 4))

        btn_sfoglia_input = ctk.CTkButton(
            card_crash,
            text="📁 Sfoglia manualmente un'altra cartella...",
            fg_color="transparent",
            text_color=ACCENT_GREEN,
            hover_color="#1C2B3A",
            anchor="w",
            font=ctk.CTkFont(size=11, underline=True),
            command=self._sfoglia_input
        )
        btn_sfoglia_input.pack(fill="x", padx=16, pady=(0, 10))

        # 2. CARD DESTINAZIONE
        card_dest = ctk.CTkFrame(left_col, fg_color=CARD_BG, border_color=CARD_BORDER, border_width=1, corner_radius=12)
        card_dest.pack(fill="x", pady=(0, 12))

        c2_head = ctk.CTkFrame(card_dest, fg_color="transparent")
        c2_head.pack(fill="x", padx=16, pady=(14, 6))

        ctk.CTkLabel(
            c2_head,
            text="② Dove salvare il File 3MF Ricostruito",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_MAIN
        ).pack(side="left")

        dest_input_box = ctk.CTkFrame(card_dest, fg_color="transparent")
        dest_input_box.pack(fill="x", padx=16, pady=6)

        self.entry_destinazione = ctk.CTkEntry(
            dest_input_box,
            placeholder_text="Percorso del file .3mf recuperato...",
            fg_color="#0F171F",
            border_color="#223344",
            text_color=TEXT_MAIN,
            height=36
        )
        self.entry_destinazione.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_sfoglia_dest = ctk.CTkButton(
            dest_input_box,
            text="Sfoglia...",
            width=80,
            height=36,
            fg_color="#1F2E3D",
            hover_color="#2E4358",
            command=self._sfoglia_output
        )
        btn_sfoglia_dest.pack(side="right")

        # Scorciatoie veloci
        shortcuts_box = ctk.CTkFrame(card_dest, fg_color="transparent")
        shortcuts_box.pack(fill="x", padx=16, pady=(2, 12))

        ctk.CTkLabel(shortcuts_box, text="Scorciatoie:", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(side="left", padx=(0, 8))

        btn_quick_doc = ctk.CTkButton(
            shortcuts_box,
            text="Documenti",
            width=75,
            height=24,
            fg_color="#1C2B3A",
            hover_color="#2A3E54",
            font=ctk.CTkFont(size=10),
            command=lambda: self._imposta_cartella_dest(Path.home() / "Documents")
        )
        btn_quick_doc.pack(side="left", padx=4)

        btn_quick_desk = ctk.CTkButton(
            shortcuts_box,
            text="Desktop",
            width=75,
            height=24,
            fg_color="#1C2B3A",
            hover_color="#2A3E54",
            font=ctk.CTkFont(size=10),
            command=lambda: self._imposta_cartella_dest(Path.home() / "Desktop")
        )
        btn_quick_desk.pack(side="left", padx=4)

        # 3. CARD OPZIONI E FALLBACK (INTEGRAZIONE)
        card_opts = ctk.CTkFrame(left_col, fg_color=CARD_BG, border_color=CARD_BORDER, border_width=1, corner_radius=12)
        card_opts.pack(fill="x", pady=(0, 12))

        c3_head = ctk.CTkFrame(card_opts, fg_color="transparent")
        c3_head.pack(fill="x", padx=16, pady=(14, 6))

        ctk.CTkLabel(
            c3_head,
            text="③ Sicurezza & Integrazione Avanzata",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_MAIN
        ).pack(side="left")

        self.switch_backup = ctk.CTkSwitch(
            card_opts,
            text="Crea copia di backup ZIP dei dati grezzi prima del recupero (Consigliato)",
            font=ctk.CTkFont(size=11),
            progress_color=ACCENT_GREEN
        )
        self.switch_backup.select()
        self.switch_backup.pack(anchor="w", padx=16, pady=6)

        fallback_box = ctk.CTkFrame(card_opts, fg_color="transparent")
        fallback_box.pack(fill="x", padx=16, pady=(6, 12))

        ctk.CTkLabel(
            fallback_box,
            text="File di origine pre-crash (usato per integrare oggetti non modificati):",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED
        ).pack(anchor="w", pady=(0, 4))

        fb_row = ctk.CTkFrame(fallback_box, fg_color="transparent")
        fb_row.pack(fill="x")

        self.entry_fallback = ctk.CTkEntry(
            fb_row,
            placeholder_text="Opzionale (lascia vuoto se era un nuovo progetto non salvato)...",
            fg_color="#0F171F",
            border_color="#223344",
            text_color=TEXT_MAIN,
            height=34
        )
        self.entry_fallback.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_sfoglia_fb = ctk.CTkButton(
            fb_row,
            text="Sfoglia...",
            width=80,
            height=34,
            fg_color="#1F2E3D",
            hover_color="#2E4358",
            command=self._sfoglia_fallback
        )
        btn_sfoglia_fb.pack(side="right")

        # --- COLONNA DESTRA: AZIONI, LOG E SUCCESSO ---
        right_col.rowconfigure(2, weight=1)
        right_col.columnconfigure(0, weight=1)

        # Card Azione Principale
        card_action = ctk.CTkFrame(right_col, fg_color=CARD_BG, border_color=CARD_BORDER, border_width=1, corner_radius=12)
        card_action.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.btn_avvia = ctk.CTkButton(
            card_action,
            text="🚀  AVVIA RECUPERO E RICOSTRUZIONE 3MF",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=ACCENT_GREEN,
            hover_color=ACCENT_GREEN_HOVER,
            text_color="#04150E",
            height=50,
            corner_radius=10,
            command=self._avvia_recupero
        )
        self.btn_avvia.pack(fill="x", padx=16, pady=16)

        # Barra di avanzamento e stato
        self.progress_bar = ctk.CTkProgressBar(card_action, progress_color=ACCENT_GREEN, fg_color="#1C2B3A", height=8)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 8))

        self.lbl_stato = ctk.CTkLabel(
            card_action,
            text="PRONTO PER IL RECUPERO",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=ACCENT_GREEN,
            wraplength=400,
            justify="center"
        )
        self.lbl_stato.pack(pady=(0, 14))


        # Card Risultato / Azioni rapide post recupero (inizialmente nascosta o disattivata)
        self.card_result = ctk.CTkFrame(right_col, fg_color="#12251D", border_color=ACCENT_GREEN, border_width=1, corner_radius=12)
        self.card_result.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        lbl_res_titolo = ctk.CTkLabel(
            self.card_result,
            text="✨ File Ricostruito con Successo!",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=ACCENT_GREEN
        )
        lbl_res_titolo.pack(anchor="w", padx=16, pady=(12, 4))

        res_btn_box = ctk.CTkFrame(self.card_result, fg_color="transparent")
        res_btn_box.pack(fill="x", padx=16, pady=(4, 12))

        self.btn_apri_bambu = ctk.CTkButton(
            res_btn_box,
            text="Apri con Bambu Studio",
            fg_color=ACCENT_GREEN,
            hover_color=ACCENT_GREEN_HOVER,
            text_color="#04150E",
            height=32,
            font=ctk.CTkFont(size=11, weight="bold"),
            state="disabled",
            command=self._apri_file_con_bambu
        )
        self.btn_apri_bambu.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_mostra_cartella = ctk.CTkButton(
            res_btn_box,
            text="Mostra nella Cartella",
            fg_color="#1F2E3D",
            hover_color="#2E4358",
            text_color=TEXT_MAIN,
            height=32,
            font=ctk.CTkFont(size=11, weight="bold"),
            state="disabled",
            command=self._apri_cartella_destinazione
        )
        self.btn_mostra_cartella.pack(side="right", fill="x", expand=True, padx=(6, 0))

        # Card Log delle Operazioni
        card_log = ctk.CTkFrame(right_col, fg_color=CARD_BG, border_color=CARD_BORDER, border_width=1, corner_radius=12)
        card_log.grid(row=2, column=0, sticky="nsew", pady=0)

        log_head = ctk.CTkFrame(card_log, fg_color="transparent")
        log_head.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(
            log_head,
            text="REGISTRO DELLE OPERAZIONI",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_MUTED
        ).pack(side="left")

        btn_pulisci_log = ctk.CTkButton(
            log_head,
            text="Pulisci",
            width=60,
            height=22,
            fg_color="#1C2B3A",
            hover_color="#2E4358",
            font=ctk.CTkFont(size=10),
            command=self._pulisci_log
        )
        btn_pulisci_log.pack(side="right")

        self.txt_log = ctk.CTkTextbox(
            card_log,
            fg_color="#090E13",
            text_color="#A8D5C8",
            font=ctk.CTkFont(family="Consolas", size=10),
            corner_radius=8,
            wrap="char"
        )
        self.txt_log.pack(fill="both", expand=True, padx=12, pady=(0, 12))


    def _costruisci_tab_diagnostica(self):
        parent = self.tab_diagnostica

        card = ctk.CTkFrame(parent, fg_color=CARD_BG, border_color=CARD_BORDER, border_width=1, corner_radius=12)
        card.pack(fill="both", expand=True, padx=20, pady=10)

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 8))

        ctk.CTkLabel(
            head,
            text="Ispezione Approfondita della Cartella di Crash",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_MAIN
        ).pack(side="left")

        btn_apri_cache = ctk.CTkButton(
            head,
            text="📂 Apri Cartella Cache Temp di Windows",
            fg_color="#1F2E3D",
            hover_color="#2E4358",
            command=self._apri_cache_temp
        )
        btn_apri_cache.pack(side="right")

        ctk.CTkLabel(
            card,
            text="Analizza la struttura interna dei file residui per verificare modelli sfusi, ZIP annidati e relazioni:",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED
        ).pack(anchor="w", padx=20, pady=(0, 10))

        btn_esegui_ispezione = ctk.CTkButton(
            card,
            text="🔍 Esegui Ispezione Diagnostica sulla Sessione Corrente",
            fg_color="#1C2B3A",
            hover_color=ACCENT_GREEN,
            height=36,
            command=self._ispeziona_diagnostica
        )
        btn_esegui_ispezione.pack(fill="x", padx=20, pady=(0, 10))

        self.txt_diagnostica = ctk.CTkTextbox(
            card,
            fg_color="#090E13",
            text_color="#B9DCD2",
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8
        )
        self.txt_diagnostica.pack(fill="both", expand=True, padx=20, pady=(0, 16))

    def _costruisci_tab_guida(self):
        parent = self.tab_guida

        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        def crea_sezione_guida(titolo, testo):
            c = ctk.CTkFrame(scroll, fg_color=CARD_BG, border_color=CARD_BORDER, border_width=1, corner_radius=10)
            c.pack(fill="x", pady=6)
            ctk.CTkLabel(c, text=titolo, font=ctk.CTkFont(size=13, weight="bold"), text_color=ACCENT_GREEN).pack(anchor="w", padx=16, pady=(12, 4))
            ctk.CTkLabel(c, text=testo, font=ctk.CTkFont(size=12), text_color=TEXT_MAIN, justify="left", wraplength=950).pack(anchor="w", padx=16, pady=(0, 12))

        crea_sezione_guida(
            "1. Perché Bambu Studio perde i file durante un crash?",
            "Durante la lavorazione di un piatto, Bambu Studio salva in tempo reale copie parziali nella cartella "
            "%LOCALAPPDATA%\\Temp\\bamboo_model. In caso di chiusura improvvisa o crash, il file finale .3mf non viene "
            "completato, lasciando sul disco modelli sparsi e archivi provvisori."
        )

        crea_sezione_guida(
            "2. Il mistero dei falsi file '.model' (ZIP annidati)",
            "Nei salvataggi parziali di Bambu Studio, i singoli modelli 3D (object_1.model, object_2.model) vengono spesso "
            "compressi internamente come archivi ZIP con l'estensione rinominata in .model. Se provi a creare un file 3MF "
            "senza scompattarli, Bambu Studio non riuscirà a leggere la geometria XML e mostrerà un piatto vuoto. "
            "Bambu Rescue rileva automaticamente questi file ed estrae la geometria XML reale al loro interno."
        )

        crea_sezione_guida(
            "3. Pulizia delle relazioni e convalidazione ZIP64",
            "Un file 3MF è a tutti gli effetti un pacchetto ZIP standard Open Packaging Conventions (OPC). Durante un crash, "
            "le relazioni (_rels/.rels) possono fare riferimento a miniature non salvate, bloccando l'apertura. Questo software "
            "ripulisce i riferimenti orfani, ricompone il pacchetto con supporto ZIP64 (essenziale per modelli molto pesanti da vari gigabyte) "
            "e ne verifica il CRC di integrità."
        )

        crea_sezione_guida(
            "4. A cosa serve il file di fallback?",
            "Se stavi modificando un progetto esistente già salvato sul computer (es. Homer.3mf), Bambu Studio potrebbe non aver riscritto "
            "tutti gli oggetti nella cache temporanea ma solo quelli toccati di recente. Indicando il file originale come fallback "
            "(spesso rilevato in automatico tramite origin.txt), il programma integrerà gli oggetti mancanti senza perdere nulla."
        )

        crea_sezione_guida(
            "5. Differenza tra Crash 3D (🟢) e Sessione Chiusa / Solo G-code (🟡)",
            "Quando Bambu Studio si chiude normalmente (senza crash), cancella in automatico i modelli 3D e il .3mf temporaneo dalla cache, "
            "lasciando spesso solo le anteprime e gli eventuali file di stampa già affettati (.gcode.3mf) nella sottocartella Metadata/. "
            "Di default Bambu Rescue ti mostra solo i crash realmente recuperabili come progetto 3D (🟢). Se però ti serve recuperare almeno "
            "il G-code di un piatto già affettato prima della chiusura, attiva l'opzione 'Mostra anche sessioni chiuse con solo G-code'."
        )

    # --- LOGICA APPLICATIVA ---

    def _scrivi_log(self, testo):
        self.txt_log.insert("end", testo + "\n")
        self.txt_log.see("end")

    def _pulisci_log(self):
        self.txt_log.delete("1.0", "end")

    def _ricerca_sessioni(self):
        self._scrivi_log("[SCANSIONE] Ricerca delle sessioni nella cartella temporanea...")
        try:
            self.tutte_sessioni_valide = engine.scopri_sessioni_crash(
                includi_solo_gcode=True, includi_vuote=False
            )
        except Exception as e:
            self._scrivi_log(f"[ERRORE] Errore durante la ricerca: {e}")
            self.tutte_sessioni_valide = []

        n_rec = sum(1 for s in self.tutte_sessioni_valide if s["stato"] == "recuperabile")
        n_gcode = sum(1 for s in self.tutte_sessioni_valide if s["stato"] == "solo_gcode")

        if n_rec == 0 and n_gcode > 0 and not self.switch_mostra_gcode.get():
            self.switch_mostra_gcode.select()
            self._scrivi_log(
                f"[INFO] Nessun crash 3D attivo trovato, ma sono disponibili {n_gcode} sessioni "
                "chiuse con file slice/G-code in Metadata."
            )

        self._filtra_e_popola_sessioni(log_riepilogo=True)

    def _filtra_e_popola_sessioni(self, log_riepilogo=False):
        includi_gcode = bool(self.switch_mostra_gcode.get())
        if includi_gcode:
            self.sessioni_trovate = list(self.tutte_sessioni_valide)
        else:
            self.sessioni_trovate = [
                s for s in self.tutte_sessioni_valide if s["stato"] == "recuperabile"
            ]

        n_rec = sum(1 for s in self.tutte_sessioni_valide if s["stato"] == "recuperabile")
        n_gcode = sum(1 for s in self.tutte_sessioni_valide if s["stato"] == "solo_gcode")

        if self.sessioni_trovate:
            voci = []
            for s in self.sessioni_trovate:
                orig_nome = s["origine"].name if s["origine"] else s.get("origine_nome")
                orig = f" · {orig_nome}" if orig_nome else ""
                if s["stato"] == "recuperabile":
                    dettaglio = f"{s['oggetti']} mod. 3D" if s["oggetti"] > 0 else ".3mf base"
                    voci.append(f"✅ {s['data_leggibile']}  ·  {dettaglio}{orig}")
                else:
                    n_sl = len(s.get("gcode_3mf", [])) + len(s.get("gcode_raw", []))
                    voci.append(f"🖨️ [Solo G-code] {s['data_leggibile']}  ·  {n_sl} slice{orig}")

            badge_txt = f"{n_rec} crash 3D" if not includi_gcode else f"{n_rec} crash + {n_gcode} slice"
            self.lbl_crash_badge.configure(text=badge_txt)
            self.combo_sessioni.configure(values=voci)
            self.combo_sessioni.set(voci[0])
            self._imposta_sessione(0)

            if log_riepilogo:
                msg = f"[SUCCESSO] Trovati {n_rec} crash 3D recuperabili"
                if n_gcode > 0:
                    msg += f" (e {n_gcode} sessioni chiuse con solo G-code in Metadata)"
                self._scrivi_log(msg + ".")
        else:
            self.sessioni_trovate = []
            self.sessione_corrente = None
            self.lbl_crash_badge.configure(text="0 sessioni")
            self.combo_sessioni.configure(values=["Nessuna sessione recuperabile trovata"])
            self.combo_sessioni.set("Nessuna sessione recuperabile trovata")
            self.lbl_info_stato.configure(
                text="⚪ Nessuna sessione trovata in cache. Usa 'Sfoglia manualmente...' se i file sono altrove.",
                text_color=TEXT_MUTED
            )
            self.lbl_info_data.configure(text="📅 Data & Ora: -")
            self.lbl_info_oggetti.configure(text="🧩 Modelli 3D recuperabili: -")
            self.lbl_info_origine.configure(text="🏷️ Progetto di origine: -")
            self._aggiorna_pulsante_azione()
            if log_riepilogo:
                self._scrivi_log("[INFO] Nessuna sessione recuperabile trovata automaticamente.")

    def _aggiorna_pulsante_azione(self):
        if not self.sessione_corrente:
            self.btn_avvia.configure(
                text="🚀  AVVIA RECUPERO E RICOSTRUZIONE 3MF",
                fg_color=ACCENT_GREEN,
                hover_color=ACCENT_GREEN_HOVER,
                text_color="#04150E",
                state="normal"
            )
            return

        stato = self.sessione_corrente.get("stato", "vuota")
        if stato == "recuperabile":
            self.btn_avvia.configure(
                text="🚀  AVVIA RECUPERO E RICOSTRUZIONE 3MF",
                fg_color=ACCENT_GREEN,
                hover_color=ACCENT_GREEN_HOVER,
                text_color="#04150E",
                state="normal"
            )
            self.lbl_stato.configure(text="PRONTO PER IL RECUPERO 3D", text_color=ACCENT_GREEN)
        elif stato == "solo_gcode":
            self.btn_avvia.configure(
                text="🖨️  ESTRAI FILE G-CODE / SLICE DA METADATA",
                fg_color=ACCENT_AMBER,
                hover_color=ACCENT_AMBER_HOVER,
                text_color="#1A1200",
                state="normal"
            )
            self.lbl_stato.configure(text="DISPONIBILE SOLO ESTRAZIONE G-CODE / SLICE", text_color=ACCENT_AMBER)
        else:
            self.btn_avvia.configure(
                text="⚠️  CARTELLA VUOTA (NESSUN DATO RECUPERABILE)",
                fg_color="#3B2328",
                hover_color="#4E2D34",
                text_color="#FFB3B3",
                state="normal"
            )
            self.lbl_stato.configure(text="SESSIONE GIÀ SVUOTATA DA BAMBU STUDIO", text_color=ACCENT_RED)

    def _su_cambio_sessione(self, valore_scelto):
        valori = self.combo_sessioni.cget("values")
        if valore_scelto in valori:
            idx = valori.index(valore_scelto)
            self._imposta_sessione(idx)

    def _imposta_sessione(self, indice):
        if not (0 <= indice < len(self.sessioni_trovate)):
            return

        s = self.sessioni_trovate[indice]
        p = s["path"]

        # Se origin.txt indica un file non trovato al path diretto, esegue ricerca profonda una sola volta
        if s.get("origine") is None and s.get("origine_nome"):
            trovato = engine.trova_progetto_originale(p, ricerca_profonda=True)
            if trovato:
                s["origine"] = trovato

        self.sessione_corrente = s
        stato = s.get("stato", "vuota")

        # Aggiorna Quick Info Card
        if stato == "recuperabile":
            dettaglio_base = "file .3mf base + " if s.get("ha_base") else "solo modelli sfusi + "
            self.lbl_info_stato.configure(
                text=f"🟢 Stato: Crash 3D recuperabile ({dettaglio_base}{s['oggetti']} modelli)",
                text_color=ACCENT_GREEN
            )
        elif stato == "solo_gcode":
            n_3mf = len(s.get("gcode_3mf", []))
            n_gc = len(s.get("gcode_raw", []))
            self.lbl_info_stato.configure(
                text=(
                    f"🟡 Stato: Sessione chiusa normalmente — i modelli 3D sono stati rimossi da Bambu Studio, "
                    f"ma restano {n_3mf} pacchetti .gcode.3mf e {n_gc} file .gcode in Metadata."
                ),
                text_color=ACCENT_AMBER
            )
        else:
            self.lbl_info_stato.configure(
                text="🔴 Stato: Cartella svuotata da Bambu Studio (nessun file 3D o G-code presente).",
                text_color=ACCENT_RED
            )

        self.lbl_info_data.configure(text=f"📅 Data & Ora sessione:  {s['data_leggibile']}")
        self.lbl_info_oggetti.configure(text=f"🧩 Modelli 3D in cache:  {s['oggetti']} oggetti geometrici")

        if s.get("origine"):
            orig_text = str(s["origine"])
        elif s.get("origine_nome"):
            orig_text = f"{s['origine_nome']} (file originale spostato o eliminato)"
        else:
            orig_text = "Nuovo progetto (non salvato su disco prima del crash)"
        self.lbl_info_origine.configure(text=f"🏷️ Progetto di origine:  {orig_text}")

        # Imposta destinazione proposta
        if s.get("origine") and s["origine"].is_file():
            stem_base = s["origine"].stem
        elif s.get("origine_nome"):
            stem_base = Path(s["origine_nome"]).stem
        else:
            stem_base = f"Bambu_{p.name.replace('#', '_')}"

        if stato == "solo_gcode":
            if s.get("gcode_3mf"):
                nome_file = f"{stem_base}_slice.gcode.3mf"
            else:
                nome_file = f"{stem_base}_slice.gcode"
        else:
            nome_file = f"{stem_base}_recuperato.3mf"

        cartella_dest = Path.home() / "Documents"
        if not cartella_dest.exists():
            cartella_dest = Path.home()

        dest = cartella_dest / nome_file
        cnt = 1
        while dest.exists():
            if nome_file.endswith(".gcode.3mf"):
                dest = cartella_dest / f"{stem_base}_slice_{cnt}.gcode.3mf"
            elif nome_file.endswith(".gcode"):
                dest = cartella_dest / f"{stem_base}_slice_{cnt}.gcode"
            else:
                dest = cartella_dest / f"{stem_base}_recuperato_{cnt}.3mf"
            cnt += 1

        self.entry_destinazione.delete(0, "end")
        self.entry_destinazione.insert(0, str(dest))

        # Imposta fallback
        self.entry_fallback.delete(0, "end")
        if s.get("origine"):
            self.entry_fallback.insert(0, str(s["origine"]))

        self._aggiorna_pulsante_azione()

    def _imposta_cartella_dest(self, cartella):
        attuale = Path(self.entry_destinazione.get().strip()) if self.entry_destinazione.get().strip() else Path("progetto_recuperato.3mf")
        nuovo = cartella / attuale.name
        self.entry_destinazione.delete(0, "end")
        self.entry_destinazione.insert(0, str(nuovo))

    def _sfoglia_input(self):
        radici = engine.ottieni_cartelle_radice_temp()
        iniziale = str(radici[0] / "bamboo_model") if radici and (radici[0] / "bamboo_model").exists() else str(Path.home())
        cartella = filedialog.askdirectory(title="Seleziona la cartella con i dati del crash", initialdir=iniziale)
        if cartella:
            p = Path(cartella)
            s = engine.analizza_sessione(p, ricerca_profonda=True)
            self.sessioni_trovate.insert(0, s)
            self._imposta_sessione(0)
            self._scrivi_log(f"[MANUALE] Impostata cartella: {p} (stato: {s['stato']})")

    def _sfoglia_output(self):
        attuale = self.entry_destinazione.get().strip()
        p_att = Path(attuale) if attuale else None
        is_raw_gcode = (
            self.sessione_corrente
            and self.sessione_corrente.get("stato") == "solo_gcode"
            and not self.sessione_corrente.get("gcode_3mf")
        )
        scelto = filedialog.asksaveasfilename(
            title="Salva file ricostruito",
            initialdir=str(p_att.parent) if p_att and p_att.parent.exists() else str(Path.home() / "Documents"),
            initialfile=p_att.name if p_att else "",
            defaultextension=".gcode" if is_raw_gcode else ".3mf",
            filetypes=[("Progetto Bambu 3MF", "*.3mf"), ("File G-code", "*.gcode"), ("Tutti i file", "*.*")]
        )
        if scelto:
            self.entry_destinazione.delete(0, "end")
            self.entry_destinazione.insert(0, scelto)

    def _sfoglia_fallback(self):
        scelto = filedialog.askopenfilename(
            title="Seleziona il progetto 3MF originale pre-crash",
            filetypes=[("Progetto Bambu 3MF", "*.3mf"), ("Tutti i file", "*.*")]
        )
        if scelto:
            self.entry_fallback.delete(0, "end")
            self.entry_fallback.insert(0, scelto)

    def _apri_cache_temp(self):
        radici = engine.ottieni_cartelle_radice_temp()
        for r in radici:
            p = r / "bamboo_model"
            if p.exists():
                os.startfile(p)
                return
        messagebox.showinfo("Cartella non trovata", "Nessuna cartella temporanea bamboo_model trovata.")

    def _ispeziona_diagnostica(self):
        if not self.sessione_corrente:
            messagebox.showwarning("Attenzione", "Seleziona prima una sessione da ispezionare.")
            return

        radice = self.sessione_corrente["path"]
        self.txt_diagnostica.delete("1.0", "end")
        self.txt_diagnostica.insert("end", f"=== DIAGNOSTICA CARTELLA: {radice} ===\n\n")

        buf = io.StringIO()
        try:
            info = engine.analizza_sessione(radice, ricerca_profonda=True)
            with contextlib.redirect_stdout(buf):
                base, loose = engine.inventario(radice)
            self.txt_diagnostica.insert("end", buf.getvalue() + "\n")

            if loose:
                self.txt_diagnostica.insert("end", "Dettaglio modelli 3D trovati in 3D/Objects:\n")
                for i, p in enumerate(loose, 1):
                    tipo = "ZIP ANNIDATO (contiene XML reale)" if zipfile.is_zipfile(p) else "File XML Diretto"
                    self.txt_diagnostica.insert("end", f"  [{i:02d}] {p.name:<20} -> {tipo} ({p.stat().st_size:,} bytes)\n")
            else:
                self.txt_diagnostica.insert("end", "Nessun modello object_*.model in 3D/Objects.\n")

            if info["gcode_3mf"] or info["gcode_raw"]:
                self.txt_diagnostica.insert("end", "\nFile di stampa (Slice/G-code) trovati in Metadata/:\n")
                for p in info["gcode_3mf"]:
                    self.txt_diagnostica.insert("end", f"  • [3MF Slice] {p.name} ({p.stat().st_size:,} bytes)\n")
                for p in info["gcode_raw"]:
                    self.txt_diagnostica.insert("end", f"  • [G-code]    {p.name} ({p.stat().st_size:,} bytes)\n")

            if info["stato"] == "recuperabile":
                stato_msg = "\nStato di prontezza: OTTIMO — Progetto 3D recuperabile!"
            elif info["stato"] == "solo_gcode":
                stato_msg = (
                    "\nStato di prontezza: SOLO G-CODE — Bambu Studio ha già rimosso il .3mf di lavoro e i modelli 3D "
                    "(probabile chiusura regolare), ma puoi estrarre i file slice/G-code in Metadata."
                )
            else:
                stato_msg = "\nStato di prontezza: NON RECUPERABILE — Cartella già svuotata da Bambu Studio."

            self.txt_diagnostica.insert("end", stato_msg + "\n")
        except Exception as e:
            self.txt_diagnostica.insert("end", f"[ERRORE] Diagnostica fallita:\n{e}\n{traceback.format_exc()}")

    def _avvia_recupero(self):
        if not self.sessione_corrente:
            messagebox.showwarning("Dati mancanti", "Seleziona una sessione di crash da recuperare.")
            return

        stato = self.sessione_corrente.get("stato", "vuota")
        radice = self.sessione_corrente["path"]

        if stato == "vuota":
            messagebox.showinfo(
                "Cartella già svuotata",
                "In questa cartella non ci sono più modelli 3D né file di stampa da recuperare.\n\n"
                "Quando Bambu Studio si chiude normalmente (senza crash), cancella in automatico i file "
                "temporanei di progetto lasciando solo la cartella vuota.\n\n"
                "Se cercavi il progetto originale, controlla il campo 'Progetto di origine' nella scheda."
            )
            return

        uscita = self.entry_destinazione.get().strip()
        fallback_str = self.entry_fallback.get().strip()
        fallback = Path(fallback_str) if fallback_str else None
        salta_backup = not self.switch_backup.get()

        if not uscita:
            messagebox.showwarning("Dati mancanti", "Specifica un percorso dove salvare il file recuperato.")
            return

        self.btn_avvia.configure(state="disabled", text="⏳  ELABORAZIONE IN CORSO...")
        self.lbl_stato.configure(text="ELABORAZIONE IN CORSO...", text_color=ACCENT_GREEN)
        self.progress_bar.set(0.05)

        self._scrivi_log("\n" + "=" * 55)
        self._scrivi_log(f"[AVVIO] Sessione: {radice.name} (Modalità: {stato})")
        self._scrivi_log(f"        Destinazione: {uscita}")
        if fallback and stato == "recuperabile":
            self._scrivi_log(f"        Progetto fallback: {fallback.name}")
        self._scrivi_log("=" * 55)

        threading.Thread(
            target=self._recupero_thread,
            args=(radice, Path(uscita), fallback, salta_backup, stato),
            daemon=True
        ).start()

    def _recupero_thread(self, radice, uscita, fallback, salta_backup, stato):
        buf = io.StringIO()

        def cb_progresso(msg, pct):
            self.after(0, self._aggiorna_progresso_ui, msg, pct)

        try:
            with contextlib.redirect_stdout(buf):
                if stato == "solo_gcode":
                    file_principale, _ = engine.estrai_gcode_metadata(
                        radice,
                        uscita,
                        salta_backup=salta_backup,
                        callback_progresso=cb_progresso
                    )
                    out_res = str(file_principale.resolve())
                else:
                    engine.recupera(
                        radice,
                        uscita,
                        progetto_fallback=fallback,
                        salta_backup=salta_backup,
                        callback_progresso=cb_progresso
                    )
                    out_res = str(uscita.resolve())
            self.after(0, self._fine_recupero, True, buf.getvalue(), out_res, "")
        except Exception as exc:
            err = buf.getvalue() + "\n" + traceback.format_exc()
            self.after(0, self._fine_recupero, False, err, "", str(exc))

    def _aggiorna_progresso_ui(self, msg, pct):
        self.lbl_stato.configure(text=msg.upper())
        self.progress_bar.set(pct)
        self._scrivi_log(f"[PROGRESSO] {msg}")

    def _fine_recupero(self, successo, log_text, percorso_uscita, errore_leggibile=""):
        self._scrivi_log(log_text)
        self._aggiorna_pulsante_azione()

        if successo:
            self.ultimo_recuperato = percorso_uscita
            self.progress_bar.set(1.0)
            self.lbl_stato.configure(text="OPERAZIONE COMPLETATA CON SUCCESSO! ✓", text_color="#19D181")

            self.btn_apri_bambu.configure(state="normal")
            self.btn_mostra_cartella.configure(state="normal")

            messagebox.showinfo(
                "Operazione Riuscita!",
                f"Il file è stato recuperato e verificato con successo!\n\n"
                f"File generato:\n{percorso_uscita}\n\n"
                "Puoi aprirlo subito cliccando sui pulsanti dedicati nella schermata."
            )
        else:
            self.progress_bar.set(0)
            self.lbl_stato.configure(text="RECUPERO NON RIUSCITO (VEDI DETTAGLI)", text_color=ACCENT_RED)
            dettaglio = errore_leggibile.strip() if errore_leggibile else "Consulta il registro delle operazioni per i dettagli."
            messagebox.showerror(
                "Impossibile completare il recupero",
                f"{dettaglio}\n\n(I dettagli tecnici completi sono stati salvati nel Registro delle Operazioni)."
            )

    def _apri_file_con_bambu(self):
        if self.ultimo_recuperato and Path(self.ultimo_recuperato).is_file():
            try:
                os.startfile(self.ultimo_recuperato)
            except Exception as e:
                messagebox.showerror("Errore apertura", f"Impossibile aprire il file con il programma predefinito:\n{e}")

    def _apri_cartella_destinazione(self):
        if self.ultimo_recuperato and Path(self.ultimo_recuperato).is_file():
            subprocess.Popen(f'explorer /select,"{self.ultimo_recuperato}"')

    def _mostra_info_licenza(self):
        info = (
            "BAMBU RESCUE · v2.1 PRO (Edizione Italiana)\n\n"
            "Sviluppo e Crediti:\n"
            "• Autore originale motore: 小岛秀夫 (MakerWorld)\n"
            "• Supporto tecnico autore originale: 耀阳 (WeChat: d570565010)\n"
            "• UI Moderna, localizzazione e packaging standalone: 2026\n\n"
            "Licenza e Condizioni d'Uso:\n"
            "✓ Software 100% gratuito per l'uso personale e la riparazione dei file.\n"
            "✓ Condivisibile liberamente in versione originale o compilata.\n"
            "✗ È vietata la vendita o il commercio a scopo di lucro di questo software.\n"
            "✗ È vietato rimuovere l'attribuzione agli autori originali."
        )
        messagebox.showinfo("Informazioni & Licenza", info)


if __name__ == "__main__":
    app = BambuRescueApp()
    app.mainloop()
