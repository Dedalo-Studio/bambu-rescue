import argparse
import os
import re
import shutil
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

OBJECT_RE = re.compile(r"object_(\d+)\.model", re.I)
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
PROD_PATH = "{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}path"


def discover():
    roots = []
    for value in (os.environ.get("TEMP"), os.environ.get("TMP")):
        if value:
            roots.append(Path(value))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(Path(local) / "Temp")
    seen = set()
    candidates = []
    for root in roots:
        if not root.exists() or root in seen:
            continue
        seen.add(root)
        for name in ("bamboo_model", "BambuStudio", "Bambu Studio"):
            base = root / name
            if base.exists():
                for p in base.rglob("*"):
                    if p.is_file() and (p.suffix.lower() == ".3mf" or OBJECT_RE.fullmatch(p.name)):
                        candidates.append((p.stat().st_mtime, p.stat().st_size, p))
    for mtime, size, path in sorted(candidates, reverse=True):
        print(f"{mtime:.0f}\t{size}\t{path}")


def safe_name(name):
    p = PurePosixPath(name.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"unsafe archive path: {name}")
    return str(p)


def find_baseline(root):
    files = [p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".3mf"]
    files += [p for p in root.iterdir() if p.is_file() and p.name == ".3mf"]
    valid = []
    for p in dict.fromkeys(files):
        try:
            with zipfile.ZipFile(p) as z:
                if "[Content_Types].xml" in z.namelist():
                    valid.append(p)
        except (OSError, zipfile.BadZipFile):
            pass
    return max(valid, key=lambda p: p.stat().st_mtime) if valid else None


def inventory(root):
    baseline = find_baseline(root)
    objects = []
    for folder in (root / "3D", root / "3D" / "Objects"):
        if folder.exists():
            objects.extend(p for p in folder.glob("object_*.model") if p.is_file())
    objects = sorted(dict.fromkeys(objects), key=lambda p: int(OBJECT_RE.fullmatch(p.name).group(1)))
    print(f"root={root}")
    print(f"baseline={baseline}")
    print(f"loose_objects={len(objects)}")
    nested = 0
    for p in objects:
        if zipfile.is_zipfile(p):
            nested += 1
    print(f"nested_zip_objects={nested}")
    return baseline, objects


def backup_source(root, output_parent):
    stamp = time.strftime("%Y%m%d_%H%M%S")
    backup = output_parent / f"{root.name}_source_backup_{stamp}.zip"
    with zipfile.ZipFile(backup, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(root).as_posix())
    with zipfile.ZipFile(backup) as z:
        if z.testzip() is not None:
            backup.unlink(missing_ok=True)
            raise ValueError("source backup failed CRC validation")
    print(f"source_backup={backup}")
    return backup


def clean_relationships(data, available):
    root = ET.fromstring(data)
    for rel in list(root):
        target = rel.attrib.get("Target", "").lstrip("/")
        rel_type = rel.attrib.get("Type", "")
        if target not in available and not rel_type.endswith("/3dmodel"):
            root.remove(rel)
    ET.register_namespace("", REL_NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def recover(root, output, fallback=None, no_backup=False):
    baseline, loose = inventory(root)
    if not baseline and not (root / "[Content_Types].xml").exists():
        raise ValueError("no baseline 3MF or unpacked [Content_Types].xml found")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not no_backup:
        backup_source(root, output.parent)
    partial = output.with_suffix(output.suffix + ".partial")
    if output.exists() or partial.exists():
        raise FileExistsError("output or partial file already exists; choose a new name")
    entries = {}
    if baseline:
        with zipfile.ZipFile(baseline) as z:
            for info in z.infolist():
                if not info.is_dir():
                    entries[safe_name(info.filename)] = ("zip", baseline, info.filename)
    else:
        for p in root.rglob("*"):
            if p.is_file() and p != output:
                entries[p.relative_to(root).as_posix()] = ("file", p, None)
    if fallback:
        fallback = fallback.resolve()
        with zipfile.ZipFile(fallback) as z:
            if z.testzip() is not None:
                raise ValueError("fallback 3MF failed CRC validation")
            for info in z.infolist():
                if not info.is_dir():
                    name = safe_name(info.filename)
                    entries.setdefault(name, ("zip", fallback, info.filename))
    for p in loose:
        target = f"3D/Objects/{p.name}"
        entries[target] = ("inner" if zipfile.is_zipfile(p) else "file", p, target if zipfile.is_zipfile(p) else None)
        entries.pop(f"3D/{p.name}", None)
    available = set(entries)
    try:
        with zipfile.ZipFile(partial, "w", allowZip64=True) as out:
            for name, source in sorted(entries.items()):
                kind, path, inner_name = source
                if name == "_rels/.rels":
                    if kind == "zip":
                        with zipfile.ZipFile(path) as z:
                            data = z.read(inner_name)
                    else:
                        data = path.read_bytes()
                    out.writestr(name, clean_relationships(data, available), compress_type=zipfile.ZIP_DEFLATED)
                    continue
                zi = zipfile.ZipInfo(name)
                zi.compress_type = zipfile.ZIP_DEFLATED
                with out.open(zi, "w", force_zip64=True) as dst:
                    if kind == "zip":
                        with zipfile.ZipFile(path) as z, z.open(inner_name) as src:
                            shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
                    elif kind == "inner":
                        with zipfile.ZipFile(path) as z:
                            members = [i for i in z.infolist() if not i.is_dir()]
                            if len(members) != 1 or safe_name(members[0].filename) != inner_name:
                                raise ValueError(f"unexpected nested archive structure: {path}")
                            with z.open(members[0]) as src:
                                shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
                    else:
                        with path.open("rb") as src:
                            shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
        validate(partial)
        os.replace(partial, output)
    finally:
        if partial.exists():
            partial.unlink()
    print(f"recovered={output}")


def validate(path):
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError("CRC validation failed")
        names = set(z.namelist())
        main = ET.fromstring(z.read("3D/3dmodel.model"))
        refs = {e.attrib[PROD_PATH].lstrip("/") for e in main.iter() if PROD_PATH in e.attrib}
        missing = refs - names
        if missing:
            raise ValueError(f"missing component paths: {sorted(missing)}")
        for name in refs:
            with z.open(name) as f:
                head = f.read(256).lstrip()
                if not (head.startswith(b"<?xml") or head.startswith(b"<model")):
                    raise ValueError(f"referenced model is not XML: {name}")
    print(f"validated_entries={len(names)} referenced_models={len(refs)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--input", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--fallback", type=Path, help="trusted original 3MF used only to fill missing package entries")
    ap.add_argument("--no-backup", action="store_true", help="skip automatic source backup only when a verified backup already exists")
    ap.add_argument("--inspect", action="store_true")
    args = ap.parse_args()
    if args.discover:
        discover(); return
    if not args.input:
        ap.error("--input is required unless --discover is used")
    root = args.input.resolve()
    if root.is_file():
        root = root.parent
    if args.inspect:
        inventory(root); return
    if not args.output:
        ap.error("--output is required for recovery")
    recover(root, args.output, args.fallback, args.no_backup)


if __name__ == "__main__":
    main()
