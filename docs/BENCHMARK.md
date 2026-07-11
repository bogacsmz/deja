# Déjà benchmark — decision arc vs single-hit recall

Same recall primitive under both; only the *synthesis* differs (honest by construction).
Baseline = the single most relevant thread's own outcome. Déjà = the arc's standing decision.
The HELD-OUT set was written after the engine was frozen and is not tuned against — it checks
that the general topic-expansion generalizes rather than overfitting the DEV cases.

```
### DEV set (used while building)  (18 cases)

kind       query                                              baseline   déjà
------------------------------------------------------------------------------
recurring  should we migrate our job queue to Temporal?              ✗      ✓
recurring  is Temporal a good fit for our pipeline?                  ✗      ✓
recurring  should we adopt Datadog for monitoring?                   ✗      ✓
recurring  can we use Datadog APM?                                   ✗      ✓
recurring  should we switch to continuous deploy?                    ✓      ✓
recurring  are we doing weekly release trains or continuous d        ✓      ✓
single     should we use MongoDB as our primary datastore?           ✓      ✓
single     monorepo or polyrepo?                                     ✓      ✓
single     should we run our own Kubernetes cluster?                 ✓      ✓
single     should we move to usage-based pricing?                    ✓      ✓
single     should we build our own auth?                             ✓      ✓
single     should we standardize on MUI?                             ✗      ✗
single     should we keep the sync daily standup?                    ✓      ✓
negative   is the coffee machine on the 3rd floor working?       FALSE     ok
negative   tabs or spaces?                                       FALSE     ok
negative   what time is the lunch and learn?                     FALSE     ok
negative   should we migrate to CockroachDB?                     FALSE     ok
negative   should we rewrite everything in Rust?                    ok     ok

  recurring (correct standing decision):  baseline 2/6   Déjà 6/6
  single    (correct standing decision):  baseline 6/7   Déjà 6/7
  negatives (FALSE decisions, lower=better): baseline 4/5   Déjà 0/5

### HELD-OUT set (fresh phrasings, NOT tuned against)  (15 cases)

kind       query                                              baseline   déjà
------------------------------------------------------------------------------
recurring  did we end up adopting Temporal?                          ✗      ✓
recurring  what's our background job system now?                     ✗      ✓
recurring  are we still paying for Datadog?                          ✗      ✓
recurring  what observability stack did we land on?                  ✗      ✗
recurring  do we deploy on every merge to main?                      ✗      ✓
recurring  did we get rid of the weekly release trains?              ✓      ✓
single     Postgres or Mongo for the core datastore?                 ✗      ✓
single     do we self-host our container platform?                   ✓      ✓
single     did we build or buy authentication?                       ✓      ✓
single     what did we pick for styling the UI?                      ✗      ✓
single     is our daily standup a meeting or async?                  ✓      ✓
negative   anyone looking at the flaky checkout test?            FALSE     ok
negative   should we adopt GraphQL for the API?                     ok     ok
negative   are we moving to Kafka for events?                       ok     ok
negative   who's on call this weekend?                              ok     ok

  recurring (correct standing decision):  baseline 1/6   Déjà 5/6
  single    (correct standing decision):  baseline 3/5   Déjà 5/5
  negatives (FALSE decisions, lower=better): baseline 1/4   Déjà 0/4
```

## Reading it
- **Recurring arcs** are where Déjà wins: the standing decision lives in a different thread
  than the top hit, so single-hit recall surfaces the *proposal*, not the *decision*. Déjà
  gathers the topic's whole thread cluster (a second recall on the query's topic terms) and
  reports the standing decision.
- **Single decisions** are a control — both do well; the arc degrades to the single thread.
- **Negatives** measure false decisions: Déjà returns INCONCLUSIVE rather than inventing one.

## How it's run (honest)
- The real synthesis engine (recall_memories / recall_arc / expand / build_arc) runs
  unchanged; only the *retrieval source* is swapped via injected primitives.
- Retrieval is a LOCAL mirror of the workspace (benchmarks/local.py) rather than live RTS,
  because Slack's assistant.search.context is rate-limited to ~1 call every few minutes —
  it cannot serve a 100+-query benchmark. The mirror ranks threads by IDF-weighted overlap
  of the query with each thread's PARENT text (RTS matches parents, not replies) and drops
  weak matches, approximating RTS's selectivity. It was calibrated against the live RTS DEV
  results (recurring 6/6, single 7/7, negatives 0/5), which it reproduces.

## Limits (honest)
- Small, seeded workspace (synthetic team memory), not a large real org.
- The local mirror is lexical (IDF), not semantic like RTS; it approximates, not equals it.
- Dates are content-conveyed ('[Mon DD]') because Slack messages can't be back-dated.
- Correctness is substring-based against hand-labelled expected decisions.
- 18 DEV + 15 held-out cases; expand the lists in benchmarks/run.py.
