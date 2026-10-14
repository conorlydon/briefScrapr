import json
import unittest
from unittest.mock import patch

from app.api.routes.briefs import stream_analysis
from models.project import SectionSpecification


class AnalysisProgressTests(unittest.TestCase):
    def test_progress_arrives_before_model_and_result_after_all_sections(self):
        result = SectionSpecification(project_name="Demo", description="Test project",
                                      languages=[], technologies=[], requirements=[],
                                      components=[], deliverables=[])
        with patch("services.llm.split_brief", return_value=["first", "second"]), patch(
            "services.llm.analyse_section", return_value=result
        ) as model:
            stream = stream_analysis("Full brief", "demo.pdf")
            first = json.loads(next(stream))
            self.assertEqual(first["completed"], 0)
            self.assertEqual(first["total"], 2)
            model.assert_not_called()
            events = [first] + [json.loads(line) for line in stream]
        self.assertEqual(model.call_count, 2)
        self.assertEqual([event["completed"] for event in events[:-1]], [0, 1, 1, 2])
        self.assertEqual(events[-1]["type"], "complete")
        self.assertEqual(events[-1]["filename"], "demo.pdf")
        self.assertEqual(events[-1]["analysis"]["project_name"], "Demo")

    def test_truncated_json_yields_error_without_success(self):
        with patch("services.llm.split_brief", return_value=["first"]), patch(
            "services.llm.client.chat", return_value={"message": {"content": '{"project_name": "unfinished'}}
        ):
            events = [json.loads(line) for line in stream_analysis("Full brief", "demo.pdf")]
        self.assertEqual(events[-1]["type"], "error")
        self.assertIn("incomplete or invalid", events[-1]["message"])
        self.assertFalse(any(event["type"] == "complete" for event in events))


if __name__ == "__main__":
    unittest.main()
