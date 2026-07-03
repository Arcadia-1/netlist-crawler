# Full-Design Netlists (local-only)

Two complete post-layout (Calibre xRC) netlists of an **11-bit differential SAR
ADC**, pulled from the remote server
`zhangz@101.6.68.147:/home/zhangz/TSMC28N/2025_LLM_AGENT/calibre/pex`
on 2026-06-21. Process: TSMC 28nm (tcbn28hpcplusbwp12t30p140).

This is the "large" tier of the example corpus — full extracted designs, far
bigger than the snippets in `examples/*.sp`, the fixtures in
`examples/parasitics/`, or the ferrosim decks in `examples/ferrosim/`.

> **Not tracked by git.** Listed in the repo `.gitignore`; lives only on this
> machine. Contains foundry-derived PEX data — keep it out of any commit.

## The two series

| Series | What it is |
|---|---|
| `L2_SAR_11B_X2/` | Standard Calibre xRC extraction of the dual SAR top cell. |
| `L2_SAR_11B_X2_CLK_COUPLING/` | Same layout, re-extracted with clock-coupling parasitics preserved. |

The two are the **same physical design**. The pre-layout source (`.src.net`)
differs only in the top-cell name; the parasitic netlists are nearly identical
in raw counts (R: 193409 vs 193412, C: 45486 vs 45488). The intended
difference is *how* clock-net coupling parasitics are extracted, not the
circuit topology — useful as an A/B pair for studying coupling sensitivity.

## Files per series

Each directory holds five files (the binary `.calibre.db` was intentionally
left on the server):

| File | Size | Role |
|---|---|---|
| `*.pex.netlist` | ~3.2 MB | Top netlist (`simulator lang=spectre`); `include`s the two below. |
| `*.pex.netlist.pex` | ~10 MB | Lumped parasitic R/C devices. |
| `*.pex.netlist.*.pxi` | ~20 MB | Parasitic instance section. |
| `*.src.net` | ~35 KB | Pre-layout source CDL (schematic, golden reference). |
| `*.lvs.report` | ~165 KB | Calibre LVS report — both series are **CORRECT**. |

The two `include` lines in `*.pex.netlist` use relative filenames that match the
files in the same directory, so the netlist resolves as-is from its own folder.

## Design hierarchy (from `.src.net`)

```
L2_SAR_11B_X2            dual top — instantiates 2× L3_SAR_11B (DOUT1 / DOUT2)
└── L3_SAR_11B           one 11-bit SAR channel
    ├── L4_BTS_X2        differential bootstrap sampling switch
    │   └── LB_SAR_BTS   bootstrap switch unit
    ├── L4_CDAC          capacitive DAC
    │   ├── L5_CAP_ARRAY 372 unit caps (LB_CUNIT_X3 ×368, LB_CUNIT_X1 ×4)
    │   └── L5_DAC_SWI   DAC bottom-plate switches
    ├── L4_COMPARATOR    dynamic comparator (38 devices, TRIM_OS<3:0> offset trim)
    └── L4_LOGIC_SWI     SAR logic / switching (90 devices)
        ├── L5_LATCH_CELL
        └── L5_LATCH_CELL_LSB
```

Top ports: `VIP/VIN` (diff input), `VREFP/VREFN`, `CLKSAR1/CLKSAR2`,
`DOUT1<11:0>`/`DOUT2<11:0>`, `TRIM_OS1/2<3:0>`, `RSTP1/2`, `VDD/VSS`.

## Quick checks

```bash
NC=.venv/bin/netlist-crawler   # run from repo root
$NC summarize    examples/full_designs/L2_SAR_11B_X2/L2_SAR_11B_X2.src.net --topcell L2_SAR_11B_X2
$NC list-subckts examples/full_designs/L2_SAR_11B_X2/L2_SAR_11B_X2.src.net
$NC export-ir    examples/full_designs/L2_SAR_11B_X2/L2_SAR_11B_X2.src.net -o L2_SAR_11B_X2.nlc.json
```

Note: the structural parser reads the `X` instance hierarchy in `.src.net`. The
`.pex.netlist` is a `simulator lang=spectre` deck whose devices live in the
included `.pex`/`.pxi` files — point parasitic commands (`scan`, `prescribe`) at
those when doing post-layout RC analysis.
