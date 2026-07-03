# Crawler exploration on the L2_SAR_11B_X2 designs

What `netlist-crawler` can and can't extract from this 11-bit SAR ADC, found by
running every command against the pulled netlists. Run from the repo root with
`NC=.venv/bin/netlist-crawler` (needs `pip install -e '.[parasitics]'` for `scan`).

## Two engines, two input files

| Engine | Input | What it reads |
|---|---|---|
| Structural / semantic | `*.src.net` | The `X` instance hierarchy (clean schematic). |
| Parasitic scan | `*.pex.netlist` | The full 664K-line extracted R/C network. |

The structural side reads `.src.net` best. The PEX deck has one giant flat
`subckt`, so structural commands are uninformative on it — point `scan` there.

## Structural / semantic commands

- **`summarize` / `brief` / `list-subckts`** — hierarchy + per-subckt device
  counts. **Gotcha:** no flattening by default. `summarize --topcell
  L2_SAR_11B_X2` reports only **2 devices** (the two `L3_SAR_11B` instances).
  Add `--expand-depth N`:
  - `L3_SAR_11B --expand-depth 5` → 2623 devices (2216 C + 282 M), 231 nets.
  - `L2_SAR_11B_X2 --expand-depth 9` → 5246 devices, 456 nets; the two channels
    mirror exactly (`VTOPN/VTOPP` degree 1115, `VBOT<11>` degree 503 = MSB bank).
  - ~250 `X` stay unexpanded — std cells / `cfmom` / `DCAP` whose masters live in
    the `.spi` libraries that aren't included.

- **`detect`** — works well on **leaf subckts**, explodes on flattened ones.
  - `L4_COMPARATOR`: cleanly finds the input pair `MM1/MM0` (VINN/VINP), the
    clock pair, and the `TRIM_OS<3:0>` offset-trim pairs — all conf 0.88.
  - But it is combinatorial: detect-all on the comparator = 87 diff-pairs +
    62 tail-sources; on flattened `L3` = **5151 + 16162**. Any two same-model
    devices sharing a source node get flagged. Use on small cells only.
  - Supported patterns: `diff-pair`, `current-mirror`, `cascode`, `active-load`,
    `tail_current_source` (note: `tail-current` is rejected). On this StrongARM
    comparator, `current-mirror` / `cascode` / `active-load` returned **nothing**
    — the first-pass rules miss them.

- **`explain` / `explain-net`** — solid net classification. On the comparator:
  `VS → tail (0.82)`, `LP/LM → differential_input (0.82)`, `DCMPP/DCMPN →
  output_candidate`, `CLK → bias/clock`. `explain <device>` prints terminals +
  role (returns "no role" for switches/buffers it has no rule for).

- **`path` / `classify-path`** — connectivity with semantic scoring.
  **Gotcha:** traverses supply rails unless you pass `--exclude-common-nets`:
  - without: `VINP → MM0 → VSS → MM106 → DCMPP` (shorts through VSS).
  - with: `VINP → MM0 → VN1 → MM45 → LM → MM10 → net1 → MM106 → DCMPP`
    (the real preamp→latch path). `classify-path` scores it conf 0.86.

- **`export-graph`** — bipartite device-net graph (comparator: 64 nodes /
  152 edges) as JSON/GraphML, with `patterns` + `summary` attached.

- **`export-ir` / `validate-ir` / `annotation-coverage`** — persistent
  `netlist-crawler.ir.v1`. On `L3_SAR_11B`: 5 instances, 80 nets, 128 edges,
  **26 auto-annotations** (all `VBOT<n>` → `bias` conf 0.78). Validation passes;
  coverage is partial (nets 26/80, devices 0/5) — expected, rules are first-pass.

## Parasitic `scan` — the most capable part

Parses the real `*.pex.netlist` in ~1s (caches 47.6 MB), counts match the files
exactly: **193,409 R / 45,522 Cg / 160,236 Cc / 169,563 nodes**. Sections:

1. **Per-net Σ R** — VDD 136k, VSS 52k, then `RSTP1/2` 33k and `CLKSAR1/2` 28k
   (high series-R clock/reset nets worth watching).
2. **Per-net Σ Cg** — total 411 fF; the merged CDAC node `XI` carries 245 fF (60%).
3. **Net-pair Cc** — coupling ranked: `VREFP↔VREFN 16.7 fF` (reference crosstalk —
   the ADC-critical one), VIP/VIN↔array, `CLKSAR1/2↔XI ~3 fF`.
6. **Drill-down** — devices touching the Cg-heavy nets.
7. **Red flags** — 315 nets over the Σ R ≥ 1 kΩ threshold.
8. **Driving-point R** (`--trace`) and **within-net R mesh** (`--within-net`).

The headline is **`--within-net`**: a real scipy R-mesh solve over every pin on a
net. On `VREFP` (149 pins, 60 sampled): pin-to-pin effective-R distribution
median 73 Ω, max 115 Ω, and it names the electrically farthest pair as
**SAR1-logic ↔ SAR2-logic VREFP (115 Ω)** — the cross-channel reference IR-drop
that drives inter-channel settling mismatch. That is genuinely useful sign-off data.

## Using scan to compare the two series

The whole point of the `_CLK_COUPLING` series shows up only in the raw deltas:

| | R | Cg | Cc | nodes |
|---|---|---|---|---|
| `L2_SAR_11B_X2` | 193,409 | 45,522 | 160,236 | 169,563 |
| `..._CLK_COUPLING` | 193,412 | 45,524 | 160,244 | 169,566 |
| **Δ** | **+3** | **+2** | **+8** | **+3** |

So the second extraction adds only ~8 coupling caps + 2 ground caps on a handful
of internal clock-adjacent nodes. At the aggregated net-pair level the clock
coupling (`CLKSAR1/2 ↔ XI/VDD`) is **identical** between the two — the delta is
sub-fF and localized, not visible in the rounded ranking.

## Bottom line

- Structural side: good for **per-cell** topology/semantics; remember
  `--expand-depth` and `--exclude-common-nets`; treat `detect` counts as a
  candidate firehose, not ground truth.
- Parasitic `scan` is the mature, high-value engine — works on the real PEX at
  scale, and `--within-net` / net-pair Cc give real post-layout insight.
