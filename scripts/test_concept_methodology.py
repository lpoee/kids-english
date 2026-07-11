import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent / "generate_ai_flashcards.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("concept_methodology", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ConceptMethodologyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_shapes_use_direct_flat_geometry(self):
        for slug in ("round", "square"):
            prompt = self.module.adjective_prompt(slug, slug)
            self.assertIn("flat front-facing geometry", prompt)
            self.assertIn("no scene, props, perspective, depth, or shadow", prompt)

    def test_comparative_adjectives_control_one_dimension(self):
        cases = {
            "big": "identical circles",
            "small": "identical circles",
            "tall": "exactly the same width",
            "short": "exactly the same width",
            "long": "exactly the same thickness",
            "wide": "exactly the same height",
            "narrow": "exactly the same height",
        }
        for slug, evidence in cases.items():
            with self.subTest(slug=slug):
                prompt = self.module.adjective_prompt(slug, slug)
                self.assertIn(evidence, prompt)
                self.assertIn("Change only the target dimension", prompt)

    def test_concrete_nouns_use_light_explanatory_context(self):
        prompt = self.module.word_prompt("cat", "cat photo")
        self.assertIn("one natural context cue", prompt)
        self.assertIn("must explain the subject", prompt)
        self.assertIn("must not compete", prompt)

    def test_actions_require_visible_motion_and_result(self):
        prompt = self.module.word_prompt("jump", "jumping child")
        self.assertIn("body position, motion direction, and visible result", prompt)
        self.assertIn("understood without reading", prompt)


if __name__ == "__main__":
    unittest.main()
