# calibre_pex — PEX/LVS netlists pulled from the server

Grouped by **server source path**. All from `zhangz@101.6.68.147` (thu-wei).
This whole tree is gitignored (local-only, large).

## RISCA/  — source: `/home/zhangz/tsmc28/RISCA/calibre/pex` (chip-correct path)

| block | size | views present |
|---|---|---|
| L1_RISCAV4_CORE_POWER_SPLIT | 2.0G | full: pex.netlist + .pxi + .pex (大件) |
| L3_CMP_LITTLE | 3.4M | spef + dspf + spectre(.pex/.pxi) |
| L4_GM_BIG_CORE_DOUBLE | 18M | spef + dspf + spectre |
| LR_REF_BUFF_STAGE2_BIG | 152M | spef + dspf + spectre |

## LLM_AGENT/  — source: `/home/zhangz/TSMC28N/2025_LLM_AGENT/calibre/pex` (older path)

| block | size | views present |
|---|---|---|
| L3_SAR_11B | 30M | Calibre-native `.pex.netlist` + **`-spectre`** (re-emitted, Spectre-includable) |
| AMP_5T_D2S | 132K | spectre `.pex.netlist` only (no spef/dspf) |
| L5_CAP_ARRAY | 172K | spef + dspf + spectre (files carry `-20260621` date suffix) |

## View naming

- `*.pex.netlist` — top SPICE/Calibre netlist (RISCA blocks: Spectre-format; LLM_AGENT L3_SAR_11B/AMP: Calibre-native `mgc_rve_*`, NOT directly Spectre-includable)
- `*-spectre`, `*-spectre.pex`, `*-spectre.<cell>.pxi` — native Spectre subckt + parasitics (directly `include`-able)
- `*-spef`, `*-dspf` — SPEF / DSPF parasitic exchange formats
- `*.src.net` — source (schematic) device netlist
- `*.lvs.report(.ext)`, `PIPO.LOG/SUM.*` — LVS report + Calibre run logs

## Re-emitting a Spectre view from an existing extraction

If a block's `svdb/<cell>.pdb` is still on the server, re-format without re-extracting:
run Calibre xRC formatting with `-format SPECTRE` → produces `<cell>.pex.netlist-spectre`
(used for L3_SAR_11B). See [[sar-11b-tb-measurement]] memory.
