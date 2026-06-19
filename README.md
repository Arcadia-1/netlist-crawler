# Netlist Crawler

Semantic static analysis CLI for LLM-assisted analog circuit understanding.

Netlist Crawler turns SPICE/Spectre-style netlists into queryable graph and
semantic summaries for AI agents. The goal is not to make an LLM re-implement
graph algorithms on demand, but to provide stable tools for topology queries,
hierarchy summaries, analog pattern detection, and concise JSON/text outputs.

This repository starts from the existing `analog-netlist-crawl` implementation:
validated post-layout netlist adapters, a canonical circuit IR, sparse
resistance/capacitance kernels, report generation, and R/Cc prescription tools.
The broader repo direction is to extend that foundation toward agent-facing
analog circuit understanding.

## Project Scope

Netlist Crawler focuses on the infrastructure layer:

- Parse practical SPICE/Spectre netlists.
- Build device-net and hierarchy graphs.
- Query neighborhoods, connectivity paths, fanin/fanout-style relationships,
  and subcircuit summaries.
- Detect analog semantic patterns such as differential pairs, current mirrors,
  cascodes, active loads, and tail current sources.
- Separate likely signal, bias, and feedback paths when evidence is available.
- Export agent-friendly JSON and compact human-readable briefs.

Downstream agent workflows, demos, and evaluations can build on this CLI as a
separate project.

## CLI Usage

```bash
netlist-crawler list-subckts examples/hierarchical_ota.sp --format json
netlist-crawler summarize examples/simple_diff_pair.sp
netlist-crawler summarize examples/two_subckts.sp --topcell bias_block --format json
netlist-crawler summarize examples/hierarchical_ota.sp --topcell ota_top --expand-depth 1 --format json
netlist-crawler neighborhood examples/simple_diff_pair.sp --net vout --depth 2
netlist-crawler path examples/simple_diff_pair.sp --from vinp --to vout
netlist-crawler detect examples/simple_diff_pair.sp --pattern diff-pair
netlist-crawler explain examples/simple_diff_pair.sp --device M1
```

`summarize`, `neighborhood`, and `path` currently operate on a lightweight
SPICE-like structural parser, support `--topcell` for subcircuit selection, and
support `--expand-depth` for hierarchical instance expansion, including simple
named-port X instances. All structural commands support `--format json` for
agent use. The semantic detector and device explanation commands include
first-pass rules for differential pairs, current mirrors, tail current sources,
and active loads, with evidence and confidence fields in JSON output.

The post-layout parasitic analysis engine is also available through:

```bash
netlist-crawler scan examples/parasitics/f1_rc_ladder.flat.scs
netlist-crawler prescribe examples/parasitics/f2_diffpair_cc.flat.scs --nets nIP,nOP -o rc_model.json
netlist-crawler inject --help
```

## Roadmap

1. Harden semantic detectors beyond the first-pass rules: cascodes, active
   loads, bias trees, feedback paths, and project-specific exceptions.
2. Add LLM-oriented brief output with evidence and confidence fields.
3. Build evaluation tasks comparing LLM-only, raw-netlist, graph-tool, and
   semantic-tool workflows.
4. Expand Spectre/SPICE syntax coverage around includes, named port mapping,
   parameters, and project-specific net aliases.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
python -m pytest -q
```

The pytest suite includes structural CLI tests and the parasitic fixture matrix
ported from `analog-netlist-crawl`.

## Relationship to Workflow Repositories

Netlist Crawler is the infrastructure layer. Agent prompts, multi-step circuit
review flows, UI demos, and benchmark harnesses can live in a separate workflow
repository, for example `analog-agent-workflows`, and depend on this CLI.

The public `L-Trump/analog-design-cli` repository covers related structural
query ideas. This repository does not vendor that code in the initial import;
it keeps Netlist Crawler centered on the earlier proposal and the existing
post-layout analysis implementation.

## Origin

Netlist Crawler builds on an earlier proposal by Token Zhang on AI-assisted
analog circuit understanding. Follow-up technical discussions with collaborators
may refine specific modules such as graph-based netlist analysis, query
interfaces, agent workflows, and evaluation tasks.

## Maintainers

- Token Zhang - project lead and original proposer

## License

MIT
