# Contract-Grounded Behavior Tree Synthesis: project page

Supplementary material for the paper, served with GitHub Pages from `docs/`. It is a static
page with no server-side code.

## Contents

| Path | Contents |
|---|---|
| `docs/index.html`, `docs/app.js`, `docs/styles.css` | The page. |
| `docs/data/catalog.json` | Everything the page needs on load: the contracts as served to the agent, the MCP tools, the paper's tables, the replay index and the OOC10 prompts. |
| `docs/data/batches/<cell>.json` | One file per cell (suite × model × method), loaded when the explorer opens it. Each holds run 1's trees, task specifications and evaluation rows, and each task's success count over all ten runs. |
| `docs/data/live/<key>.{mp4,json,jpg}` | Live replays: the simulator video, the per-tick status of every tree node, and a poster frame. |
| `docs/data/robot_demo.mp4` | The hardware demonstration. |
| `docs/data/experimental_data.zip` | The complete experimental data: every submitted tree and every execution result for all ten runs of every cell, with a README. Internal run bookkeeping is removed and the lab name is redacted as `[lab]` in the Panther folders. |
| `build_catalog.py` | Builds `docs/data/` from the released results, the task suites and the served contracts. |
| `tools/highlights.json` | The trees replayed for the Live Execution section. |

## Cells

A cell is one suite × model × method.

- **Suites:** `core60`, `lang50`, `hard15`, `prior30`, `panther`.
- **Models:** `sonnet` (Sonnet 5) and `gemma` (Gemma4:31b).
- **Methods:**
  - `mcore`: Full contract, 𝒞.
  - `b1`: Contract without rootstocks, 𝒞∖ℛ.
  - `obtea` / `obtea_full`: the LLM-OBTEA baseline.

Each simulation cell was run ten times. The explorer shows run 1's trees and, for each task,
how many of the ten runs succeeded.

## How the live replays are made

Each replay executes a released tree in PyRoboSim through the same code path the scoring used:

- the same in-process simulator control and GUI code path;
- 100 ms ticks at realtime factor 5;
- the suite's time budget;
- policy mode for LLM-OBTEA trees;
- the same deterministic reset layout.

The replay is then scored with the evaluation harness's own functions. It is kept only if its
execution status, goal result, success, failure category and failing node all match the
recorded run.

The trace records every node's status after every tick, in pre-order of the tree JSON. Node
`i` in a trace is `data-i="i"` in the drawn tree.

## Rebuilding

`build_catalog.py` expects the evaluation harness, the simulator, the MCP servers and the paper
sources as sibling folders. It must run in a Python environment with PyRoboSim installed, since
the world vocabulary is produced by the simulator's own code.

```bash
python build_catalog.py
python -m http.server 8000 --directory docs
```

Location names that would identify the hardware site are replaced with `[lab]` throughout the
published data.
