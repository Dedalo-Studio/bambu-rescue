# -*- coding: utf-8 -*-
"""
Modulo: recupero_bambu_3mf.py
Descrizione: Motore di recupero e ricostruzione dei progetti Bambu Studio 3MF
             a seguito di crash o chiusure impreviste su Windows.

Autore originale: 小岛秀夫 (MakerWorld)
Supporto tecnico autore originale: 耀阳 (WeChat: d570565010)
Adattamento, ottimizzazione e localizzazione italiana: 2026

Accordo di licenza d'uso: consultare 'references/usage-agreement.md'.
"""

import argparse
import os
import re
import shutil
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

# Configura encoding stdout per evitare UnicodeEncodeError su console Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# Espressione regolare per identificare i file dei modelli di oggetti (es. object_1.model)
OBJECT_RE = re.compile(r"object_(\d+)\.model", re.I)

# Namespace standard OpenXML e 3MF
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
PROD_PATH = "{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}path"


def ottieni_cartelle_radice_temp():
    """Restituisce l'elenco delle cartelle temporanee di sistema dove cercare i file di crash."""
    radici = []
    for var in ("LOCALAPPDATA", "TEMP", "TMP"):
        valore = os.environ.get(var)
        if valore:
            p = Path(valore)
            if var == "LOCALAPPDATA":
                radici.append(p / "Temp")
            else:
                radici.append(p)
    
    # Rimuovi duplicati mantenendo l'ordine
    univoche = []
    viste = set()
    for r in radici:
        if r.exists():
            r_res = r.resolve()
            if r_res not in viste:
                viste.add(r_res)
                univoche.append(r_res)
    return univoche


def trova_gcode_metadata(cartella_radice):
    """
    Cerca eventuali file di stampa già affettati (.gcode.3mf e .gcode) rimasti
    nella sottocartella Metadata/ (tipico delle sessioni chiuse regolarmente).
    """
    meta = Path(cartella_radice) / "Metadata"
    risultato = {"gcode_3mf": [], "gcode": []}
    if not meta.is_dir():
        return risultato

    try:
        for p in meta.iterdir():
            if not p.is_file():
                continue
            nome_low = p.name.lower()
            if nome_low.endswith(".3mf") and not nome_low.endswith("_config.3mf"):
                try:
                    with zipfile.ZipFile(p) as z:
                        if any(n.lower().endswith(".gcode") for n in z.namelist()):
                            risultato["gcode_3mf"].append(p)
                except (OSError, zipfile.BadZipFile):
                    pass
            elif nome_low.endswith(".gcode") and p.stat().st_size > 0:
                risultato["gcode"].append(p)
    except OSError:
        pass

    risultato["gcode_3mf"].sort(key=lambda x: x.stat().st_mtime, reverse=True)
    risultato["gcode"].sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return risultato


def analizza_sessione(cartella, ricerca_profonda=True):
    """
    Analizza una singola cartella di sessione Bambu Studio e restituisce
    un dizionario completo con lo stato di recuperabilità e i metadati.
    Stati possibili:
      - 'recuperabile': contiene .3mf base, [Content_Types].xml o modelli 3D (object_*.model)
      - 'solo_gcode':   modelli 3D già rimossi da Bambu Studio, ma presenti slice/G-code in Metadata
      - 'vuota':        cartella residua senza file 3D né G-code recuperabili
    """
    cartella = Path(cartella)
    base = trova_3mf_base(cartella)
    ha_content = (cartella / "[Content_Types].xml").is_file()
    ha_base = (base is not None) or ha_content

    oggetti = []
    for sub in (cartella / "3D", cartella / "3D" / "Objects"):
        if sub.exists():
            oggetti.extend(p for p in sub.glob("object_*.model") if p.is_file())
    oggetti = list(dict.fromkeys(oggetti))
    conteggio_oggetti = len(oggetti)

    gcode_info = trova_gcode_metadata(cartella)
    gcode_3mf = gcode_info["gcode_3mf"]
    gcode_raw = gcode_info["gcode"]

    if ha_base or conteggio_oggetti > 0:
        stato = "recuperabile"
    elif gcode_3mf or gcode_raw:
        stato = "solo_gcode"
    else:
        stato = "vuota"

    mtime_max = 0
    try:
        for root_dir, _, files in os.walk(cartella):
            for fname in files:
                try:
                    t = os.path.getmtime(os.path.join(root_dir, fname))
                    if t > mtime_max:
                        mtime_max = t
                except OSError:
                    pass
    except (OSError, PermissionError):
        pass

    if mtime_max == 0:
        try:
            mtime_max = cartella.stat().st_mtime
        except OSError:
            mtime_max = 0

    dt = datetime.fromtimestamp(mtime_max) if mtime_max > 0 else datetime.now()
    data_str = dt.strftime("%d/%m/%Y %H:%M:%S")
    origine = trova_progetto_originale(cartella, ricerca_profonda=ricerca_profonda)
    origine_nome = origine.name if origine else leggi_nome_origine(cartella)

    return {
        "path": cartella,
        "mtime": mtime_max,
        "data_leggibile": data_str,
        "oggetti": conteggio_oggetti,
        "ha_base": ha_base,
        "base_file": base,
        "gcode_3mf": gcode_3mf,
        "gcode_raw": gcode_raw,
        "stato": stato,
        "origine": origine,
        "origine_nome": origine_nome,
        "descrizione": f"{data_str} · {conteggio_oggetti} oggetti · {cartella.name}",
    }


def scopri_sessioni_crash(includi_solo_gcode=False, includi_vuote=False):
    """
    Scansiona il computer alla ricerca di cartelle di sessione recenti di Bambu Studio.
    Di default restituisce solo le sessioni effettivamente recuperabili come progetto 3D.
    """
    radici = ottieni_cartelle_radice_temp()
    nomi_cartelle = ("bamboo_model", "BambuStudio", "Bambu Studio")
    cartelle_trovate = set()
    sessioni = []

    cartelle_interne = {
        "3d", "objects", "metadata", "_rels", ".rels",
        "auxiliaries", ".thumbnails", "model pictures", "profile pictures"
    }

    for radice in radici:
        for nome in nomi_cartelle:
            base = radice / nome
            if not base.exists():
                continue

            try:
                for root_dir, dirs, files in os.walk(base):
                    cartella = Path(root_dir)
                    # Filtra subito le sottodirectory interne di progetto
                    dirs[:] = [d for d in dirs if d.lower() not in cartelle_interne]

                    if cartella in cartelle_trovate:
                        continue

                    ha_3d = (cartella / "3D").is_dir()
                    ha_meta = (cartella / "Metadata").is_dir()
                    ha_3mf = (".3mf" in files) or any(f.lower().endswith(".3mf") for f in files)
                    ha_content = "[Content_Types].xml" in files

                    if ha_3d or ha_meta or ha_3mf or ha_content:
                        cartelle_trovate.add(cartella)
                        dirs[:] = []  # Non scendere ulteriormente dentro questa sessione
                        info = analizza_sessione(cartella, ricerca_profonda=False)
                        if info["stato"] == "recuperabile":
                            sessioni.append(info)
                        elif info["stato"] == "solo_gcode" and includi_solo_gcode:
                            sessioni.append(info)
                        elif info["stato"] == "vuota" and includi_vuote:
                            sessioni.append(info)
            except (OSError, PermissionError):
                continue

    # Ordina per data (dal più recente al più vecchio)
    sessioni.sort(key=lambda s: s["mtime"], reverse=True)
    return sessioni


def scopri(includi_tutte=False):
    """Funzione CLI per visualizzare l'inventario dei crash trovati."""
    sessioni = scopri_sessioni_crash(includi_solo_gcode=includi_tutte, includi_vuote=includi_tutte)
    if not sessioni:
        print("[INFO] Nessuna sessione recuperabile di Bambu Studio trovata nella cartella temporanea.")
        return

    print("=" * 80)
    print("SESSIONI RILEVATE IN BAMBU STUDIO:")
    print("=" * 80)
    for s in sessioni:
        orig_label = s["origine"].name if s["origine"] else s.get("origine_nome")
        orig = f" | Origine: {orig_label}" if orig_label else ""
        stato_tag = {
            "recuperabile": "RECUPERABILE 3D",
            "solo_gcode": f"SOLO G-CODE ({len(s['gcode_3mf']) + len(s['gcode_raw'])} slice)",
            "vuota": "VUOTA (già ripulita)"
        }.get(s["stato"], s["stato"])
        print(f"[{stato_tag}] Data: {s['data_leggibile']} | Oggetti: {s['oggetti']:2d}{orig}")
        print(f"  Percorso: {s['path']}")
        print("-" * 80)


def percorso_sicuro(nome):
    """Verifica che un percorso all'interno dell'archivio ZIP non contenga tentativi di Path Traversal."""
    p = PurePosixPath(nome.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"Percorso archivio non sicuro rilevato: {nome}")
    return str(p)


def trova_3mf_base(cartella_radice):
    """
    Cerca un file .3mf valido all'interno della cartella di crash da usare come modello base.
    Un 3MF valido deve contenere il file [Content_Types].xml.
    """
    file_candidati = [p for p in cartella_radice.iterdir() if p.is_file() and p.suffix.lower() == ".3mf"]
    file_candidati += [p for p in cartella_radice.iterdir() if p.is_file() and p.name == ".3mf"]
    
    validi = []
    for p in dict.fromkeys(file_candidati):
        try:
            with zipfile.ZipFile(p) as z:
                if "[Content_Types].xml" in z.namelist():
                    validi.append(p)
        except (OSError, zipfile.BadZipFile):
            pass

    return max(validi, key=lambda p: p.stat().st_mtime) if validi else None


def _leggi_valori_origine(cartella_crash):
    file_origine = Path(cartella_crash) / "origin.txt"
    if not file_origine.exists():
        return []
    try:
        dati_grezzi = file_origine.read_bytes()
    except OSError:
        return []
    valori = []
    for codifica in ("utf-8-sig", "utf-8", "gb18030", "mbcs", "latin-1"):
        try:
            testo = dati_grezzi.decode(codifica).strip().strip('"')
            if testo and testo not in valori:
                valori.append(testo)
        except (UnicodeError, LookupError):
            pass
    return valori


def leggi_nome_origine(cartella_crash):
    """Restituisce il solo nome file del progetto indicato in origin.txt, anche se spostato."""
    for val in _leggi_valori_origine(cartella_crash):
        nome = Path(val).name
        if nome.lower().endswith(".3mf"):
            return nome
    return None


def trova_progetto_originale(cartella_crash, ricerca_profonda=True):
    """
    Legge il file origin.txt (se presente) per determinare il percorso del progetto
    originale salvato prima del crash, cercando anche nelle cartelle comuni dell'utente.
    """
    valori = _leggi_valori_origine(cartella_crash)
    if not valori:
        return None

    for val in valori:
        p = Path(val)
        if p.is_file() and p.suffix.lower() == ".3mf":
            return p

    if not ricerca_profonda:
        return None

    nomi_file = {Path(v).name for v in valori if Path(v).name.lower().endswith(".3mf")}
    if not nomi_file:
        return None

    cartelle_ricerca = [
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Downloads",
        Path.home() / "OneDrive" / "Desktop",
        Path.home() / "OneDrive" / "Documents",
    ]
    cartelle_skip = {"node_modules", ".git", ".venv", "venv", "build", "dist", "__pycache__"}
    trovati = []
    for cartella in cartelle_ricerca:
        if not cartella.exists():
            continue
        try:
            for root_dir, dirs, files in os.walk(cartella):
                dirs[:] = [d for d in dirs if d not in cartelle_skip and not d.startswith(".")]
                for nome in nomi_file:
                    if nome in files:
                        trovati.append(Path(root_dir) / nome)
        except (OSError, PermissionError):
            pass

    return max(trovati, key=lambda p: p.stat().st_mtime) if trovati else None


def inventario(cartella_radice):
    """
    Esegue un'ispezione della cartella di crash, rilevando il file 3MF base,
    i file dei singoli modelli (.model) e identificando quanti di essi
    sono in realtà archivi ZIP annidati mascherati da file .model.
    """
    cartella_radice = Path(cartella_radice).resolve()
    base = trova_3mf_base(cartella_radice)
    oggetti = []
    for cartella in (cartella_radice / "3D", cartella_radice / "3D" / "Objects"):
        if cartella.exists():
            oggetti.extend(p for p in cartella.glob("object_*.model") if p.is_file())

    # Ordina gli oggetti in base all'ID numerico (object_1, object_2, ...)
    oggetti = sorted(
        dict.fromkeys(oggetti),
        key=lambda p: int(OBJECT_RE.fullmatch(p.name).group(1)) if OBJECT_RE.fullmatch(p.name) else 999999
    )

    annidati = 0
    for p in oggetti:
        if zipfile.is_zipfile(p):
            annidati += 1

    print(f"[ISPEZIONE] Cartella analizzata: {cartella_radice}")
    print(f"[ISPEZIONE] File 3MF base: {base.name if base else 'Non trovato (verranno usati i file sfusi)'}")
    print(f"[ISPEZIONE] File modello sfusi: {len(oggetti)}")
    print(f"[ISPEZIONE] Modelli memorizzati come ZIP annidati: {annidati}")
    
    origine = trova_progetto_originale(cartella_radice)
    if origine:
        print(f"[ISPEZIONE] File progetto originale individuato: {origine}")

    gcode_info = trova_gcode_metadata(cartella_radice)
    if gcode_info["gcode_3mf"] or gcode_info["gcode"]:
        print(
            f"[ISPEZIONE] Slice/G-code in Metadata: "
            f"{len(gcode_info['gcode_3mf'])} pacchetti .gcode.3mf, "
            f"{len(gcode_info['gcode'])} file .gcode"
        )

    return base, oggetti


def backup_sorgente(cartella_radice, cartella_destinazione):
    """
    Crea un archivio ZIP di sicurezza contenente l'intera cartella di crash
    con verifica CRC per garantire che nessuna prova o dato venga perso.
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    nome_backup = f"{cartella_radice.name}_backup_sorgente_{timestamp}.zip"
    file_backup = cartella_destinazione / nome_backup

    print(f"[BACKUP] Creazione copia di sicurezza in: {file_backup}...")
    with zipfile.ZipFile(file_backup, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for p in sorted(cartella_radice.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(cartella_radice).as_posix())

    with zipfile.ZipFile(file_backup) as z:
        if z.testzip() is not None:
            file_backup.unlink(missing_ok=True)
            raise ValueError("Il backup dei dati originali non ha superato la verifica CRC!")

    print(f"[BACKUP] Copia di sicurezza creata e verificata con successo: {file_backup.name}")
    return file_backup


def pulisci_relazioni(dati_xml, elementi_disponibili):
    """
    Rimuove dal file _rels/.rels i riferimenti a elementi opzionali mancanti
    (come miniature o allegati inesistenti) per evitare che Bambu Studio rifiuti il file.
    Non rimuove mai la relazione principale del modello 3D.
    """
    radice = ET.fromstring(dati_xml)
    for rel in list(radice):
        target = rel.attrib.get("Target", "").replace("\\", "/").lstrip("/")
        tipo_rel = rel.attrib.get("Type", "")
        if target not in elementi_disponibili and not tipo_rel.endswith("/3dmodel"):
            radice.remove(rel)

    ET.register_namespace("", REL_NS)
    return ET.tostring(radice, encoding="utf-8", xml_declaration=True)


def recupera(cartella_radice, file_uscita, progetto_fallback=None, salta_backup=False, callback_progresso=None):
    """
    Esegue il recupero completo del progetto Bambu Studio 3MF.
    
    Parametri:
    - cartella_radice: Cartella contenente i residui del crash.
    - file_uscita: Percorso del file .3mf da generare.
    - progetto_fallback: Percorso di un file .3mf originale usato solo per integrare elementi mancanti.
    - salta_backup: Se True, salta la creazione del file ZIP di backup.
    - callback_progresso: Funzione opzionale callback(messaggio, percentuale_float)
    """
    cartella_radice = Path(cartella_radice).resolve()
    if callback_progresso:
        callback_progresso("Analisi della cartella di crash...", 0.05)
    base, oggetti_sfusi = inventario(cartella_radice)

    if not base and not (cartella_radice / "[Content_Types].xml").exists():
        # Se ci sono modelli sfusi E un file di fallback valido, usa il fallback come struttura base
        if oggetti_sfusi and progetto_fallback and Path(progetto_fallback).is_file():
            fb_path = Path(progetto_fallback).resolve()
            try:
                with zipfile.ZipFile(fb_path) as z_fb:
                    if "[Content_Types].xml" in z_fb.namelist() and z_fb.testzip() is None:
                        print(
                            f"[AVVISO] File .3mf base assente nella cache di crash: "
                            f"utilizzo la struttura di '{fb_path.name}' come base per i "
                            f"{len(oggetti_sfusi)} modelli 3D trovati."
                        )
                        base = fb_path
            except (OSError, zipfile.BadZipFile):
                pass

    if not base and not (cartella_radice / "[Content_Types].xml").exists():
        gcode_info = trova_gcode_metadata(cartella_radice)
        ha_gcode = bool(gcode_info["gcode_3mf"] or gcode_info["gcode"])
        if not oggetti_sfusi:
            msg = (
                "Sessione non recuperabile come progetto 3D: Bambu Studio ha già rimosso "
                "il file .3mf di lavoro e tutti i modelli 3D (cartella 3D/Objects vuota), "
                "come avviene dopo una chiusura regolare."
            )
            if ha_gcode:
                msg += (
                    " Sono però presenti file di stampa già affettati (.gcode.3mf / .gcode) "
                    "nella sottocartella Metadata/ che puoi comunque estrarre."
                )
            raise ValueError(msg)
        else:
            raise ValueError(
                f"Trovati {len(oggetti_sfusi)} modelli 3D nella cache, ma manca il file .3mf base. "
                "Seleziona il file .3mf originale pre-crash nel campo ③ (Fallback) per ricostruire il pacchetto."
            )

    file_uscita = Path(file_uscita).resolve()
    file_uscita.parent.mkdir(parents=True, exist_ok=True)

    if not salta_backup:
        if callback_progresso:
            callback_progresso("Creazione copia di backup dei dati originali...", 0.15)
        backup_sorgente(cartella_radice, file_uscita.parent)

    file_parziale = file_uscita.with_suffix(file_uscita.suffix + ".parziale")
    if file_parziale.exists():
        file_parziale.unlink()

    voci_archivio = {}


    # 1. Carica i file dal 3MF base (se presente) oppure dai file scompattati nella cartella
    if base:
        print(f"[RECUPERO] Caricamento struttura dal 3MF base: {base.name}")
        with zipfile.ZipFile(base) as z:
            for info in z.infolist():
                if not info.is_dir():
                    voci_archivio[percorso_sicuro(info.filename)] = ("zip", base, info.filename)
    else:
        print("[RECUPERO] Caricamento file sfusi dalla cartella di crash...")
        for p in cartella_radice.rglob("*"):
            if p.is_file() and p != file_uscita:
                voci_archivio[p.relative_to(cartella_radice).as_posix()] = ("file", p, None)

    # 2. Se è stato specificato un progetto di fallback, aggiungi i componenti mancanti
    if progetto_fallback:
        progetto_fallback = Path(progetto_fallback).resolve()
        print(f"[RECUPERO] Integrazione elementi mancanti dal progetto di fallback: {progetto_fallback.name}")
        with zipfile.ZipFile(progetto_fallback) as z:
            if z.testzip() is not None:
                raise ValueError("Il file di fallback non ha superato la verifica CRC!")
            for info in z.infolist():
                if not info.is_dir():
                    nome_voce = percorso_sicuro(info.filename)
                    voci_archivio.setdefault(nome_voce, ("zip", progetto_fallback, info.filename))

    # 3. Integra o sovrascrivi con gli oggetti 3D più recenti estratti dal crash
    print(f"[RECUPERO] Elaborazione di {len(oggetti_sfusi)} modelli 3D recenti...")
    if callback_progresso:
        callback_progresso(f"Elaborazione di {len(oggetti_sfusi)} modelli 3D recenti...", 0.45)
    for p in oggetti_sfusi:
        destinazione = f"3D/Objects/{p.name}"
        e_zip = zipfile.is_zipfile(p)
        voci_archivio[destinazione] = ("annidato" if e_zip else "file", p, destinazione if e_zip else None)
        # Rimuovi eventuale riferimento duplicato alla vecchia cartella 3D/
        voci_archivio.pop(f"3D/{p.name}", None)

    elementi_disponibili = set(voci_archivio)

    # 4. Scrivi il nuovo archivio 3MF (ZIP64 con compressione DEFLATED)
    print(f"[RECUPERO] Scrittura del pacchetto 3MF finale: {file_uscita.name}...")
    if callback_progresso:
        callback_progresso(f"Scrittura archivio 3MF ZIP64 ({len(voci_archivio)} file)...", 0.70)
    try:
        with zipfile.ZipFile(file_parziale, "w", allowZip64=True) as out:
            for nome, sorgente in sorted(voci_archivio.items()):
                tipo, percorso, nome_interno = sorgente
                
                # Pulisci le relazioni per evitare crash su miniature mancanti
                if nome == "_rels/.rels":
                    if tipo == "zip":
                        with zipfile.ZipFile(percorso) as z:
                            dati = z.read(nome_interno)
                    else:
                        dati = percorso.read_bytes()
                    out.writestr(nome, pulisci_relazioni(dati, elementi_disponibili), compress_type=zipfile.ZIP_DEFLATED)
                    continue

                zi = zipfile.ZipInfo(nome)
                zi.compress_type = zipfile.ZIP_DEFLATED
                with out.open(zi, "w", force_zip64=True) as dst:
                    if tipo == "zip":
                        with zipfile.ZipFile(percorso) as z, z.open(nome_interno) as src:
                            shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
                    elif tipo == "annidato":
                        # Estrai il file XML dal file ZIP annidato
                        with zipfile.ZipFile(percorso) as z:
                            membri = [i for i in z.infolist() if not i.is_dir()]
                            if not membri:
                                raise ValueError(f"Archivio ZIP annidato vuoto: {percorso}")
                            
                            # Cerca il file che corrisponde a nome_interno o prendi l'unico file presente
                            membro_bersaglio = None
                            for m in membri:
                                nome_pulito = percorso_sicuro(m.filename)
                                if nome_pulito == nome_interno or PurePosixPath(nome_pulito).name == PurePosixPath(nome_interno).name:
                                    membro_bersaglio = m
                                    break
                            if not membro_bersaglio and len(membri) == 1:
                                membro_bersaglio = membri[0]

                            if not membro_bersaglio:
                                raise ValueError(f"Struttura imprevista nell'archivio ZIP annidato: {percorso}")

                            with z.open(membro_bersaglio) as src:
                                shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
                    else:
                        with percorso.open("rb") as src:
                            shutil.copyfileobj(src, dst, 8 * 1024 * 1024)

        # 5. Esegui la convalida di integrità del file generato
        if callback_progresso:
            callback_progresso("Convalida CRC e integrità XML...", 0.90)
        valida(file_parziale)
        
        # Sostituisci il file parziale con quello finale
        if file_uscita.exists():
            file_uscita.unlink()
        os.replace(file_parziale, file_uscita)

    finally:
        if file_parziale.exists():
            file_parziale.unlink()

    if callback_progresso:
        callback_progresso("Recupero completato con successo!", 1.0)
    print(f"[SUCCESSO] Progetto recuperato con successo in: {file_uscita}")
    return file_uscita


def estrai_gcode_metadata(cartella_radice, file_uscita, salta_backup=False, callback_progresso=None):
    """
    Estrae i file di stampa (.gcode.3mf o .gcode) rimasti nella sottocartella Metadata/
    quando Bambu Studio ha già rimosso i modelli 3D dalla cache di lavoro.
    Restituisce il percorso del file principale estratto (e l'elenco completo).
    """
    cartella_radice = Path(cartella_radice).resolve()
    if callback_progresso:
        callback_progresso("Ricerca file slice/G-code in Metadata...", 0.15)

    gcode_info = trova_gcode_metadata(cartella_radice)
    gcode_3mf = gcode_info["gcode_3mf"]
    gcode_raw = gcode_info["gcode"]

    if not gcode_3mf and not gcode_raw:
        raise ValueError("Nessun file .gcode.3mf o .gcode trovato in Metadata/.")

    file_uscita = Path(file_uscita).resolve()
    file_uscita.parent.mkdir(parents=True, exist_ok=True)

    if not salta_backup:
        if callback_progresso:
            callback_progresso("Creazione copia di backup dei dati originali...", 0.30)
        backup_sorgente(cartella_radice, file_uscita.parent)

    file_estratti = []
    sorgenti = gcode_3mf if gcode_3mf else gcode_raw
    estensione = ".gcode.3mf" if gcode_3mf else ".gcode"

    base_stem = file_uscita.stem
    if base_stem.lower().endswith(".gcode"):
        base_stem = base_stem[:-6]

    for idx, src in enumerate(sorgenti, start=1):
        if callback_progresso:
            pct = 0.40 + 0.50 * (idx / max(len(sorgenti), 1))
            callback_progresso(f"Estrazione e verifica slice {idx}/{len(sorgenti)}...", pct)

        if len(sorgenti) == 1:
            dest = file_uscita.parent / f"{base_stem}{estensione}"
        else:
            dest = file_uscita.parent / f"{base_stem}_piatto{idx}{estensione}"

        cnt = 1
        while dest.exists():
            dest = file_uscita.parent / f"{base_stem}_piatto{idx}_{cnt}{estensione}"
            cnt += 1

        if gcode_3mf:
            with zipfile.ZipFile(src) as z:
                if z.testzip() is not None:
                    raise ValueError(f"Il file {src.name} in Metadata/ è corrotto (CRC fallito).")

        shutil.copy2(src, dest)
        file_estratti.append(dest)
        print(f"[G-CODE] Estratto con successo: {dest}")

    if callback_progresso:
        callback_progresso("Estrazione G-code completata con successo!", 1.0)
    return file_estratti[0], file_estratti


def valida(percorso):
    """
    Verifica che il file 3MF generato rispetti gli standard:
    - Integrità CRC di tutti i file ZIP.
    - Presenza del file XML principale 3D/3dmodel.model.
    - Presenza di tutti i componenti e oggetti referenziati.
    - Validità XML effettiva dei modelli referenziati.
    """
    print(f"[CONVALIDA] Verifica integrità archivio: {percorso.name}...")
    with zipfile.ZipFile(percorso) as z:
        if z.testzip() is not None:
            raise ValueError("Convalida CRC fallita: l'archivio ZIP risulta danneggiato!")

        nomi_presenti = set(z.namelist())
        if "3D/3dmodel.model" not in nomi_presenti:
            raise ValueError("File principale 3D/3dmodel.model assente nel pacchetto!")

        modello_principale = ET.fromstring(z.read("3D/3dmodel.model"))
        riferimenti = {
            e.attrib[PROD_PATH].lstrip("/")
            for e in modello_principale.iter()
            if PROD_PATH in e.attrib
        }
        
        mancanti = riferimenti - nomi_presenti
        if mancanti:
            raise ValueError(f"Percorsi dei componenti mancanti: {sorted(mancanti)}")

        for nome in riferimenti:
            with z.open(nome) as f:
                intestazione = f.read(256).lstrip()
                if not (intestazione.startswith(b"<?xml") or intestazione.startswith(b"<model")):
                    raise ValueError(f"Il modello referenziato non è un file XML valido: {nome}")

    print(f"[CONVALIDA] Superata! File totali: {len(nomi_presenti)}, Modelli verificati: {len(riferimenti)}")


def main():
    parser = argparse.ArgumentParser(
        description="Strumento di recupero e ricostruzione progetti 3MF Bambu Studio da crash di Windows."
    )
    parser.add_argument("--discover", "--scopri", action="store_true", help="Elenca le sessioni di crash rilevate nel computer")
    parser.add_argument("--all", "--tutte", action="store_true", help="Con --scopri, include anche le sessioni chiuse con solo G-code o vuote")
    parser.add_argument("--input", "-i", type=Path, help="Cartella con i file del crash da recuperare")
    parser.add_argument("--output", "-o", type=Path, help="Percorso del file .3mf recuperato da salvare")
    parser.add_argument("--fallback", "-f", type=Path, help="File .3mf originale di riferimento per integrare eventuali modelli mancanti")
    parser.add_argument("--no-backup", action="store_true", help="Salta la creazione della copia di backup")
    parser.add_argument("--inspect", "--ispeziona", action="store_true", help="Analizza la cartella di input senza eseguire il recupero")
    parser.add_argument("--extract-gcode", "--estrai-gcode", action="store_true", help="Estrae i file .gcode.3mf o .gcode dalla sottocartella Metadata/")

    args = parser.parse_args()

    if args.discover:
        scopri(includi_tutte=args.all)
        return

    if not args.input:
        parser.error("Il parametro --input (-i) è obbligatorio a meno che non si usi --discover")

    radice = args.input.resolve()
    if radice.is_file():
        radice = radice.parent

    if args.inspect:
        inventario(radice)
        return

    if not args.output:
        parser.error("Il parametro --output (-o) è obbligatorio per avviare il recupero")

    if args.extract_gcode:
        estrai_gcode_metadata(radice, args.output, args.no_backup)
    else:
        recupera(radice, args.output, args.fallback, args.no_backup)


if __name__ == "__main__":
    main()
