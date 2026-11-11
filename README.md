# Bambu Rescue 🛟

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Usage Agreement](https://img.shields.io/badge/License-Free%20%2F%20Non--Commercial-orange.svg)](references/usage-agreement.md)
[![Bambu Studio](https://img.shields.io/badge/Bambu%20Studio-Compatible-00AE42.svg)](https://bambulab.com)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6.svg)](#)
[![Release](https://img.shields.io/github/v/release/Dedalo-Studio/bambu-rescue?color=00AE68)](https://github.com/Dedalo-Studio/bambu-rescue/releases/latest)

[🇮🇹 **Italiano**](#-italiano) | [🇬🇧 **English**](#-english)

---

> [!IMPORTANT]
> **Attribuzione e Versione Derivata / Attribution & Derivative Notice**
> Questo progetto è un adattamento con interfaccia grafica ridisegnata, localizzazione italiana e miglioramenti funzionali basato sul motore originale di recupero sviluppato da **小岛秀夫 (MakerWorld)** / **耀阳** (WeChat: `d570565010`). Non si tratta della release ufficiale dell'autore originale: i file originali intatti e l'accordo d'uso obbligatorio sono conservati nelle cartelle [`scripts/`](scripts) e [`references/`](references/usage-agreement.md).

---

## 🇮🇹 Italiano

**Bambu Rescue** è un'applicazione desktop moderna, rapida e portatile progettata per **recuperare e ricostruire automaticamente i progetti `.3mf` di Bambu Studio** andati persi in seguito a crash, blocchi di sistema o chiusure impreviste su Windows.

### 💡 Perché Bambu Studio "perde" il lavoro dopo un crash?
Durante la modifica di un piatto, Bambu Studio salva salvataggi parziali nella cache temporanea di Windows (`%LOCALAPPDATA%\Temp\bamboo_model`). Tentarne il ripristino manuale fallisce quasi sempre per tre motivi:
1. **Il tranello dei falsi `.model` (ZIP annidati)**: i singoli oggetti (`3D/Objects/object_N.model`) spesso iniziano con byte `PK` — sono veri archivi ZIP con estensione rinominata in `.model`. Se ricompressi tali e quali in un `.3mf`, Bambu Studio mostra un piatto vuoto.
2. **Snapshot incrementali**: se modificavi un `.3mf` già salvato, nella cache potrebbero trovarsi solo gli oggetti toccati di recente, mentre gli altri restano nel file originale indicato in `origin.txt`.
3. **Relazioni orfane & ZIP64**: `_rels/.rels` può puntare a miniature non salvate mandando in errore il parser, e progetti pesanti richiedono scrittura streaming **ZIP64**.

### 🛠️ Funzionalità Principali
- 🔍 **Rilevamento Automatico Intelligente**: scansiona `%LOCALAPPDATA%\Temp\bamboo_model` e distingue:
  - 🟢 **Crash 3D recuperabili** (mostrati di default, con conteggio oggetti e progetto di origine);
  - 🟡 **Sessioni chiuse con solo G-code/slice in `Metadata/`** (attivabili con switch dedicato per estrarre `.gcode.3mf` / `.gcode` affettati prima della chiusura);
  - Filtra automaticamente le cartelle già svuotate da Bambu Studio alla chiusura regolare.
- 📦 **Decompressione Automatica ZIP Annidati**: estrae l'XML reale dai falsi `object_*.model` mantenendo UUID, trasformazioni e configurazioni di stampa.
- 🧩 **Integrazione Fallback da `origin.txt`**: rileva il file `.3mf` originale (anche se spostato tra *Documenti*, *Desktop* o *Download*) per integrare gli oggetti non modificati.
- 🛡️ **Backup Preventivo + Verifica Integrità**: crea una copia ZIP di sicurezza verificata via CRC prima di operare e valida ogni pacchetto generato (CRC + XML `3D/3dmodel.model`).
- 🖥️ **Interfaccia Dark Stile Bambu Studio**: scheda recupero guidata, barra di avanzamento in tempo reale, registro operazioni, tab diagnostica approfondita e apertura diretta con Bambu Studio.

---

### 📦 Download Diretto

Non è necessario installare Python: puoi scegliere la modalità che preferisci per Windows:

#### 🪟 Windows
* 🎒 [**Versione Portatile (`BambuRescue.exe`)**](https://github.com/Dedalo-Studio/bambu-rescue/releases/latest/download/BambuRescue.exe) — *Singolo eseguibile portatile, avvio immediato senza installazione.*
* 💿 [**Versione Installabile (`BambuRescue-Setup-v2.1.0.exe`)**](https://github.com/Dedalo-Studio/bambu-rescue/releases/latest/download/BambuRescue-Setup-v2.1.0.exe) — *Installer classico Windows con collegamento nel Menu Start, icona Desktop opzionale e disinstallatore.*
* 📦 [**Tutto il Progetto (`BambuRescue-v2.1.0-full.zip`)**](https://github.com/Dedalo-Studio/bambu-rescue/releases/latest/download/BambuRescue-v2.1.0-full.zip) — *Archivio `.zip` completo con eseguibile portatile, sorgenti Python, script di avvio, guida, script originali e script installer.*

---

### 🚀 Come Usare l'Applicazione

#### Metodo Grafico (GUI)
1. Avvia **`BambuRescue.exe`** (oppure **`Avvia_Recupero_Bambu.bat`** dal codice sorgente).
2. Nella card **①**, controlla la sessione di crash rilevata automaticamente (oppure attiva l'interruttore *Mostra anche sessioni chiuse con solo G-code/slice* o usa *Sfoglia manualmente...*).
3. Nella card **②**, verifica o modifica il percorso di salvataggio proposto.
4. Nella card **③**, lascia attivo il backup di sicurezza e controlla l'eventuale file originale di fallback rilevato da `origin.txt`.
5. Clicca su **`🚀 AVVIA RECUPERO E RICOSTRUZIONE 3MF`** e apri il file ricostruito direttamente con Bambu Studio!

#### Metodo da Riga di Comando (CLI)
```powershell
# Elenca i crash 3D recuperabili trovati in cache
python recupero_bambu_3mf.py --scopri

# Elenca tutte le sessioni (incluse chiuse con solo G-code e vuote)
python recupero_bambu_3mf.py --scopri --tutte

# Ispeziona una cartella di crash senza modificarla
python recupero_bambu_3mf.py -i "C:\Users\<Nome>\AppData\Local\Temp\bamboo_model\..." --ispeziona

# Ricostruisci il file .3mf (con fallback opzionale al progetto originale)
python recupero_bambu_3mf.py -i "C:\...\sessione" -o "C:\...\progetto_recuperato.3mf" -f "C:\...\originale.3mf"

# Estrai eventuali slice .gcode.3mf / .gcode rimasti in Metadata/
python recupero_bambu_3mf.py -i "C:\...\sessione" -o "C:\...\piatto_slice.gcode.3mf" --estrai-gcode
```

---

### 💻 Avvio da Sorgente Python (Opzionale)

1. Clona il repository:
   ```bash
   git clone https://github.com/Dedalo-Studio/bambu-rescue.git
   cd bambu-rescue
   ```
2. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```
3. Avvia l'interfaccia grafica:
   ```bash
   python recupero_bambu_3mf_gui.py
   ```

---

## 🇬🇧 English

**Bambu Rescue** is a fast, portable desktop tool designed to **recover and rebuild Bambu Studio `.3mf` project files** from Windows crash/autosave cache directories (`%LOCALAPPDATA%\Temp\bamboo_model`).

### 💡 Why Manual Cache Recovery Usually Fails
1. **Nested ZIP "fake `.model`" files**: Bambu Studio often writes `3D/Objects/object_*.model` as single-entry ZIP archives with `.model` extensions. Repackaging them raw causes Bambu Studio to open an empty plate.
2. **Incremental snapshots**: edited projects may only store recently touched objects in cache, requiring missing parts to be merged back from the original `.3mf` referenced in `origin.txt`.
3. **Orphaned OPC relationships & ZIP64**: broken `_rels/.rels` thumbnail links and huge XML models require relationship pruning and streaming **ZIP64** output.

### 🛠️ Key Features & Modifications Over Upstream
Built on top of the recovery engine by **小岛秀夫 / 耀阳** (preserved untouched in [`scripts/`](scripts/)), this derivative release adds:
- 🇮🇹 Full Italian localization & modern dark **CustomTkinter** GUI ([`recupero_bambu_3mf_gui.py`](recupero_bambu_3mf_gui.py)) with guided workflow, live log, and diagnostics tab;
- 🧠 Session state classification (`recuperabile` 3D crashes vs `solo_gcode` normally-closed sessions with sliced `.gcode.3mf`/`.gcode` leftovers in `Metadata/` vs cleaned empty dirs);
- ⚡ Fast directory pruning & deferred `origin.txt` deep lookup (`recupero_bambu_3mf.py`);
- 📦 Portable standalone Windows `.exe` (`BambuRescue.exe`).

### 📦 Direct Downloads
* 🎒 [**Portable Version (`BambuRescue.exe`)**](https://github.com/Dedalo-Studio/bambu-rescue/releases/latest/download/BambuRescue.exe) — *Single portable executable, zero installation.*
* 💿 [**Windows Installer (`BambuRescue-Setup-v2.1.0.exe`)**](https://github.com/Dedalo-Studio/bambu-rescue/releases/latest/download/BambuRescue-Setup-v2.1.0.exe) — *Standard Windows Setup wizard with Start Menu shortcut, optional Desktop icon, and uninstaller.*
* 📦 [**Full Project Archive (`BambuRescue-v2.1.0-full.zip`)**](https://github.com/Dedalo-Studio/bambu-rescue/releases/latest/download/BambuRescue-v2.1.0-full.zip) — *Complete `.zip` containing the portable `.exe`, Python source code, launcher scripts, documentation, upstream scripts, and Inno Setup script.*

### 🛠️ Building Standalone `.exe` & Installer
```powershell
pip install -r requirements.txt pyinstaller
python -m PyInstaller --onefile --noconsole --name "BambuRescue" --icon "app_icon.ico" --add-data "app_icon.ico;." --collect-all customtkinter --clean recupero_bambu_3mf_gui.py
```
To build the Windows installer (`BambuRescue-Setup-v2.1.0.exe`), compile the `--onedir` bundle into `build_inst\dist\BambuRescue` and run Inno Setup 6 (`ISCC.exe installer.iss`).

---

## ⚖️ Credits & Usage Agreement

- **Original Engine & Skill Author**: **小岛秀夫** (MakerWorld)
- **Original Author Paid Manual Support**: **耀阳** (WeChat: `d570565010`)
- **Italian GUI Redesign, v2.1 Engine Enhancements & Packaging**: [Dedalo-Studio](https://github.com/Dedalo-Studio) (2026)

Please read [`references/usage-agreement.md`](references/usage-agreement.md) before redistributing or modifying:
- Free for personal use and free redistribution with original author attribution and agreement intact.
- **Strictly prohibited** to sell copies, download links, paid packs, or charge users for access to this tool or its derived `.exe`.
