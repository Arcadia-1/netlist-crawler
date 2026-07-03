# PEX Netlist File Structure (Calibre xRC three-part split)

Notes from reading the `L2_SAR_11B_X2` files. The same layout applies to the
`L2_SAR_11B_X2_CLK_COUPLING` series (identical organization, different top-cell
name and a slightly different clock-coupling extraction).

## The five files per series

| File | Lines | What it holds |
|---|---|---|
| `*.src.net` | 823 | Pre-layout source CDL (golden schematic netlist). |
| `*.pex.netlist` | 46,820 | Top deck: back-annotated devices + `include`s of the two files below. |
| `*.pex.netlist.pex` | 245,887 | Parasitic **models**: 1022 `PM_*` subckts (per-net R + grounded C). |
| `*.pex.netlist.*.pxi` | 371,993 | Parasitic **instances**: 1022 `x_PM_*` calls + 160,236 coupling caps `cc_*`. |
| `*.lvs.report` | — | Calibre LVS comparison (result: CORRECT). |

`*.calibre.db` (binary Calibre database) was left on the server.

---

## 1. `*.src.net` — pre-layout source

Plain auCdl / SPICE. `.INCLUDE`s the TSMC 28nm standard-cell and device-model
`.spi` libraries, then 13 `.SUBCKT` definitions building bottom-up to the top
`L2_SAR_11B_X2`. Leaf cells go to transistor level, e.g.:

```
.SUBCKT LB_CUNIT_X3 BOT TOP        # unit cap = 3× 200aF ideal caps
CC2 TOP BOT 200.0a $[CP]
...
.SUBCKT LB_SAR_BTS CLK VBST VDD VIN VSS   # bootstrap switch, pch/nch_mac + cfmom MOM cap
MM0 VBST net2 net33 net33 pch_ulvt_mac l=30n w=500n m=8 nf=1
...
```

This is the **golden reference** LVS compares the layout against. It is what the
`netlist-crawler` structural parser reads cleanly (the `X` instance hierarchy).

---

## 2. `*.pex.netlist` — top deck (back-annotated)

```
simulator lang=spectre
include "L2_SAR_11B_X2.pex.netlist.pex"
subckt L2_SAR_11B_X2 ( CLKSAR1 CLKSAR2 DOUT1<11>...VDD VIN VIP VREFN VREFP VSS )
  <2770 device instances>  +  <1492 unit-cap instances>
ends
include "...pxi"   (the .pxi is pulled in via the top file too)
```

Two instance kinds inside the top subckt:

- **Uppercase `X...` = back-annotated MOSFETs (2770).** Called directly on the
  `nch_mac`/`pch_mac` model with the FULL layout-extracted parameter set —
  `ad/as/pd/ps/nrd/nrs`, stress/LOD (`sa/sb/sca/scb`), DFM and proximity terms.
  A schematic device `MM3` is split by layout into `MM3`, `MM3@2 … MM3@10`
  (per-finger / per-segment fragments). Each terminal connects to a **parasitic
  node**, not the ideal net:
  `N_<net>_<inst>_d` (drain), `_g` (gate), `_s` (source), `_b` (bulk).

- **Lowercase `x...` = unit-cap instances (1492).** Call the `LB_CUNIT_X3`
  unit-cap master between a `VBOTP<n>` plate and the `VTOPP` top plate — the
  binary-weighted CDAC array.

Hierarchy is preserved in the instance name with escaped slashes:
`XXI_SAR1\/XI_CDACP\/MM3` = device `MM3` in `XI_CDACP` in channel `XI_SAR1`.

---

## 3. `*.pex.netlist.pex` — parasitic models (intra-net R/C)

1022 subckts, one per extracted net, named `PM_L2_SAR_11B_X2%<netpath>`:

```
subckt PM_L2_SAR_11B_X2%XI_SAR1/XI7/XI0/net33 ( 2 20 22 24 ... VSS )
  c814 ( 2839 VSS ) capacitor c=0.00261582f   # grounded cap on internal node
  r... ( 2839 2830 ) resistor r=...            # distributed wire resistance
  ...
ends
```

Each `PM_` subckt is the **distributed RC tree of a single net**: numbered
internal nodes, series `resistor`s modelling metal/via resistance, and
`capacitor`s to `VSS` modelling that net's self/area capacitance. Ports are the
net's connection points (device terminals + coupling tap nodes).

---

## 4. `*.pex.netlist.*.pxi` — parasitic instances + coupling

Two things live here:

- **`x_PM_*` (1022)** — instantiates each `PM_` model from the `.pex` file,
  wiring its internal parasitic nodes to the real device-terminal nodes
  (`N_..._s`, `N_..._b`, etc.) declared in the top deck.

- **`cc_*` coupling caps (160,236)** — the inter-net capacitors. Each connects a
  parasitic node of one net to a parasitic node of a **different** net:

  ```
  cc_1 ( N_XI_SAR1/XI7/XI0/net33_c_49_n  N_XI_SAR1/XI7/XI0/net1_c_1004_n ) capacitor c=...
  ```

  This is the cross-coupling that matters for SAR ADC kickback / clock feedthrough
  — and the `_CLK_COUPLING` series exists to extract these more faithfully on the
  clock nets.

---

## Mental model

```
.src.net          ideal schematic  (what it SHOULD be)
                          │  LVS: CORRECT
                          ▼
.pex.netlist      real devices, terminals fan out to N_<net>_<inst>_x nodes
   ├── include .pex   each net's own R-tree + caps-to-ground   (PM_ models)
   └── include .pxi   wire those models in  +  net-to-net coupling caps (cc_)
```

So: **devices** sit in the top deck, **self-parasitics** in `.pex`, **wiring of
parasitics + mutual coupling** in `.pxi`. To simulate, you load `.pex.netlist`
and the two includes resolve relatively from the same directory.
