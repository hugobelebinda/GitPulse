"""Topic matching tests."""

from gitpulse.topics import TOPICS, match_topic_slugs


def test_fifty_topics() -> None:
    assert len(TOPICS) == 50
    assert len({t.slug for t in TOPICS}) == 50


def test_seed_repo_match() -> None:
    assert "python" in match_topic_slugs("python/cpython")
    assert "llm" in match_topic_slugs("ollama/ollama")


def test_keyword_match() -> None:
    assert "kubernetes" in match_topic_slugs("acme/kubernetes-operator")
    assert "docker" in match_topic_slugs("acme/docker-compose-helper")


def test_empty_repo() -> None:
    assert match_topic_slugs("") == []
    assert match_topic_slugs(None) == []  # type: ignore[arg-type]
