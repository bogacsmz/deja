"""Hermetic tests for LLM query-expansion helpers (deja.expand) + the subject guard — no LLM/Slack."""

from deja.arc import _query_subjects
from deja.expand import _parse, keep_specific


def test_parse_extracts_terms():
    assert _parse('{"terms": ["Datadog", "Grafana", "monitoring"]}') == [
        "Datadog",
        "Grafana",
        "monitoring",
    ]


def test_parse_bad_json_is_empty():
    assert _parse("sorry, I cannot") == []
    assert _parse('{"terms": "not-a-list"}') == []
    assert _parse('{"terms": []}') == []  # non-decision question → no expansion


def test_keep_specific_drops_generic_connectors():
    # lone generic words drift topics ("queue" -> Temporal, "CI" -> deploy) → dropped
    out = keep_specific(["Kafka", "queue", "events", "event streaming", "API"])
    assert "Kafka" in out and "event streaming" in out  # specific / multi-word kept
    assert "queue" not in out and "events" not in out and "API" not in out


def test_keep_specific_dedupes_case_insensitive():
    assert keep_specific(["Datadog", "datadog", "Grafana"]) == ["Datadog", "Grafana"]


def test_query_subjects_finds_product_names():
    assert _query_subjects("should we migrate to Temporal?") == ["Temporal"]
    assert _query_subjects("Postgres or Mongo for the datastore?") == [
        "Postgres",
        "Mongo",
    ]
    # sentence-initial stopword is not a subject; descriptive queries have none
    assert _query_subjects("What observability stack did we land on?") == []
