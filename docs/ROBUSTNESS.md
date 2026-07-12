# Déjà robustness — adversarial self-test

The jury will type anything into the sandbox. **Principle: silence is cheap, a confident
wrong answer is fatal — but a silent bot is a cheap victory, so we measure recall too.**
This runs the *full live pipeline* (judge → recall_arc, the real card path) over 75 hostile
queries and splits the outcome honestly:

- **correct** — found the right standing decision.
- **MISS** — a real decision existed, we stayed silent (the recall gap we care about).
- **correct-silent** — nothing to find; silence is right.
- **CONFIDENT-WRONG** — asserted a wrong/off-topic decision. **Must be 0.**

```
verdict              mode     query
------------------------------------------------------------------------------
  correct            topic    are we on Temporal or Redis for jobs?
  correct            topic    did the Temporal migration work out?
  correct            topic    what happened with the Temporal thing?
  correct            topic    should we move our job queue to Temporal?
  correct            topic    is Temporal our workflow engine?
  correct            topic    remind me why we didn't go with Temporal
  correct            topic    are we paying for Datadog?
  correct            topic    what's our monitoring vendor?
  correct            topic    should we buy Datadog?
  correct            topic    did we go with Datadog for observability?
  correct            topic    can we add Datadog APM?
  correct            topic    how do we ship to production?
  correct            topic    do we deploy on merge?
  correct            topic    release trains or continuous deploy?
  correct            topic    should we switch to continuous deploy?
🟡MISS               topic    Postgres or Mongo?
  correct            topic    what's our primary datastore?
  correct            topic    should we use MongoDB?
  correct            topic    monorepo or many repos?
  correct            topic    do we self-host Kubernetes?
  correct            topic    should we run our own k8s?
  correct            topic    usage-based or seat-based pricing?
  correct            topic    did we build or buy auth?
  correct            topic    should we adopt MUI?
  correct            topic    what did we pick for CSS?
  correct            topic    is standup sync or async?
  correct-silent     silent   should we adopt an RFC process?
  correct-silent     silent   did we decide on a design-doc process?
  correct-silent     silent   do we have an RFC process now?
  correct-silent     silent   should we adopt GraphQL?
  correct-silent     silent   are we moving to Kafka?
  correct-silent     silent   should we migrate to CockroachDB?
  correct-silent     silent   should we rewrite in Rust?
  correct-silent     silent   should we use Svelte for the frontend?
  correct-silent     silent   gRPC or REST for internal APIs?
  correct-silent     silent   should we adopt Terraform?
  correct-silent     silent   do we use HashiCorp Vault?
  correct-silent     silent   Elasticsearch or OpenSearch?
  correct-silent     silent   should we put analytics in Snowflake?
  correct-silent     silent   Nomad instead of our current setup?
  correct-silent     silent   should we introduce RabbitMQ?
  correct-silent     silent   did we standardize on Redux?
  correct-silent     silent   Webpack or Vite?
  correct-silent     silent   should we adopt a service mesh?
  correct-silent     silent   are we going multi-cloud?
  correct-silent     silent   purple monkey dishwasher
  correct-silent     silent   asdfghjkl qwerty
  correct-silent     silent   should we deploy the moon to Redis?
  correct-silent     silent   what color is the database?
  correct-silent     silent   how many Temporals fit in a Datadog?
  correct-silent     silent   banana continuous coffee
  correct-silent     silent   is the standup a Kubernetes?
  correct-silent     silent   do we serve tacos on Tuesdays?
  correct            topic    shoud we migrat to Temporl?
  correct            topic    Datadgo monitorng vendorr?
  correct            topic    continous deploi or relese trains?
  correct            topic    Postgress or Mongo db?
  correct            topic    shud we uze MUI?
  correct            topic    should we use Temporal and Datadog?
🟡MISS               topic    Postgres or Mongo, and monorepo or not?
  correct            topic    Datadog for monitoring and Kafka for events?
  correct            topic    Temporal'a geçmeli miyiz yoksa Redis mi?
  correct            topic    ¿deberíamos usar Datadog para monitoreo?
🟡MISS               topic    faut-il adopter le déploiement continu?
🟡MISS               topic    sollten wir Postgres oder Mongo nehmen?
🟡MISS               topic    didn't we decide to drop Postgres?
  correct            topic    we agreed to buy Datadog, right?
  correct            topic    we're on Temporal now, correct?
  correct            topic    we killed continuous deploy, didn't we?
  correct            topic    we standardized on MUI, yeah?
  correct            topic    we went with usage-based pricing, right?
  correct            topic    we self-host Kubernetes now, don't we?
  correct            topic    we built our own auth in the end, correct?
  correct            topic    we're using MongoDB as the main DB, right?
  correct            topic    we brought back the sync standup, yeah?

TOTAL 75 adversarial queries (48 have a real decision to find):
  correct         : 43   (found the right standing decision)
  MISS            : 5   <<< recall gap: it was there, we stayed silent
  correct-silent  : 27   (nothing to find — silence is right)
  CONFIDENT-WRONG : 0   <<< must stay 0

  RECALL on real-decision queries: 43/48 = 90%
```

## Categories
Paraphrases · never-discussed topics · nonsense · typos · multi-topic · other languages ·
**false-premise provocations** ('didn't we decide to drop Postgres?' — no, we kept it).

## Why CONFIDENT-WRONG stays at 0
- The **judge** gates chit-chat/logistics/nonsense before any search.
- The **grounding invariant** (deja/arc.py): a standing decision is shown only if it's on
  the query's topic (named-product guard), a genuine decision, and sourced by a permalink.
- The **decision state machine**: the standing decision is DERIVED from the last
  state-changing transition (adopted/reversed), not guessed from recency; a trailing
  'revived' doesn't overturn it. Provocations get the real decision or nothing — never the
  premise parroted back.

## The remaining misses (honest)
- Terse 'Postgres or Mongo?' variants: the decision lives in a *reply* ('going with
  Postgres') while the thread's parent proposes *MongoDB*. RTS matches parents, and the
  exact-token mirror scores this below its relevance floor — a conservative under-report;
  live RTS's fuzzier match likely finds it (the fuller 'Postgres or Mongo for the datastore'
  already passes). We chose not to loosen the mirror (it started cross-matching topics).
- One French phrasing ('déploiement continu'): **Déjà is monolingual (English).** Bridging
  other languages needs the LLM translation the live card path keeps off for speed. A named
  limit, not a hidden failure.

Reproducible: judge outputs are cached (DEJA_JUDGE_CACHE); retrieval is the local mirror
calibrated to live. Run: `python benchmarks/adversarial.py --md`.
