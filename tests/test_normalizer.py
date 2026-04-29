import unittest

from app.normalizer import normalize_arguments


class TestNormalizer(unittest.TestCase):
    def test_translate_department_alias(self):
        normalized = normalize_arguments("get_patients_by_department", {"department": "cardiologia"})
        self.assertEqual(normalized["department"], "cardiology")

    def test_translate_status_alias(self):
        normalized = normalize_arguments("set_patient_status", {"status": "dimesso"})
        self.assertEqual(normalized["status"], "discharged")

    def test_preserve_other_values(self):
        normalized = normalize_arguments("update_vital_signs", {"heart_rate": 72})
        self.assertEqual(normalized["heart_rate"], 72)


if __name__ == "__main__":
    unittest.main()
