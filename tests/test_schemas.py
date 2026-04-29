import unittest

from app.schemas import QueryResponse, ToolCall


class TestSchemas(unittest.TestCase):
    def test_query_response_has_quality_fields(self):
        response = QueryResponse(
            answer="Ok",
            tool_calls=[ToolCall(name="get_patients_by_department", arguments={})],
            iterations=1,
            model="claude-haiku-4-5-20251001",
            confidence=0.85,
            quality_checks=["Nessuna anomalia rilevata."],
        )

        self.assertEqual(response.confidence, 0.85)
        self.assertEqual(response.quality_checks[0], "Nessuna anomalia rilevata.")


if __name__ == "__main__":
    unittest.main()
