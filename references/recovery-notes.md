# Recovery notes

## Evidence levels

- Community-documented: Windows crash/autosave remnants have been reported under `%LOCALAPPDATA%\Temp\bamboo_model`, with date/timestamp subdirectories and sometimes a file named only `.3mf`.
- Field-verified in July 2026: a real crash remnant contained valid package metadata plus 45 files named `object_N.model` that were actually one-entry ZIP archives. Each inner archive contained the genuine XML model at `3D/Objects/object_N.model`. Directly packaging the outer archives caused Bambu Studio parsing failure; streaming out the inner XML and restoring referenced paths produced a working project.
- Implementation inference: cache layout and naming may change between Bambu Studio versions and platforms. Discover candidates rather than hard-coding a single directory as guaranteed.

## Useful public sources

- Bambu Lab Community Forum, “Multi-Window Auto Save / Recovery”: https://forum.bambulab.com/t/multi-window-auto-save-recovery/241654
- Bambu Studio source repository: https://github.com/bambulab/BambuStudio
- Bambu Studio command-line usage: https://github.com/bambulab/BambuStudio/wiki/Command-Line-Usage

Do not describe the community recovery path as official Bambu Lab documentation.

