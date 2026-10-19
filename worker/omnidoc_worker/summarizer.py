import logging
import re

from omnidoc_worker.ner import _resolve_device
from omnidoc_worker.schemas import DocumentInsight

log = logging.getLogger(__name__)

_CHUNK_CHARS = 6000
_MAX_FACTS = 12
_SYSTEM = (
    "You are a precise document analyst. Write in clear, specific prose. "
    "Use only information that appears in the document, and do not invent facts."
)
_BULLET = re.compile(r"^(?:[-*•]+|\d+[.)])\s*")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


class DocumentSummarizer:
    def __init__(self, model_name: str, model_file: str, device: str) -> None:
        self.model_name = model_name
        self.model_file = model_file
        self._generate = _load_generator(model_name, model_file, device)

    def analyze(self, text: str) -> DocumentInsight:
        cleaned = " ".join(text.split())
        if not cleaned:
            return DocumentInsight(
                summary="The document contains no readable text.",
                keyInformation=["No readable text was found."],
            )

        parts = chunk_text(cleaned, _CHUNK_CHARS)
        summaries = [self._summarize(part) for part in parts]
        summary = summaries[0] if len(summaries) == 1 else self._summarize(" ".join(summaries))
        if not summary:
            summary = extractive_summary(cleaned)

        facts: list[str] = []
        for part in parts:
            facts.extend(parse_key_information(self._key_facts(part)))
        facts = unique_facts(facts)[:_MAX_FACTS]
        if not facts:
            facts = unique_facts(parse_key_information(summary))[:_MAX_FACTS] or [summary]

        insight = DocumentInsight(summary=summary, keyInformation=facts)
        log.info("Summary ready (%s chars, %s key facts)", len(insight.summary), len(insight.key_information))
        return insight

    def _summarize(self, text: str) -> str:
        prompt = (
            "Write a clear summary of this document in 4 to 6 sentences. "
            "Say what kind of document it is, who is involved, and the important dates, "
            "amounts, and obligations. Keep the wording specific.\n\n"
            f"Document:\n{text}"
        )
        return _clean_generation(self._generate(prompt, 360))

    def _key_facts(self, text: str) -> str:
        prompt = (
            "List the key facts from this document. "
            "Put each fact on its own line as Label: value. "
            "Include the parties, dates, amounts, reference numbers, and obligations that appear. "
            "Do not add a title or a closing sentence.\n\n"
            f"Document:\n{text}"
        )
        return self._generate(prompt, 420)


def chunk_text(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            break_at = text.rfind(" ", start + size // 2, end)
            if break_at != -1:
                end = break_at
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        start = end
    return chunks or [text]


def parse_key_information(raw: str) -> list[str]:
    lines = []
    for line in raw.splitlines():
        line = _BULLET.sub("", line).strip(" -:\t")
        if _usable_fact(line):
            lines.append(line)
    if len(lines) <= 1:
        lines = [sentence.strip() for sentence in _SENTENCE.split(raw.strip()) if _usable_fact(sentence.strip())]
    return lines


def unique_facts(facts: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for fact in facts:
        key = fact.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(fact)
    return unique


def extractive_summary(text: str) -> str:
    if len(text) <= 500:
        return text
    cut = text[:500]
    period = cut.rfind(". ")
    if period > 80:
        return cut[: period + 1]
    return cut.rstrip() + "..."


def _usable_fact(line: str) -> bool:
    if len(line) < 3:
        return False
    lowered = line.casefold()
    skipped = (
        "list the key facts",
        "summarize:",
        "here are",
        "key facts",
        "the key facts",
    )
    return not lowered.startswith(skipped)


def _clean_generation(text: str) -> str:
    cleaned = text.strip()
    if cleaned.casefold().startswith("summary:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    return cleaned.strip("`").strip()


def _load_generator(model_name: str, model_file: str, device: str):
    import os

    from huggingface_hub import hf_hub_download
    from llama_cpp import Llama

    log.info("Loading summarization model %s (%s)", model_name, model_file)
    path = hf_hub_download(repo_id=model_name, filename=model_file)
    threads = min(8, os.cpu_count() or 4)
    gpu_layers = 0 if _resolve_device(device) < 0 else 99
    llm = Llama(
        model_path=path,
        n_ctx=4096,
        n_threads=threads,
        n_gpu_layers=gpu_layers,
        verbose=False,
    )

    def generate(prompt: str, max_new_tokens: int) -> str:
        result = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_new_tokens,
            temperature=0.4,
            repeat_penalty=1.08,
        )
        return str(result["choices"][0]["message"]["content"]).strip()

    return generate
