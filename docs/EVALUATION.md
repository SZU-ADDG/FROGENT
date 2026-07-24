# Agent Evaluation

Evaluation answers one question: does a change improve FROGENT's retrieval, Deep Research, memory,
qualitative judgment or tool use?

## Active assets

- `evaluation/cases/research-eval-v1.*`: deterministic evidence-pipeline integrity fixture;
- `evaluation/cases/qualitative-judgment-v1.*`: knowledge-led prioritization cases;
- `evaluation/benchmarks/data/capability-52.exposed.json`: exposed PubMedQA, BioASQ and
  LongMemEval capability pack;
- `evaluation/benchmarks/`: preparation, incremental execution and scoring code.

The repository keeps one active generation for each purpose. Previous experiments remain
recoverable through Git.

## Acceptance signals

- task success and useful answer quality;
- retrieval hit quality, canonical identity and source coverage;
- citation correctness and locator completeness;
- counterevidence retention;
- evidence admission, memory retention and revocation;
- recovery from provider, Reader, model and persistence failures;
- tool input lineage and output binding;
- latency, concurrency and cost when measured.

Metrics without a reliable oracle use `not_measured`. Static tests demonstrate contract integrity;
real cases establish behavior.

## Current benchmark use

The exposed 52-case pack contains PubMedQA, BioASQ and LongMemEval cases. It supports regression
diagnosis and workflow improvement. It does not provide a hidden-held-out claim because cases and
oracles are visible in the repository.

Run the complete current verification:

```bash
runtime/app/venv/bin/python scripts/check.py
```

Run the incremental capability benchmark:

```bash
runtime/app/venv/bin/python scripts/run_agent_capability_benchmark.py run \
  --pack evaluation/benchmarks/data/capability-52.exposed.json \
  --factory frogent \
  --output runtime/evaluation/capability-52.results.jsonl
```

## Evaluation loop

1. Complete one coherent Agent capability block.
2. Run focused contract tests.
3. Run a small real or public-data effect panel.
4. Analyze individual failures and false confidence.
5. Change Agent policy, prompt, retrieval, memory or tool routing.
6. Run the same panel again and record the behavior change.
7. Run the full regression suite before commit.

Skill ablations are reserved for stable workflows where attribution changes a development decision.
