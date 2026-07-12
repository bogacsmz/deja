# Déjà governance benchmark

Does the guardrail brake the right proposals — and never fabricate one? Labelled proposals
run through the SAME live path (`judge → check_decision`, same grounding gate + thresholds
as the card). No tuning; run once.

```
  got          expected      proposal
--------------------------------------------------------------------------------------------
  CONFLICTS    CONFLICTS     Opening a PR to migrate the job queue to Tem
  CONFLICTS    CONFLICTS     Let's switch our monitoring over to Datadog.
  CONFLICTS    CONFLICTS     We should move pricing to pure usage-based b
🟡ALLOW        CONFLICTS     Proposing we standardize the datastore on Mo
🟡ALLOW        CONFLICTS     Let's self-host our own Kubernetes cluster.
  CONFLICTS    CONFLICTS     We should build our own auth in-house.
  CONFLICTS    CONFLICTS     Let's standardize the UI on MUI as our compo
🟡ALLOW        CONFLICTS     Proposing a public GA launch this quarter.
  ALLOW        ALLOW         Proposing we add a usage add-on for heavy ac
  ALLOW        ALLOW         Let's keep the job queue on Redis.
  ALLOW        ALLOW         We'll use Postgres as the primary datastore.
  ALLOW        ALLOW         Let's keep shipping continuous deploy on mer
  ALLOW        ALLOW         Standardize styling on Tailwind and Radix.
  ALLOW        ALLOW         Use managed ECS Fargate for the new services
  ALLOW        ALLOW         Should we adopt GraphQL for the public API?
  ALLOW        ALLOW         Let's migrate our event bus to Kafka.
  ALLOW        ALLOW         Proposing we rewrite the billing service in 
  ALLOW        ALLOW         Should we adopt Terraform for infrastructure
  ALLOW        ALLOW         Did we decide to buy a boat for the offsite?
  ALLOW        ALLOW         Are we migrating the office to Mars?
  ALLOW        ALLOW         Should we drop the ball on the holiday party
  ALLOW        ALLOW         anyone up for coffee before standup?
  ALLOW        ALLOW         let's grab lunch after the deploy
  ALLOW        ALLOW         who's migrating to the new office?
  ALLOW        ALLOW         should we roll back the party plan?
  INCONCLUSIVE INCONCLUSIVE  Should we adopt an RFC process for big decis
  INCONCLUSIVE INCONCLUSIVE  Can we introduce a design-doc process for ma

CONFLICTS: precision 100% · recall 62%  (tp 5 · fp 0 · fn 3)
🔴 FALSE CONFLICTS (paralysing false alarm): 0
🟡 FALSE ALLOW (missed brake): 3
INCONCLUSIVE returned: 2
🔴 SOURCELESS VERDICT (must be 0): 0

OWNER ATTRIBUTION: right 11 · wrong 0 · wrongly-empty 0   (of 11 sourced decisions)
```

## What the numbers mean
- **FALSE CONFLICTS** is the most expensive error — a false alarm paralyses the team. This
  is the number we most want at 0.
- **FALSE ALLOW** is a missed conflict (the brake didn't fire) — honest recall cost.
- **SOURCELESS VERDICT** must be 0: every CONFLICTS/INCONCLUSIVE is backed by clickable
  sources; a conflict we can't link downgrades to INCONCLUSIVE. A fabricated brake is worse
  than no brake.
- **OWNER ATTRIBUTION** — we print '@X made the call' on the card, so we measure it. If the
  wrong rate is not ~0, the honest fix is a threshold: show no owner rather than the wrong
  one (pointing at the wrong person is worse than pointing at no one).

The retrieval engine is unchanged from the live benchmark; this measures the governance
verdict on top of it. Lexical traps ('buy a boat', 'migrate to Mars') check that a shared
word never triggers a brake on an unrelated topic.

## The findings (honest — run once, no tuning)
- **FALSE CONFLICTS = 0, SOURCELESS = 0.** The two errors that would disqualify a guardrail
  never happened: not one false alarm, not one unsourced verdict. Every trap correctly
  ALLOWs — including the hardest class, non-proposal chit-chat whose keyword IS a real
  decision subject ('anyone up for coffee before **standup**?', 'let's grab lunch after the
  **deploy**'). One of these braked live once; the fix makes the agent path use the SAME
  should_recall gate as the human path (an agent verdict is never more permissive than the
  card), so word overlap alone can no longer raise a brake.
- **Owner attribution measured for the first time: 11/11 right, 0 wrong.** We print '@X made
  the call' on the card and had never verified it — turns out the arc's decider matches the
  ground-truth owner every time here, so no threshold is needed (we kept the measurement so
  a future regression would show up).
- **Recall 62% — the 3 missed brakes are all one honest class:** the standing decision is a
  positive adoption that names the rejected alternative WITHOUT a rejection cue the engine
  reads ('going with Postgres, not Mongo'; 'managed Fargate, not self-hosted k8s'; 'staying
  in private beta'). We deliberately do NOT chase this recall by loosening the conflict test
  — that would trade away the precision/false-alarm guarantee. We'd rather miss a brake than
  raise a false one.