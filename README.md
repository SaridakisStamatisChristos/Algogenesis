# AlgoGenesis

Research laboratory for finite-domain program synthesis and algorithm discovery.

## Current GitHub import

The initial repository import contains the v0.6 **dynamic-loop synthesizer** (`dynamic_synthesis.py`) and its dependency, the bounded register-machine interpreter (`control_flow.py`). The remainder of the v0.6 research snapshot is not yet imported. This is a partial import, not a complete source migration.

## Run

Python 3.10+ is required. From the repository root:

```bash
python dynamic_synthesis.py
python -m unittest discover -s tests -v
```

## Correctness scope

Synthesis verifies candidate programs only on the supplied finite input domain. No general/unbounded proof, SOTA claim, or production-readiness claim is made.
