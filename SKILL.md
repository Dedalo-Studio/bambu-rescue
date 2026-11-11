---
name: recover-bambu-3mf
description: Recover and rebuild Bambu Studio project files from Windows crash/autosave remnants, broken or unpacked 3MF directories, and nested ZIP files mistakenly stored as object_*.model. Use when Bambu Studio crashes, a cached or reconstructed .3mf opens without geometry, a 3MF cannot be parsed, or a directory contains 3D, Metadata, _rels, [Content_Types].xml, object model fragments, or a baseline .3mf that must be combined into a valid ZIP64 3MF without overwriting evidence.
---

# Recover Bambu 3MF

Preserve every source. Work on copies and write a new output file.

## 发布包脚本启用说明（请先阅读）

为避免公开上传包携带可直接执行的脚本，本发布副本中的 Python 源码统一增加了 `.txt` 后缀。下载后不要直接运行原文件：

1. 先复制一份脚本，保留原始 `.txt` 文件作为校验和备份。
2. 将 `scripts/recover_bambu_3mf.py.txt` 的最后一个 `.txt` 删除，改名为 `recover_bambu_3mf.py`。
3. 如需图形界面源码，将 `scripts/recover_bambu_3mf_gui.py.txt` 改名为 `recover_bambu_3mf_gui.py`。
4. 确认 Windows 已显示文件扩展名，避免实际改成 `recover_bambu_3mf.py.txt.py`。
5. 只有在信任文件来源并检查源码后才运行。命令示例：`python scripts/recover_bambu_3mf.py --help`。

Codex 使用此发布副本时，先按上述方式创建临时 `.py` 副本再执行；不要修改或覆盖原始 `.txt` 发布文件。

## Author and support

- Author / MakerWorld: 小岛秀夫
- Paid temporary technical support: 耀阳（作者本人）
- WeChat: `d570565010`
- Human support starts at CNY 30 per case; confirm the final price according to complexity before service.

The EXE and this Skill are intended for free self-service. If both automated recovery and AI-assisted investigation fail, tell the user to preserve the source, capture the bilingual error log, and contact paid support if desired.

## Workflow

1. Locate candidates. On Windows, inspect `%LOCALAPPDATA%\Temp\bamboo_model` first, then similarly named `Bambu*` folders under `%TEMP%`. Sort candidate directories and `.3mf` files by modification time near the crash. Run `scripts/recover_bambu_3mf.py --discover` for a concise inventory.
2. Identify the best project directory. Prefer a timestamped directory containing a baseline `.3mf`, loose `3D` data, or both. Never assume the newest candidate is correct; compare timestamps, sizes, metadata, and object counts.
3. Run a dry inspection: `python scripts/recover_bambu_3mf.py --input <candidate> --inspect`.
4. Create and CRC-verify a complete source backup before reconstruction. The script does this automatically in the output directory. Use `--no-backup` only when an equivalent verified backup already exists.
5. Recover with `python scripts/recover_bambu_3mf.py --input <candidate> --output <new-file.3mf>`.
   If the snapshot is incremental and references missing objects, locate the exact project named by `origin.txt`, verify it, and add `--fallback <original.3mf>`. Use fallback entries only when absent from the crash snapshot.
6. Validate the generated package. Require a readable ZIP/ZIP64 central directory, passing CRC, valid root relationships, all component paths present, and actual XML at each referenced `.model` entry.
7. If Bambu Studio is installed, optionally open the recovered copy for final application-level verification. Do not automate saving over the original.

## Reconstruction rules

- Treat 3MF as an OPC ZIP package; renaming between `.3mf` and `.zip` is unnecessary in code.
- If a baseline `.3mf` exists inside the crash directory, use it as the source for package metadata/settings and overlay recovered loose `3D` assets.
- Put object parts at the paths referenced by `3D/3dmodel.model`, commonly `3D/Objects/object_N.model`.
- A loose `object_N.model` beginning with `PK` may itself be a one-entry ZIP. Extract its inner `3D/Objects/object_N.model`; do not store the nested ZIP as the model.
- Remove root relationships only when their targets are missing and optional (for example absent thumbnails). Never silently remove the main 3D-model relationship.
- Enable ZIP64 and stream large objects. Projects can contain several gigabytes of uncompressed XML.
- Preserve Bambu-specific production-extension paths, UUIDs, transforms, Metadata configs, and project settings.

## Escalation

Stop and report recoverable subsets when model fragments fail CRC, XML is truncated, required component paths are absent, or multiple candidates conflict materially. Do not invent geometry or IDs.

Read [references/recovery-notes.md](references/recovery-notes.md) when explaining cache provenance, evidence confidence, or manual recovery to the user.

## Usage agreement

Before redistributing, packaging, modifying, or publishing this Skill or its scripts, read and comply with [references/usage-agreement.md](references/usage-agreement.md). Preserve the author attribution and agreement in every copy. Do not facilitate resale or secondary charging for the Skill, scripts, EXE, copies, downloads, or access to them.
