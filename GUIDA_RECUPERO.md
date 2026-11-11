# Guida Completa · Bambu Rescue v2.1 PRO

**Bambu Rescue** è un'applicazione moderna, rapida e intuitiva per **recuperare e ricostruire completamente i progetti di Bambu Studio (.3mf)** andati persi a seguito di un crash, blocco del PC o chiusura improvvisa di Windows, oltre a estrarre eventuali file `.gcode.3mf` / `.gcode` già affettati rimasti nella cartella `Metadata/`.

---

## 🌟 Interfaccia Grafica Moderna (v2.1 PRO)

L'applicazione utilizza un tema dark moderno ispirato a Bambu Studio:

1. **Tab 🚀 Recupero Guidato (Schermata Principale)**:
   - **Card ① Seleziona la Sessione del Crash**: scansiona automaticamente la cache temporanea di Windows (`%LOCALAPPDATA%\Temp\bamboo_model`) classificando ogni cartella in:
     - 🟢 **Crash 3D recuperabili** (mostrati di default): contengono il file `.3mf` base e/o i modelli `object_*.model` reali.
     - 🟡 **Sessioni chiuse con solo G-code/slice in Metadata**: attivabile tramite l'apposito interruttore se Bambu Studio è stato chiuso regolarmente (eliminando i modelli 3D dalla cache) ma hai comunque bisogno del G-code già affettato prima della chiusura.
     - Le cartelle vuote già ripulite da Bambu Studio vengono filtrate automaticamente.
   - **Card ② Dove salvare il File Ricostruito**: propone automaticamente un nome chiaro nei tuoi *Documenti* (es. `NomeProgetto_recuperato.3mf` oppure `_slice.gcode.3mf`), con pulsanti rapidi per *Documenti* e *Desktop*.
   - **Card ③ Sicurezza & Integrazione Avanzata**: crea una copia di backup ZIP verificata via CRC prima di qualsiasi operazione e integra automaticamente o manualmente il file `.3mf` originale pre-crash come fallback per eventuali oggetti non modificati.
   - **Pannello Azione & Barra di Avanzamento Dinamica**: il pulsante si adatta allo stato della sessione (`🚀 AVVIA RECUPERO E RICOSTRUZIONE 3MF` in verde per crash 3D, oppure `🖨️ ESTRAI FILE G-CODE / SLICE DA METADATA` in ambra), con barra di caricamento in tempo reale e **Registro delle Operazioni** integrato.
   - **Pannello Risultato con Azioni Immediate**:
     - `Apri con Bambu Studio` (apre direttamente il file recuperato);
     - `Mostra nella Cartella` (apre Esplora File selezionando il file).

2. **Tab 🔍 Diagnostica & Cache**:
   - Analizza la cartella della sessione selezionata, mostra quali `object_*.model` sono in realtà archivi ZIP annidati, elenca eventuali pacchetti slice/G-code in `Metadata/` ed esplicita lo stato di recuperabilità.
   - Include il pulsante diretto per aprire la cartella cache temporanea di Windows (`bamboo_model`).

3. **Tab 📖 Come Funziona**:
   - Spiega il meccanismo di salvataggio temporaneo di Bambu Studio, il formato dei falsi `.model` (ZIP annidati), la ricostruzione ZIP64 con pulizia delle relazioni `_rels/.rels` e la differenza tra crash reale (🟢) e chiusura regolare con pulizia cache (🟡).

---

## 🚀 Come Avviare l'Applicazione

### Opzione A: Eseguibile Standalone (Consigliata)
- Fai doppio clic su **`BambuRescue.exe`**.
- È un **singolo file eseguibile portatile**: funziona su qualsiasi PC Windows 10/11 senza bisogno di installare Python.

### Opzione B: Script Batch / Sorgente Python
- Fai doppio clic su **`Avvia_Recupero_Bambu.bat`** oppure esegui `python recupero_bambu_3mf_gui.py`.

---

## 🛠️ Utilizzo da Riga di Comando (CLI)

```powershell
# 1. Scansiona e visualizza le sessioni recuperabili come progetto 3D:
python recupero_bambu_3mf.py --scopri

# 1b. Visualizza tutte le sessioni (incluse sessioni chiuse con solo G-code o vuote):
python recupero_bambu_3mf.py --scopri --tutte

# 2. Ispeziona una cartella specifica senza modificarla:
python recupero_bambu_3mf.py --input "C:\Users\<TuoNome>\AppData\Local\Temp\bamboo_model\..." --ispeziona

# 3. Esegui il recupero 3MF da terminale:
python recupero_bambu_3mf.py --input "C:\Users\<TuoNome>\AppData\Local\Temp\bamboo_model\..." --output "C:\Users\<TuoNome>\Documents\Recuperato.3mf"

# 4. Estrai eventuali file .gcode.3mf / .gcode rimasti in Metadata/:
python recupero_bambu_3mf.py --input "C:\Users\<TuoNome>\AppData\Local\Temp\bamboo_model\..." --output "C:\Users\<TuoNome>\Documents\Slice.gcode.3mf" --estrai-gcode
```

---

## ⚖️ Crediti & Condizioni d'Uso Gratuite

- **Autore originale motore & logica di recupero**: 小岛秀夫 (MakerWorld)
- **Supporto tecnico autore originale**: 耀阳 (WeChat: `d570565010`)
- **Versione derivata italiana v2.1 PRO (UI CustomTkinter, classificazione crash/G-code, ottimizzazione scansione e packaging standalone)**: Dedalo-Studio (2026)
- Consultare [`references/usage-agreement.md`](references/usage-agreement.md) per i termini completi dell'autore originale: il software è **100% gratuito** per uso personale; è vietata qualsiasi vendita o distribuzione a pagamento e va sempre mantenuta l'attribuzione all'autore originale.
