import unittest

from app.evaluator import build_quality_checks, compute_confidence


class TestEvaluator(unittest.TestCase):
    def test_confidence_high_when_clean(self):
        confidence = compute_confidence("Tutto ok.", [{"name": "get_patient_status"}], 2, False)
        self.assertGreaterEqual(confidence, 0.7)

    def test_confidence_low_when_tool_error(self):
        confidence = compute_confidence("Errore nei dati.", [{"name": "get_patient_status", "error": "not found"}], 3, True)
        self.assertLess(confidence, 0.6)

    def test_quality_notes_for_errors(self):
        notes = build_quality_checks("Errore nei dati.", [{"name": "get_patient_status", "error": "not found"}], 3, True)
        self.assertTrue(any("errore" in note.lower() for note in notes))

    def test_quality_notes_when_clean(self):
        notes = build_quality_checks("Risposta valida.", [{"name": "get_patient_status"}], 2, False)
        self.assertTrue(any("nessuna anomalia" in note.lower() for note in notes))


if __name__ == "__main__":
    unittest.main()
