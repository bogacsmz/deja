# Déjà benchmark — decision arc vs single-hit recall

This measures the **exact live pipeline**: each sentence goes `judge(sentence) → query →`
`recall_arc(expand=False)` — the same front-end (the LLM trigger) and the same retrieval the
live Slack card uses. Baseline shares the judge, then takes the single top hit (no arc
synthesis). The HELD-OUT set was written after the engine froze and is not tuned against.

```
### DEV set (used while building)  (18 cases)

kind       query                                              baseline   déjà
------------------------------------------------------------------------------
recurring  should we migrate our job queue to Temporal?              ✓      ✓
recurring  is Temporal a good fit for our pipeline?                  ✗      ✓
recurring  should we adopt Datadog for monitoring?                   ✓      ✓
recurring  can we use Datadog APM?                                   ✗      ✓
recurring  should we switch to continuous deploy?                    ✓      ✓
recurring  are we doing weekly release trains or continuous d        ✓      ✓
single     should we use MongoDB as our primary datastore?           ✓      ✓
single     monorepo or polyrepo?                                     ✓      ✓
single     should we run our own Kubernetes cluster?                 ✓      ✓
single     should we move to usage-based pricing?                    ✓      ✓
single     should we build our own auth?                             ✓      ✓
single     should we standardize on MUI?                             ✓      ✓
single     should we keep the sync daily standup?                    ✓      ✓
negative   is the coffee machine on the 3rd floor working?          ok     ok
negative   tabs or spaces?                                          ok     ok
negative   what time is the lunch and learn?                        ok     ok
negative   should we migrate to CockroachDB?                        ok     ok
negative   should we rewrite everything in Rust?                    ok     ok

  recurring (correct standing decision):  baseline 4/6   Déjà 6/6
  single    (correct standing decision):  baseline 7/7   Déjà 7/7
  negatives (FALSE decisions, lower=better): baseline 0/5   Déjà 0/5

### HELD-OUT set (fresh phrasings, NOT tuned against)  (15 cases)

kind       query                                              baseline   déjà
------------------------------------------------------------------------------
recurring  did we end up adopting Temporal?                          ✗      ✓
recurring  what's our background job system now?                     ✗      ✗
recurring  are we still paying for Datadog?                          ✗      ✓
recurring  what observability stack did we land on?                  ✗      ✗
recurring  do we deploy on every merge to main?                      ✗      ✓
recurring  did we get rid of the weekly release trains?              ✓      ✓
single     Postgres or Mongo for the core datastore?                 ✗      ✓
single     do we self-host our container platform?                   ✓      ✓
single     did we build or buy authentication?                       ✓      ✓
single     what did we pick for styling the UI?                      ✗      ✗
single     is our daily standup a meeting or async?                  ✓      ✓
negative   anyone looking at the flaky checkout test?            FALSE     ok
negative   should we adopt GraphQL for the API?                     ok     ok
negative   are we moving to Kafka for events?                       ok     ok
negative   who's on call this weekend?                              ok     ok

  recurring (correct standing decision):  baseline 1/6   Déjà 4/6
  single    (correct standing decision):  baseline 3/5   Déjà 4/5
  negatives (FALSE decisions, lower=better): baseline 1/4   Déjà 0/4
```

## Reading it
- **Recurring arcs** are where Déjà wins: the standing decision lives in a different thread
  than the top hit, so single-hit recall surfaces the *proposal*, not the *decision*. Déjà
  re-recalls the query's distinctive terms, gathers the topic's cluster, and reports the
  standing decision.
- **Single decisions** are a control — both do well; the arc degrades to the single thread.
- **Negatives**: the judge gates noise/logistics for BOTH (so DEV false-decisions are 0/0 —
  that's the judge, not the arc). On a decision-shaped never-discussed query, single-hit can
  drift onto an unrelated decision; Déjà's subject guard + INCONCLUSIVE keep it at 0.

## How it's run (honest — we surface this, we don't hide it)
- Runs the REAL engine end-to-end, including the LLM judge (cached to disk for reproducible
  runs). Only the retrieval *source* is a local mirror of the workspace, not live RTS —
  because Slack's `assistant.search.context` is rate-limited to ~1 call every few minutes
  (measured `Retry-After: 288s`), which cannot serve a 100+-query benchmark.
- The mirror ranks threads by IDF-weighted overlap with each thread's PARENT text (RTS
  matches parents, not replies). It is **calibrated to live**: sentences that fail live
  (e.g. the judge emits 'continuous deployment', which RTS misses) also route through the
  same lexical expansion here, and were verified to render the same result live.

## Limits (honest)
- Small, seeded workspace (synthetic team memory), not a large real org.
- The live card path is **lexical-only** (fast, no LLM in the hot path, light on rate-limited
  RTS). So the held-out semantic-gap cases ('observability stack' → the *Datadog* decision;
  'background job system' → the *Temporal* decision) MISS — bridging them needs the LLM query
  expansion, which is available but OFF on the live card path. This is why held-out recurring
  is 4/6, not higher: an honest cost of keeping the live card fast, not a hidden failure.
- The local mirror is lexical (IDF), not semantic like RTS; it approximates, not equals it.
- Correctness is substring-based against hand-labelled expected decisions.
- 18 DEV + 15 held-out cases; expand the lists in benchmarks/run.py.
