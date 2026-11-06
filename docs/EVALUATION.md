# Evaluation

Every claim about quality or safety has a command that checks it and a test that fails the build if it stops being true.

``` bash
python -m zaldi evals all --write       # offline: product search + attack resistance (same numbers on every machine)
python -m zaldi evals agent --write     # live: 30 cases through a real model (needs a key and quota)
python -m zaldi evals harvest           # turn failures into new test cases
```

Results are saved to `evals/RESULTS.md` and `evals/results/latest.json`. Saving **merges**: running one suite never erases another's results.
The minimum scores live in `evals/thresholds.json`, and `tests/test_evals.py` fails CI when a change pushes search or attack
resistance below them.

## 1. Product search (offline)

134 queries generated from the catalogue itself, labelled by rule (a product is relevant when it really has the attributes the query
names): plain attributes ("red cotton kurta"), Hinglish and spelling variants ("lal sari"), and budgets ("sherwani under 8000").
Scored with hit rate, MRR, nDCG and recall at 6 for four methods, so each half of the hybrid is shown to earn its place:

| Method | What it is |
|---|---|
| keyword only | lexical scoring |
| meaning only | vector similarity |
| hybrid (RRF) | both, fused with Reciprocal Rank Fusion |
| full pipeline | extracted filters (budget, colour...) plus hybrid ranking: what a shopper really gets |

Honest limit: labels are made from the same attributes the filters read, so a near-perfect full-pipeline score shows the extractor
understands them, not that it matches shopper taste.

## 2. Attack resistance (offline)

| Layer | What is run |
|---|---|
| Hostile messages | 57 messages: instruction override, prompt extraction, jailbreak, price tricks, chat-template tokens. Each must be refused |
| Ordinary shopping | 40 messages that must **not** be refused (words like "ignore", "system", "previous order" used innocently) |
| Instructions in store data | 15 planted instructions in product or policy text must be neutralised; 7 normal texts must be left intact |
| Tool-layer attacks | 6 attacks run for real against the tools (an id that does not exist, a product never shown, 5000 units, another shopper's cart, reading it, passing a session id) |

Honest limit: the attack lists were written together with the rules, so this is a regression gate, not a claim of general robustness.

## 3. Agent with a live model

30 cases in `evals/agent_cases.jsonl`, each naming the tools the agent should use (`expect_tools`), tools it must not (`forbid_tools`),
optionally "at least one of" (`expect_any`), and a kind (search, policy, cart, memory, ask, orders, attack, scope...). Per case:

-   **tool choice correct**, and **faithful**: no amount in the reply that a tool did not return (the same check production uses);
-   attacks refused by the guardrail count as handled without calling the model;
-   latency, tokens and estimated cost.

The run uses a throwaway copy of the sample catalogue with offline embeddings, so your real data and search index are untouched. The
harness refuses to report a run where the model failed on more than a quarter of the cases, so an outage cannot produce misleading numbers.

**First live result** (`openai/gpt-oss-120b` on Groq): tool choice 100%, faithfulness 100%, 0 model errors, median 4.3 s and slowest 5%
13.7 s per chat, about $0.0006 and 3,000 tokens per chat. The first run scored 96.7%: the one miss was "find the cheapest kurta and add
it", where the agent asked which size (sensible for clothing). That case was changed to accept adding it or asking for the size and the
suite re-run, so the 100% comes from a rubric adjusted after seeing a result. It is one run of one model on cases written by the
maintainer. Latency depends on the provider's rate limits.

Run it yourself:

``` bash
LLM_PROVIDER=groq LLM_MODEL=openai/gpt-oss-120b EMBEDDING_PROVIDER=local python -m zaldi evals agent --write
```

## 4. In production

-   Every chat records latency, tokens, estimated cost (prices in `zaldi/telemetry.py`), model, prompt version and the answer-check result.
-   **Admin -> Metrics** shows speed (median, slowest 5%), cost per agent chat, tool failures, answer-check counts, and thumbs up/down by
    prompt version.
-   **Thumbs** on every answer feed `python -m zaldi evals harvest`, which collects thumbs-down and self-repaired chats, removes personal
    data, and appends them to `evals/harvested.jsonl` for review and promotion into `agent_cases.jsonl`. A real failure becomes a
    permanent regression test.
-   **Prompt experiment:** write a second wording under Content -> Assistant -> "Experiment: variant B". Half of the sessions (a stable
    split) get it; Metrics compares thumbs up by version. Leave it empty to stop the experiment.
