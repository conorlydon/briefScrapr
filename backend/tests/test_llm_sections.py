import unittest
from unittest.mock import patch

from models.project import SectionSpecification
from services.llm import analyse_brief, split_brief


class SectionAnalysisTests(unittest.TestCase):
    def test_sections_cover_source_including_final_section(self):
        for text in ("".join(f"Line {i}: source material\n" for i in range(500)), "x" * 7001):
            sections = split_brief(text)
            self.assertTrue(all(len(section) <= 2000 for section in sections))
            reconstructed = sections[0] + "".join(section[200:] for section in sections[1:])
            self.assertEqual(reconstructed, text)
            self.assertTrue(text.endswith(sections[-1]))

    def test_merge_keeps_all_sections_and_more_than_five_items(self):
        sections = [f"Section {index}" for index in range(4)]
        results = [SectionSpecification(
            project_name="Whole project" if index == 0 else "",
            description=f"Part {index} summary.",
            languages=[" Python " if index == 0 else "python"],
            technologies=[], requirements=[f"Task {index}a", f"Task {index}b"],
            components=[f"Part {index}"], deliverables=[f"Submission {index}"],
        ) for index in range(4)]
        with patch("services.llm.split_brief", return_value=sections), patch(
            "services.llm.analyse_section", side_effect=results
        ) as analyse:
            result = analyse_brief("Full brief")
        self.assertEqual([call.args[0] for call in analyse.call_args_list], sections)
        self.assertEqual(result.project_name, "Whole project")
        self.assertEqual(result.languages, ["Python"])
        self.assertEqual(len(result.requirements), 8)
        self.assertEqual(result.deliverables, [f"Submission {index}" for index in range(4)])
        for index in range(4):
            self.assertIn(f"Part {index} summary.", result.description)

    def test_failed_section_does_not_return_partial_success(self):
        with patch("services.llm.split_brief", return_value=["first", "last"]), patch(
            "services.llm.analyse_section", side_effect=ValueError("invalid section")
        ):
            with self.assertRaises(ValueError):
                analyse_brief("Full brief")


if __name__ == "__main__":
    unittest.main()
