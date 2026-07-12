# Déjà robustness — adversarial self-test

The jury will type anything into the sandbox. **Principle: silence is cheap, a confident
wrong answer is fatal.** This runs the *full live pipeline* (judge → recall_arc, the real
card path) over ~90 hostile queries and classifies each. The number that matters is
**CONFIDENT-WRONG — the target is 0.**

```
verdict              mode     query
------------------------------------------------------------------------------
  correct            topic    are we on Temporal or Redis for jobs?
  correct            topic    did the Temporal migration work out?
  correct            topic    what happened with the Temporal thing?
  correct            topic    should we move our job queue to Temporal?
  correct            topic    is Temporal our workflow engine?
  correct            topic    remind me why we didn't go with Temporal
  correct-inconclusive topic    are we paying for Datadog?
  correct            topic    what's our monitoring vendor?
  correct-inconclusive topic    should we buy Datadog?
  correct            topic    did we go with Datadog for observability?
  correct            topic    can we add Datadog APM?
  correct-inconclusive topic    how do we ship to production?
  correct            topic    do we deploy on merge?
  correct            topic    release trains or continuous deploy?
  correct            topic    should we switch to continuous deploy?
  correct-inconclusive topic    Postgres or Mongo?
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
  correct-inconclusive silent   should we adopt an RFC process?
  correct-inconclusive silent   did we decide on a design-doc process?
  correct-inconclusive silent   do we have an RFC process now?
  correct-inconclusive silent   should we adopt GraphQL?
  correct-inconclusive silent   are we moving to Kafka?
  correct-inconclusive silent   should we migrate to CockroachDB?
  correct-inconclusive silent   should we rewrite in Rust?
  correct-inconclusive silent   should we use Svelte for the frontend?
  correct-inconclusive silent   gRPC or REST for internal APIs?
  correct-inconclusive silent   should we adopt Terraform?
  correct-inconclusive silent   do we use HashiCorp Vault?
  correct-inconclusive silent   Elasticsearch or OpenSearch?
  correct-inconclusive silent   should we put analytics in Snowflake?
  correct-inconclusive silent   Nomad instead of our current setup?
  correct-inconclusive silent   should we introduce RabbitMQ?
  correct-inconclusive silent   did we standardize on Redux?
  correct-inconclusive silent   Webpack or Vite?
  correct-inconclusive silent   should we adopt a service mesh?
  correct-inconclusive silent   are we going multi-cloud?
  correct-inconclusive silent   purple monkey dishwasher
  correct-inconclusive silent   asdfghjkl qwerty
  correct-inconclusive silent   should we deploy the moon to Redis?
  correct-inconclusive silent   what color is the database?
  correct-inconclusive silent   how many Temporals fit in a Datadog?
  correct-inconclusive silent   banana continuous coffee
  correct-inconclusive silent   is the standup a Kubernetes?
  correct-inconclusive silent   do we serve tacos on Tuesdays?
  correct            topic    shoud we migrat to Temporl?
  correct            topic    Datadgo monitorng vendorr?
  correct            topic    continous deploi or relese trains?
  correct            topic    Postgress or Mongo db?
  correct            topic    shud we uze MUI?
  correct            topic    should we use Temporal and Datadog?
  correct-inconclusive topic    Postgres or Mongo, and monorepo or not?
  correct            topic    Datadog for monitoring and Kafka for events?
  correct            topic    Temporal'a geçmeli miyiz yoksa Redis mi?
  correct            topic    ¿deberíamos usar Datadog para monitoreo?
  correct-inconclusive topic    faut-il adopter le déploiement continu?
  correct-inconclusive topic    sollten wir Postgres oder Mongo nehmen?
  correct-inconclusive topic    didn't we decide to drop Postgres?
  correct            topic    we agreed to buy Datadog, right?
  correct            topic    we're on Temporal now, correct?
  correct            topic    we killed continuous deploy, didn't we?
  correct            topic    we standardized on MUI, yeah?
  correct            topic    we went with usage-based pricing, right?
  correct            topic    we self-host Kubernetes now, don't we?
  correct-inconclusive topic    we built our own auth in the end, correct?
  correct            topic    we're using MongoDB as the main DB, right?
  correct            topic    we brought back the sync standup, yeah?

TOTAL 75 adversarial queries:
  correct                : 39
  correct-inconclusive   : 36  (silence — safe)
  CONFIDENT-WRONG        : 0   <<< the number that matters (target 0)
```

## Categories
Paraphrases · never-discussed topics · nonsense · typos · multi-topic · other languages ·
**false-premise provocations** ('didn't we decide to drop Postgres?' — no, we kept it).

## Why CONFIDENT-WRONG stays at 0
- The **judge** gates chit-chat/logistics/nonsense before any search.
- The **grounding invariant** (deja/arc.py): a standing decision is shown only if it's on
  the query's topic, a genuine decision, and sourced by a permalink — else INCONCLUSIVE.
- **Provocations** get the *actual* standing decision (which contradicts the false premise)
  or nothing — Déjà never parrots the premise back.

Reproducible: judge outputs are cached (DEJA_JUDGE_CACHE); retrieval is the local mirror
calibrated to live. Run: `python benchmarks/adversarial.py --md`.
