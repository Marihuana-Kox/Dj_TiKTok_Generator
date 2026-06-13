from django.test import SimpleTestCase

from .services import build_short_script_prompt, parse_short_script_json


class ShortScriptParserTests(SimpleTestCase):
    def test_build_prompt_keeps_json_template(self):
        prompt = build_short_script_prompt("Пирамиды Гизы")

        self.assertIn('"style": ""', prompt)
        self.assertIn("Пирамиды Гизы", prompt)

    def test_parse_valid_script_json(self):
        data = parse_short_script_json(
            """
            {
              "style": "SHOCK",
              "hook": "Test hook.",
              "voiceover": "Full voiceover.",
              "scenes": [
                {"text": "One", "image_prompt": "cinematic one", "duration": 3},
                {"text": "Two", "image_prompt": "cinematic two", "duration": 3},
                {"text": "Three", "image_prompt": "cinematic three", "duration": 3},
                {"text": "Four", "image_prompt": "cinematic four", "duration": 3}
              ]
            }
            """
        )

        self.assertEqual(data["style"], "SHOCK")
        self.assertEqual(len(data["scenes"]), 4)
