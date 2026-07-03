# Local Artifact Sources

This repository intentionally does not track full foundry-derived PEX/LVS
artifacts, raw Spectre outputs, or local simulator work directories.  The files
below are local analysis inputs that can be restored from the lab server when
needed.

## Server Sources

Use `rsync -ah --info=progress2` from another machine with SSH access.

```bash
# RISCA chip-level and block-level Calibre PEX/LVS artifacts.
rsync -ah --info=progress2 \
  zhangz@101.6.68.147:/home/zhangz/tsmc28/RISCA/calibre/pex/ \
  artifacts/calibre_pex/RISCA/

# Older LLM_AGENT Calibre PEX/LVS artifacts.
rsync -ah --info=progress2 \
  zhangz@101.6.68.147:/home/zhangz/TSMC28N/2025_LLM_AGENT/calibre/pex/ \
  artifacts/calibre_pex/LLM_AGENT/
```

Selective block pulls:

```bash
# RISCA full chip.  This is the large one.
rsync -ah --info=progress2 \
  zhangz@101.6.68.147:/home/zhangz/tsmc28/RISCA/calibre/pex/L1_RISCAV4_CORE_POWER_SPLIT/ \
  artifacts/calibre_pex/RISCA/L1_RISCAV4_CORE_POWER_SPLIT/

# Smaller RISCA blocks.
rsync -ah --info=progress2 \
  zhangz@101.6.68.147:/home/zhangz/tsmc28/RISCA/calibre/pex/L3_CMP_LITTLE/ \
  artifacts/calibre_pex/RISCA/L3_CMP_LITTLE/
rsync -ah --info=progress2 \
  zhangz@101.6.68.147:/home/zhangz/tsmc28/RISCA/calibre/pex/L4_GM_BIG_CORE_DOUBLE/ \
  artifacts/calibre_pex/RISCA/L4_GM_BIG_CORE_DOUBLE/
rsync -ah --info=progress2 \
  zhangz@101.6.68.147:/home/zhangz/tsmc28/RISCA/calibre/pex/LR_REF_BUFF_STAGE2_BIG/ \
  artifacts/calibre_pex/RISCA/LR_REF_BUFF_STAGE2_BIG/

# Older LLM_AGENT blocks.
rsync -ah --info=progress2 \
  zhangz@101.6.68.147:/home/zhangz/TSMC28N/2025_LLM_AGENT/calibre/pex/L3_SAR_11B/ \
  artifacts/calibre_pex/LLM_AGENT/L3_SAR_11B/
rsync -ah --info=progress2 \
  zhangz@101.6.68.147:/home/zhangz/TSMC28N/2025_LLM_AGENT/calibre/pex/AMP_5T_D2S/ \
  artifacts/calibre_pex/LLM_AGENT/AMP_5T_D2S/
rsync -ah --info=progress2 \
  zhangz@101.6.68.147:/home/zhangz/TSMC28N/2025_LLM_AGENT/calibre/pex/L5_CAP_ARRAY/ \
  artifacts/calibre_pex/LLM_AGENT/L5_CAP_ARRAY/
```

If only the schematic source netlists are needed, pull just `*.src.net`:

```bash
mkdir -p artifacts/calibre_pex/RISCA/{L1_RISCAV4_CORE_POWER_SPLIT,L3_CMP_LITTLE,L4_GM_BIG_CORE_DOUBLE,LR_REF_BUFF_STAGE2_BIG}
mkdir -p artifacts/calibre_pex/LLM_AGENT/{L3_SAR_11B,AMP_5T_D2S,L5_CAP_ARRAY}

rsync -ah zhangz@101.6.68.147:/home/zhangz/tsmc28/RISCA/calibre/pex/L1_RISCAV4_CORE_POWER_SPLIT/L1_RISCAV4_CORE_POWER_SPLIT.src.net artifacts/calibre_pex/RISCA/L1_RISCAV4_CORE_POWER_SPLIT/
rsync -ah zhangz@101.6.68.147:/home/zhangz/tsmc28/RISCA/calibre/pex/L3_CMP_LITTLE/L3_CMP_LITTLE.src.net artifacts/calibre_pex/RISCA/L3_CMP_LITTLE/
rsync -ah zhangz@101.6.68.147:/home/zhangz/tsmc28/RISCA/calibre/pex/L4_GM_BIG_CORE_DOUBLE/L4_GM_BIG_CORE_DOUBLE.src.net artifacts/calibre_pex/RISCA/L4_GM_BIG_CORE_DOUBLE/
rsync -ah zhangz@101.6.68.147:/home/zhangz/tsmc28/RISCA/calibre/pex/LR_REF_BUFF_STAGE2_BIG/LR_REF_BUFF_STAGE2_BIG.src.net artifacts/calibre_pex/RISCA/LR_REF_BUFF_STAGE2_BIG/
rsync -ah zhangz@101.6.68.147:/home/zhangz/TSMC28N/2025_LLM_AGENT/calibre/pex/L3_SAR_11B/L3_SAR_11B.src.net artifacts/calibre_pex/LLM_AGENT/L3_SAR_11B/
rsync -ah zhangz@101.6.68.147:/home/zhangz/TSMC28N/2025_LLM_AGENT/calibre/pex/AMP_5T_D2S/AMP_5T_D2S.src.net artifacts/calibre_pex/LLM_AGENT/AMP_5T_D2S/
rsync -ah zhangz@101.6.68.147:/home/zhangz/TSMC28N/2025_LLM_AGENT/calibre/pex/L5_CAP_ARRAY/L5_CAP_ARRAY.src.net artifacts/calibre_pex/LLM_AGENT/L5_CAP_ARRAY/
```

The local `examples/full_designs/` tree is a curated copy/subset of those
artifacts for crawler stress testing:

- `examples/full_designs/L1_RISCAV4_CORE_POWER_SPLIT/` comes from
  `artifacts/calibre_pex/RISCA/L1_RISCAV4_CORE_POWER_SPLIT/`.
- `examples/full_designs/L2_SAR_11B_X2/` and
  `examples/full_designs/L2_SAR_11B_X2_CLK_COUPLING/` come from
  `/home/zhangz/TSMC28N/2025_LLM_AGENT/calibre/pex/`.

## What Not To Commit

- `*.pex.netlist`, `*.pex.netlist.pex`, `*.pxi`, `*.calibre.db`: large
  Calibre/Spectre extraction products.
- `*.src.net`, `*.lvs.report`, `PIPO.*`: small enough to store, but still real
  circuit/foundry-derived design artifacts.  Restore them from the server
  instead of publishing them in this repository.
- `WORK/`: local scratch simulations, derived netlists, raw waveform data, and
  exploratory scripts.

## Local Sizes Observed

At the time this note was written:

- `examples/full_designs/`: about 2.0 GB.
- `artifacts/calibre_pex/`: about 2.2 GB.
- `WORK/`: about 2.8 GB.
