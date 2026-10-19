import logging
from typing import Any

from omnidoc_worker.schemas import EntitySpan, ExtractedEntities

log = logging.getLogger(__name__)

_LABELS = {
    "PERSON": "NAME",
    "PER": "NAME",
    "ORG": "ORG",
    "ORGANIZATION": "ORG",
    "DATE": "DATE",
    "TIME": "DATE",
    "MONEY": "VALUE",
    "PERCENT": "VALUE",
    "QUANTITY": "VALUE",
    "CARDINAL": "VALUE",
    "CARDINAL_NUMBER": "VALUE",
}


class EntityExtractor:
    def __init__(self, model_name: str, score_threshold: float, device: str) -> None:
        from transformers import pipeline

        resolved = _resolve_device(device)
        log.info("Loading NER model %s on %s", model_name, "cuda" if resolved == 0 else "cpu")
        self._pipeline = pipeline(
            "token-classification",
            model=model_name,
            aggregation_strategy=None,
            device=resolved,
        )
        self._threshold = score_threshold
        self.model_name = model_name

    def extract(self, text: str) -> ExtractedEntities:
        if not text.strip():
            return ExtractedEntities(names=[], dates=[], orgs=[], values=[], entities=[])
        predictions = self._pipeline(text)
        return build_entities(predictions, text, self._threshold)


def build_entities(predictions: list[dict[str, Any]], source: str, score_threshold: float) -> ExtractedEntities:
    if predictions and "entity_group" in predictions[0]:
        spans = _spans_from_groups(predictions, source, score_threshold)
    else:
        spans = _spans_from_tokens(predictions, source, score_threshold)
    return ExtractedEntities(
        names=_unique(span.text for span in spans if span.label == "NAME"),
        dates=_unique(span.text for span in spans if span.label == "DATE"),
        orgs=_unique(span.text for span in spans if span.label == "ORG"),
        values=_unique(span.text for span in spans if span.label == "VALUE"),
        entities=spans,
    )


def _spans_from_groups(predictions: list[dict[str, Any]], source: str, score_threshold: float) -> list[EntitySpan]:
    spans: list[EntitySpan] = []
    for prediction in predictions:
        label = _canonical_label(str(prediction.get("entity_group") or ""))
        score = float(prediction.get("score", 0.0))
        if label is None or score < score_threshold:
            continue
        start = int(prediction.get("start", 0))
        end = int(prediction.get("end", start))
        start, end, text = _expand_span(source, start, end, label)
        if not text:
            continue
        spans.append(EntitySpan(text=text, label=label, score=round(score, 4), start=start, end=end))
    return _dedupe(spans)


def _spans_from_tokens(predictions: list[dict[str, Any]], source: str, score_threshold: float) -> list[EntitySpan]:
    grouped: list[dict[str, Any]] = []
    for prediction in predictions:
        label = _canonical_label(str(prediction.get("entity") or ""))
        score = float(prediction.get("score", 0.0))
        start = int(prediction.get("start", 0))
        end = int(prediction.get("end", start))
        piece = source[start:end] if 0 <= start <= end <= len(source) else ""
        if grouped and _extends(grouped[-1], label, score, start, piece, source, score_threshold):
            current = grouped[-1]
            current["end"] = end
            current["score"] = min(float(current["score"]), score)
            continue
        if label is None or score < score_threshold or not piece.strip():
            continue
        grouped.append({"label": label, "start": start, "end": end, "score": score})

    spans: list[EntitySpan] = []
    for item in grouped:
        start, end, text = _expand_span(source, int(item["start"]), int(item["end"]), str(item["label"]))
        if not text or _is_punctuation(text):
            continue
        spans.append(
            EntitySpan(
                text=text,
                label=item["label"],
                score=round(float(item["score"]), 4),
                start=start,
                end=end,
            )
        )
    return _dedupe(spans)


def _extends(
    current: dict[str, Any],
    label: str | None,
    score: float,
    start: int,
    piece: str,
    source: str,
    score_threshold: float,
) -> bool:
    gap = source[int(current["end"]):start]
    adjacent = start == int(current["end"]) or _is_bridge(gap)
    if not adjacent:
        return False
    if label == current["label"] and score >= score_threshold:
        return True
    date_text = source[int(current["start"]):int(current["end"])]
    return current["label"] == "DATE" and adjacent and piece.isdigit() and date_text[-1:].isdigit()


def _expand_span(source: str, start: int, end: int, label: str) -> tuple[int, int, str]:
    if label == "VALUE" and start > 0 and source[start - 1] in "$€£":
        start -= 1
    if label == "VALUE" and end < len(source) and source[end] == "%":
        end += 1
    text = " ".join(source[start:end].split())
    return start, end, text


def _is_bridge(gap: str) -> bool:
    return bool(gap) and all(character.isspace() or character in ",.-/" for character in gap)


def _is_punctuation(text: str) -> bool:
    return all(not character.isalnum() for character in text)


def _canonical_label(raw: str) -> str | None:
    label = raw.strip().upper().replace("-", "_").replace(" ", "_")
    if label.startswith("B_") or label.startswith("I_"):
        label = label[2:]
    return _LABELS.get(label)


def _dedupe(spans: list[EntitySpan]) -> list[EntitySpan]:
    seen: set[tuple[str, str, int]] = set()
    unique: list[EntitySpan] = []
    for span in spans:
        key = (span.label, span.text.casefold(), span.start)
        if key in seen:
            continue
        seen.add(key)
        unique.append(span)
    return unique


def _unique(values) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return unique


def _resolve_device(device: str) -> int:
    choice = device.strip().lower()
    if choice == "cpu":
        return -1
    if choice == "cuda":
        return 0
    import torch

    return 0 if torch.cuda.is_available() else -1
