from omnidoc_worker.schemas import DocumentInsight
from omnidoc_worker.summarizer import (
    DocumentSummarizer,
    chunk_text,
    parse_key_information,
    unique_facts,
)


def test_chunk_text_splits_on_a_word_boundary():
    text = "alpha beta gamma delta"
    chunks = chunk_text(text, 12)
    assert chunks[0] == "alpha beta"
    assert all(len(chunk) <= 12 for chunk in chunks)
    assert " ".join(chunks) == text


def test_parse_key_information_keeps_one_fact_per_line():
    raw = "- Vendor: ACME Supplies\n2. Amount: $250.00\n\nList the key facts from this document."
    assert parse_key_information(raw) == ["Vendor: ACME Supplies", "Amount: $250.00"]


def test_unique_facts_drops_case_duplicates():
    assert unique_facts(["Due: January 12", "due: january 12", "Payee: Jane Miller"]) == [
        "Due: January 12",
        "Payee: Jane Miller",
    ]


def test_analyze_combines_chunk_summaries_and_facts():
    calls = []

    def generate(prompt: str, max_new_tokens: int) -> str:
        calls.append(prompt)
        if prompt.startswith("summarize:"):
            return "ACME billed Jane Miller $250 due January 12, 2024."
        return "Vendor: ACME Supplies\nAmount: $250.00\nDue: January 12, 2024"

    summarizer = DocumentSummarizer.__new__(DocumentSummarizer)
    summarizer.model_name = "fake"
    summarizer._generate = generate
    insight = summarizer.analyze("Invoice from ACME Supplies to Jane Miller for $250.00 due January 12, 2024.")

    assert any("4 to 6 sentences" in prompt for prompt in calls)
    assert isinstance(insight, DocumentInsight)
    assert "ACME" in insight.summary
    assert insight.key_information == [
        "Vendor: ACME Supplies",
        "Amount: $250.00",
        "Due: January 12, 2024",
    ]
    assert calls


def test_empty_text_returns_an_explicit_summary():
    summarizer = DocumentSummarizer.__new__(DocumentSummarizer)
    summarizer.model_name = "fake"
    summarizer._generate = lambda prompt, max_new_tokens: (_ for _ in ()).throw(AssertionError("model should not run"))
    insight = summarizer.analyze("   \n  ")
    assert insight.summary == "The document contains no readable text."
    assert insight.key_information == ["No readable text was found."]
