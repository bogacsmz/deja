# Déjà benchmark — decision arc vs single-hit recall

Same recall primitive under both; only the synthesis differs (honest by construction).
Baseline = the single most relevant thread's own outcome. Déjà = the arc's standing decision.

```

kind       query                                                baseline   déjà
--------------------------------------------------------------------------------
recurring  should we migrate our job queue to Temporal?                ✗      ✓
recurring  is Temporal a good fit for our pipeline?                    ✗      ✗
recurring  should we adopt Datadog for monitoring?                     ✗      ✓
recurring  can we use Datadog APM?                                     ✗      ✗
recurring  should we switch to continuous deploy?                      ✗      ✓
recurring  are we doing weekly release trains or continuous dep        ✓      ✓
single     should we use MongoDB as our primary datastore?             ✓      ✓
single     monorepo or polyrepo?                                       ✓      ✓
single     should we run our own Kubernetes cluster?                   ✓      ✓
single     should we move to usage-based pricing?                      ✓      ✓
single     should we build our own auth?                               ✓      ✓
single     should we standardize on MUI?                               ✓      ✓
single     should we keep the sync daily standup?                      ✓      ✓
negative   is the coffee machine on the 3rd floor working?         FALSE     ok
negative   tabs or spaces?                                         FALSE     ok
negative   what time is the lunch and learn?                       FALSE     ok
negative   should we migrate to CockroachDB?                          ok     ok
negative   should we rewrite everything in Rust?                      ok     ok

SCORES (correct standing decision):
  recurring arcs:  baseline 1/6   Déjà 4/6
  single decisions:baseline 7/7   Déjà 7/7
FALSE DECISIONS on negatives (lower is better):
  negatives:       baseline 3/5   Déjà 0/5
```

## Reading it
- **Recurring arcs** are where Déjà wins: the standing decision lives in a different thread
  than the top hit, so single-hit recall surfaces the *proposal*, not the *decision*.
- **Single decisions** are a control — both do well; the arc degrades to the single thread.
- **Negatives** measure false decisions: Déjà returns INCONCLUSIVE rather than inventing one.

## Limits (honest)
- Small, seeded workspace (synthetic team memory), not a large real org.
- Dates are content-conveyed ('[Mon DD]') because Slack messages can't be back-dated.
- RTS matches on a thread's parent text; an arc whose threads don't share topic keywords
  in their parents may be under-retrieved. The seed is written with that in mind.
- Correctness is substring-based against hand-labelled expected decisions.
- 18 cases; expand `CASES` in benchmarks/run.py to grow it.
