# Déjà external validation — real, publicly documented decisions

**This validates decision-arc reasoning on real, publicly documented decision histories we
did not author. It does not test Slack retrieval — that is covered by the live workspace
benchmark.**

Eight famous open-source decisions, each with ≥3 discussion moments across months/years, at
least one reversal or reopen, and a public standing decision (the URL is the ground truth —
not our interpretation). Run through the SAME live pipeline (`judge → recall_arc`, same
grounding gate, same IDF + relevance-floor thresholds as the live benchmark — never more
permissive). No tuning; run once.

```
verdict           topic                                  query
------------------------------------------------------------------------------------------------
  correct         JS pipeline operator (F# vs Hack)     should the JavaScript pipeline operator use 
🟡MISS            Rust async/await syntax (prefix vs p  is await prefix or postfix syntax in Rust?
  correct         Kubernetes dockershim removal         are we removing dockershim from Kubernetes?
  correct         CPython removing the GIL (PEP 703)    can we make the GIL optional in CPython?
🟡MISS            JS decorators design (static vs plai  should JavaScript decorators use the static 
  correct         Vue function-based vs Composition AP  is the function-based component API replacin
  correct         TypeScript legacy vs standard decora  should we keep using experimental legacy dec
  correct         SharedArrayBuffer after Spectre       can we use SharedArrayBuffer enabled by defa
  correct-silent  (never decided here)                  should JavaScript add operator overloading?
  correct-silent  (never decided here)                  are we adding a built-in datetime type to th
  correct-silent  (never decided here)                  should Python switch to curly-brace blocks i
🔴CONFIDENT-WRONG (never decided here)                  should Kubernetes replace YAML manifests wit

REAL-decision recall: 6/8   ·   MISS 2   ·   negatives silent 3/4   ·   CONFIDENT-WRONG 1
```

## The cases (ground truth = the linked source)
- **JS pipeline operator (F# vs Hack)** — https://github.com/tc39/proposal-pipeline-operator
- **Rust async/await syntax (prefix vs postfix)** — https://boats.gitlab.io/blog/post/await-decision/
- **Kubernetes dockershim removal** — https://kubernetes.io/blog/2022/01/07/kubernetes-is-moving-on-from-dockershim/
- **CPython removing the GIL (PEP 703)** — https://peps.python.org/pep-0703/
- **JS decorators design (static vs plain)** — https://github.com/tc39/proposal-decorators
- **Vue function-based vs Composition API** — https://github.com/vuejs/rfcs/pull/78
- **TypeScript legacy vs standard decorators** — https://devblogs.microsoft.com/typescript/announcing-typescript-5-0/
- **SharedArrayBuffer after Spectre** — https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer

## What this does and does not claim
- **Does** show the arc engine reconstructs a standing decision from real, multi-author,
  reversal-laden histories it never saw during development: **6/8 real decisions** (pipeline
  operator → Hack pipes, dockershim → removed, GIL → PEP 703 accepted, Vue → additive Composition
  API, TypeScript → standard decorators, SharedArrayBuffer → cross-origin isolation).
- **Does not** measure Slack Real-Time Search — the live workspace benchmark covers that.

## The findings (honest — this set exists to expose gaps, and it did)
- **2 misses, both at the front-of-pipeline, not fabrication:**
  - *Rust async/await* — the **judge declined** "is await prefix or postfix syntax in Rust?": it
    reads as a factual how-question, not a "what did we decide" recall, so Déjà stayed silent.
  - *JS decorators* — the **named-subject guard**: the judge extracted "JavaScript" as the subject,
    but the real threads say "decorators/static", never the word "javascript", so they were filtered
    out and Déjà stayed silent. Honest silence, never a guess.
- 🔴 **1 CONFIDENT-WRONG — the real catch:** "should Kubernetes replace YAML manifests with JSON?"
  (never decided here) returned the **dockershim** decision. The grounding gate passed on the *broad
  shared subject* "Kubernetes" while the query's specific topic (YAML/JSON manifests) is absent from
  the arc. **The live adversarial set (0 confident-wrong) never covered this "same broad subject,
  different specific topic" class — this external set does.** Candidate general fix: require the
  query's *non-subject* distinctive terms (or the standing decision itself) to overlap, so a shared
  product/subject name alone can't ground an off-topic decision. Reported, **not** applied here — per
  the rule for this set: no tuning, run once, report whatever comes out.