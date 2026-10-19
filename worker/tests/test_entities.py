import unittest

from pydantic import ValidationError

from omnidoc_worker.ner import build_entities
from omnidoc_worker.schemas import ExtractedEntities


class EntityMappingTests(unittest.TestCase):
    def test_merges_split_date_and_money_tokens(self) -> None:
        text = "Jane Miller of ACME Supplies signed on January 12, 2024 and paid $250.00."
        predictions = [
            {"entity": "B-PERSON", "score": 0.99, "start": 0, "end": 4},
            {"entity": "I-PERSON", "score": 0.99, "start": 5, "end": 11},
            {"entity": "B-ORG", "score": 0.99, "start": 15, "end": 17},
            {"entity": "I-ORG", "score": 0.99, "start": 17, "end": 19},
            {"entity": "I-ORG", "score": 0.99, "start": 20, "end": 28},
            {"entity": "B-DATE", "score": 0.99, "start": 39, "end": 46},
            {"entity": "I-DATE", "score": 0.99, "start": 47, "end": 49},
            {"entity": "I-DATE", "score": 0.99, "start": 49, "end": 50},
            {"entity": "I-DATE", "score": 0.99, "start": 51, "end": 54},
            {"entity": "B-PERSON", "score": 0.79, "start": 54, "end": 55},
            {"entity": "B-MONEY", "score": 0.99, "start": 66, "end": 69},
            {"entity": "B-MONEY", "score": 0.99, "start": 69, "end": 70},
            {"entity": "B-MONEY", "score": 0.99, "start": 70, "end": 72},
        ]

        entities = build_entities(predictions, text, 0.5)

        self.assertEqual(entities.names, ["Jane Miller"])
        self.assertEqual(entities.orgs, ["ACME Supplies"])
        self.assertEqual(entities.dates, ["January 12, 2024"])
        self.assertEqual(entities.values, ["$250.00"])

    def test_maps_ontonotes_labels_and_drops_low_scores(self) -> None:
        text = "Jane Miller of ACME Supplies signed on January 12, 2024 and paid $250.00."
        predictions = [
            {"entity_group": "PERSON", "score": 0.98, "word": "Jane Miller", "start": 0, "end": 11},
            {"entity_group": "ORG", "score": 0.91, "word": "ACME Supplies", "start": 15, "end": 28},
            {"entity_group": "DATE", "score": 0.88, "word": "January 12, 2024", "start": 39, "end": 55},
            {"entity_group": "MONEY", "score": 0.93, "word": "$250.00", "start": 65, "end": 72},
            {"entity_group": "GPE", "score": 0.99, "word": "ignored", "start": 0, "end": 4},
            {"entity_group": "PERSON", "score": 0.2, "word": "too low", "start": 0, "end": 4},
        ]

        entities = build_entities(predictions, text, 0.5)

        self.assertEqual(entities.names, ["Jane Miller"])
        self.assertEqual(entities.orgs, ["ACME Supplies"])
        self.assertEqual(entities.dates, ["January 12, 2024"])
        self.assertEqual(entities.values, ["$250.00"])
        self.assertEqual([span.label for span in entities.entities], ["NAME", "ORG", "DATE", "VALUE"])

    def test_schema_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValidationError):
            ExtractedEntities.model_validate(
                {"names": [], "dates": [], "orgs": [], "values": [], "entities": [], "extra": True}
            )


if __name__ == "__main__":
    unittest.main()
