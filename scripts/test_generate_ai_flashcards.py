import json
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageColor


SCRIPT_PATH = Path(__file__).resolve().parent / "generate_ai_flashcards.py"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_ai_flashcards", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GenerateAiFlashcardsTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module()

    def test_output_directories_match_generated_tree(self):
        self.assertTrue(str(self.module.WORD_DIR).endswith("images/generated/vocab"))
        self.assertTrue(str(self.module.ADJ_DIR).endswith("images/generated/adjectives"))
        self.assertTrue(str(self.module.PHRASE_DIR).endswith("images/generated/phrases"))

    def test_index_expected_assets_match_catalog(self):
        self.module.assert_catalog_matches_index()

    def test_default_pipeline_includes_review_and_audit(self):
        with mock.patch.object(sys, "argv", ["generate_ai_flashcards.py"]):
            args = self.module.parse_args()
        self.assertEqual(args.only, "words,adjs,phrases,review,manifests,audit")

    def test_default_generation_backend_is_local_comfyui(self):
        with mock.patch.object(sys, "argv", ["generate_ai_flashcards.py"]):
            args = self.module.parse_args()
        self.assertEqual(args.model, "sd_xl_base_1.0.safetensors")
        self.assertEqual(args.generator, "comfyui")

    def test_build_comfyui_workflow_uses_flux2_klein_nodes(self):
        spec = self.module.AssetSpec(
            slug="grape",
            prompt="grape prompt",
            out_dir=Path("/tmp/out"),
            filename="grape.png",
            asset_type="still",
            label="Grape",
            query="grape",
        )
        workflow = self.module.build_comfyui_workflow(
            spec=spec,
            checkpoint=self.module.FLUX2_KLEIN_CHECKPOINT,
            width=1024,
            height=1024,
            seed=123,
            negative="no person",
        )
        self.assertEqual(workflow["64"]["class_type"], "UNETLoader")
        self.assertEqual(workflow["67"]["class_type"], "CLIPLoader")
        self.assertEqual(workflow["68"]["class_type"], "VAELoader")
        self.assertEqual(workflow["64"]["inputs"]["unet_name"], self.module.FLUX2_KLEIN_CHECKPOINT)
        self.assertEqual(workflow["67"]["inputs"]["clip_name"], self.module.FLUX2_KLEIN_TEXT_ENCODER)
        self.assertEqual(workflow["68"]["inputs"]["vae_name"], self.module.FLUX2_VAE)
        self.assertEqual(workflow["69"]["inputs"]["text"], "no person")

    def test_ensure_comfyui_ready_accepts_flux2_klein_models(self):
        responses = [
            {"devices": [{"name": "cuda:1"}]},
            {"UNETLoader": {"input": {"required": {"unet_name": [[self.module.FLUX2_KLEIN_CHECKPOINT]]}}}},
            {"CLIPLoader": {"input": {"required": {"clip_name": [[self.module.FLUX2_KLEIN_TEXT_ENCODER]]}}}},
            {"VAELoader": {"input": {"required": {"vae_name": [[self.module.FLUX2_VAE]]}}}},
        ]
        with mock.patch.object(self.module, "comfyui_json_request", side_effect=responses):
            self.module.ensure_comfyui_ready(self.module.FLUX2_KLEIN_CHECKPOINT)

    def test_parse_review_payload_extracts_wrapped_json(self):
        parsed = self.module.parse_review_payload(
            'review: {"pass": true, "score": 91, "reason": "clear concept", "issues": []}'
        )
        self.assertTrue(parsed["pass"])
        self.assertEqual(parsed["score"], 91)
        self.assertEqual(parsed["reason"], "clear concept")
        self.assertEqual(parsed["issues"], [])

    def test_build_audit_report_flags_missing_low_score_and_unreviewed(self):
        ok_review = self.module.ReviewResult(
            slug="cat",
            passed=True,
            score=92,
            reason="clear",
            issues=(),
            reviewer="omini",
            reviewed_at="2026-05-23T00:00:00+00:00",
        )
        low_review = self.module.ReviewResult(
            slug="big",
            passed=True,
            score=70,
            reason="too ambiguous",
            issues=("ambiguous",),
            reviewer="omini",
            reviewed_at="2026-05-23T00:00:00+00:00",
        )
        report = self.module.build_audit_report(
            expected={
                "vocab": {"cat", "dog"},
                "adjectives": {"big"},
                "phrases": {"hello"},
            },
            actual={
                "vocab": {"cat"},
                "adjectives": {"big"},
                "phrases": {"hello"},
            },
            reviews={
                "vocab": {"cat": ok_review},
                "adjectives": {"big": low_review},
                "phrases": {},
            },
            min_score=85,
        )
        self.assertFalse(report["ok"])
        self.assertEqual(report["stages"]["vocab"]["missing"], ["dog"])
        self.assertEqual(report["stages"]["adjectives"]["low_score"], ["big"])
        self.assertEqual(report["stages"]["phrases"]["unreviewed"], ["hello"])

    def test_index_keeps_images_enabled_by_default(self):
        html = (SCRIPT_PATH.parent.parent / "index.html").read_text(encoding="utf-8")
        self.assertIn("const IMAGES_ENABLED = true;", html)

    def test_review_image_payload_is_compressed_for_local_vlm(self):
        sample_png = next((SCRIPT_PATH.parent.parent / "assets" / "images" / "openmoji" / "color" / "618x618").glob("*.png"))
        payload = self.module.encode_review_image_data_url(sample_png)
        self.assertTrue(payload.startswith("data:image/png;base64,"))

    def test_review_image_request_disables_reasoning_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            image_path = out_dir / "cat.png"
            Image.new("RGB", (32, 32), "white").save(image_path)
            spec = self.module.AssetSpec(
                slug="cat",
                prompt="cat prompt",
                out_dir=out_dir,
                filename="cat.png",
                asset_type="still",
                label="Cat",
                query="cat",
            )

            class DummyResponse:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return b'{"choices":[{"message":{"content":"{\\"pass\\": true, \\"score\\": 95, \\"reason\\": \\"clear\\", \\"issues\\": []}"}}]}'

            def fake_urlopen(request_obj, timeout):
                payload = json.loads(request_obj.data.decode("utf-8"))
                self.assertFalse(payload["include_reasoning"])
                self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})
                self.assertIn("Output exactly one JSON object and stop.", payload["messages"][0]["content"])
                self.assertIn("Fail if the image is not about the animal", payload["messages"][1]["content"][0]["text"])
                self.assertIn("Do NOT fail because of background style", payload["messages"][1]["content"][0]["text"])
                return DummyResponse()

            with mock.patch.object(self.module.urlrequest, "urlopen", side_effect=fake_urlopen):
                review = self.module.review_image(
                    spec,
                    qa_url="http://127.0.0.1:18090/v1/chat/completions",
                    qa_model="Nemotron",
                    timeout=1,
                )
        self.assertTrue(review.passed)
        self.assertEqual(review.score, 95)

    def test_review_specs_records_review_errors_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            image_path = out_dir / "cat.png"
            Image.new("RGB", (32, 32), "white").save(image_path)
            spec = self.module.AssetSpec(
                slug="cat",
                prompt="cat prompt",
                out_dir=out_dir,
                filename="cat.png",
                asset_type="still",
                label="Cat",
                query="cat",
            )
            with (
                mock.patch.object(self.module, "review_image", side_effect=RuntimeError("boom")),
                mock.patch.object(self.module, "write_review_manifest"),
            ):
                reviews = self.module.review_specs(
                    stage="vocab",
                    specs=[spec],
                    qa_url="http://127.0.0.1:18090/v1/chat/completions",
                    qa_model="Nemotron",
                    min_score=85,
                    timeout=1,
                    dry_run=False,
                    force=True,
                )
        self.assertIn("cat", reviews)
        self.assertFalse(reviews["cat"].passed)
        self.assertIn("review request failed", reviews["cat"].reason)
        self.assertEqual(reviews["cat"].issues, ("review_error",))

    def test_word_prompt_requires_single_clear_subject_and_consistent_style(self):
        prompt = self.module.word_prompt("cat", "cat photo")
        self.assertIn("Show one clear main subject only.", prompt)
        self.assertIn("This is a flashcard image, not a poster, page design, or story scene.", prompt)
        self.assertIn("framed picture grid", prompt)
        self.assertIn("multi-panel layout", prompt)
        self.assertIn("Show one cat only.", prompt)
        self.assertIn("plain pale background", prompt)
        self.assertIn("no scenery or props", prompt)

    def test_food_prompt_requires_object_only_product_photo(self):
        prompt = self.module.word_prompt("grape", "grapes fruit")
        self.assertIn("square photo of exactly one food item", prompt)
        self.assertIn("realistic studio object photography", prompt)
        self.assertIn("not portrait photography", prompt)
        self.assertIn("one complete hanging bunch of small oval translucent green grapes on a branching vine", prompt)
        self.assertIn("exactly one complete food item fully inside frame", prompt)
        self.assertIn("single bunch must read clearly as one whole cluster", prompt)
        self.assertIn("stem visible near the top", prompt)
        self.assertIn("generous plain background around it", prompt)
        self.assertIn("Do not zoom in to a pile or texture of loose grapes", prompt)
        self.assertIn("not as apples or round fruit", prompt)
        self.assertIn("object-only with no people and no visible body parts", prompt)
        self.assertIn("unsupported against the seamless studio background", prompt)
        self.assertIn("fully inside the frame with empty margin on every side", prompt.lower())
        self.assertIn("no bowl, no plate, no table", prompt.lower())
        self.assertIn("no drink", prompt.lower())
        self.assertIn("no nearby prop", prompt.lower())
        self.assertNotIn("preschool learning card", prompt)
        self.assertNotIn("child", prompt.lower())

    def test_cherry_prompt_uses_cherry_specific_cluster_language(self):
        prompt = self.module.word_prompt("cherry", "cherries fruit")
        self.assertIn("one complete pair or small cluster of glossy red cherries attached together by thin stems", prompt)
        self.assertIn("one attached pair or a very small cherry cluster", prompt)
        self.assertIn("Do not zoom in to a repeating cherry pattern", prompt)
        self.assertNotIn("small oval grape", prompt)
        self.assertNotIn("apples or round fruit", prompt)

    def test_food_words_use_food_negative_prompt(self):
        spec = self.module.AssetSpec(
            slug="grape",
            prompt="grape prompt",
            out_dir=Path("/tmp"),
            filename="grape.png",
            asset_type="still",
            label="Grape",
            query="grapes fruit",
        )
        negative = self.module.negative_prompt_for_spec(spec)
        self.assertIsNotNone(negative)
        self.assertIn("portrait", negative)
        self.assertIn("person", negative)
        self.assertIn("table", negative)
        self.assertIn("glass", negative)
        self.assertIn("vase", negative)
        self.assertIn("black frame", negative)
        self.assertIn("duplicate fruit", negative)
        self.assertIn("cropped subject", negative)
        self.assertIn("macro close-up", negative)

    def test_generation_attempt_prompt_escalates_to_isolated_subject_for_animals(self):
        spec = self.module.AssetSpec(
            slug="cat",
            prompt=self.module.word_prompt("cat", "cat photo"),
            out_dir=Path("/tmp"),
            filename="cat.png",
            asset_type="still",
            label="Cat",
            query="cat photo",
        )
        first_prompt = self.module.prompt_for_generation_attempt(spec, attempt=1)
        later_prompt = self.module.prompt_for_generation_attempt(spec, attempt=3)
        self.assertEqual(first_prompt, spec.prompt)
        self.assertIn("Create one flashcard image of a single cat.", later_prompt)
        self.assertIn("empty pastel background", later_prompt)
        self.assertIn("no scenery or props", later_prompt)

    def test_generation_attempt_prompt_escalates_to_packshot_for_food(self):
        spec = self.module.AssetSpec(
            slug="grape",
            prompt=self.module.word_prompt("grape", "grapes fruit"),
            out_dir=Path("/tmp"),
            filename="grape.png",
            asset_type="still",
            label="Grape",
            query="grapes fruit",
        )
        later_prompt = self.module.prompt_for_generation_attempt(spec, attempt=3)
        self.assertIn("studio object photo", later_prompt)
        self.assertIn("one complete hanging bunch of small oval translucent green grapes on a branching vine", later_prompt)
        self.assertIn("single bunch must read clearly as one whole cluster", later_prompt)
        self.assertIn("stem visible near the top", later_prompt)
        self.assertIn("not as apples or round fruit", later_prompt)
        self.assertIn("zero humans, zero faces, zero hands, zero dishes, and zero tables", later_prompt.lower())
        self.assertIn("unsupported against the seamless studio background", later_prompt)
        self.assertIn("empty margin on every side", later_prompt.lower())
        self.assertIn("no nearby prop", later_prompt.lower())

    def test_generation_attempt_prompt_uses_cherry_specific_cluster_rules(self):
        spec = self.module.AssetSpec(
            slug="cherry",
            prompt=self.module.word_prompt("cherry", "cherries fruit"),
            out_dir=Path("/tmp"),
            filename="cherry.png",
            asset_type="still",
            label="Cherry",
            query="cherries fruit",
        )
        later_prompt = self.module.prompt_for_generation_attempt(spec, attempt=3)
        self.assertIn("glossy red cherries attached together by thin stems", later_prompt)
        self.assertIn("very small cherry cluster", later_prompt)
        self.assertIn("repeating cherry pattern", later_prompt)
        self.assertNotIn("small oval grape", later_prompt)

    def test_cluster_fruit_preserves_full_subject(self):
        grape = self.module.AssetSpec(
            slug="grape",
            prompt="grape prompt",
            out_dir=Path("/tmp"),
            filename="grape.png",
            asset_type="still",
            label="Grape",
            query="grapes fruit",
        )
        cat = self.module.AssetSpec(
            slug="cat",
            prompt="cat prompt",
            out_dir=Path("/tmp"),
            filename="cat.png",
            asset_type="still",
            label="Cat",
            query="cat photo",
        )
        self.assertTrue(self.module.preserves_full_subject(grape))
        self.assertFalse(self.module.preserves_full_subject(cat))

    def test_normalize_generated_image_contains_cluster_fruit_without_cropping_edges(self):
        spec = self.module.AssetSpec(
            slug="grape",
            prompt="grape prompt",
            out_dir=Path("/tmp"),
            filename="grape.png",
            asset_type="still",
            label="Grape",
            query="grapes fruit",
        )
        image = Image.new("RGB", (400, 200), "#eee4d4")
        for x in range(0, 12):
            for y in range(40, 160):
                image.putpixel((x, y), (0, 0, 255))
        for x in range(388, 400):
            for y in range(40, 160):
                image.putpixel((x, y), (255, 0, 0))

        normalized = self.module.normalize_generated_image(image, spec, width=300, height=300)

        left_found = False
        right_found = False
        for x in range(0, 60):
            for y in range(80, 220):
                if normalized.getpixel((x, y)) == (0, 0, 255):
                    left_found = True
                    break
            if left_found:
                break
        for x in range(240, 300):
            for y in range(80, 220):
                if normalized.getpixel((x, y)) == (255, 0, 0):
                    right_found = True
                    break
            if right_found:
                break
        self.assertTrue(left_found)
        self.assertTrue(right_found)

    def test_phrase_prompt_requires_toddler_friendly_scene_illustration(self):
        prompt = self.module.phrase_prompt("lets_play", "two children happily starting a simple game together")
        self.assertIn("clear scene illustration", prompt)
        self.assertIn("one easy-to-read moment", prompt)
        self.assertIn("toddler can understand instantly", prompt)
        self.assertIn("no background clutter", prompt)
        self.assertIn("Use Chinese children", prompt)
        self.assertIn("use a Chinese parent and child", prompt)

    def test_body_word_prompt_avoids_identifiable_identity_features(self):
        prompt = self.module.word_prompt("eye", "eye")
        self.assertIn("real close-up photo", prompt)
        self.assertIn("Chinese child's eye area", prompt)
        self.assertIn("identity is not visible", prompt)
        self.assertIn("No full face, no hairstyle, no clothing, no jewelry", prompt)

    def test_action_word_prompt_avoids_recognizable_faces(self):
        prompt = self.module.word_prompt("run", "running child")
        self.assertIn("one Chinese preschool child", prompt)
        self.assertIn("exactly one child and exactly one body", prompt)
        self.assertIn("full body visible", prompt)
        self.assertIn("natural side view sports-photo composition", prompt)
        self.assertIn("simple plain clothing with no logos", prompt)
        self.assertIn("no border or poster frame", prompt)

    def test_action_words_use_person_compatible_negative_prompt(self):
        spec = self.module.AssetSpec(
            slug="run",
            prompt="run prompt",
            out_dir=Path("/tmp"),
            filename="run.png",
            asset_type="still",
            label="Run",
            query="running child",
        )
        negative = self.module.negative_prompt_for_spec(spec)
        self.assertIsNotNone(negative)
        self.assertIn("duplicate person", negative)
        self.assertNotIn("person, child, human", negative)

    def test_review_prompt_uses_explicit_toddler_flashcard_rubric(self):
        prompt = self.module.QA_PROMPT
        self.assertIn("image_quality", prompt)
        self.assertIn("concept_clarity", prompt)
        self.assertIn("child_friendliness", prompt)
        self.assertIn("distraction_level", prompt)
        self.assertIn("Do NOT fail an image just because the background is not plain", prompt)
        self.assertIn("Do not think step by step.", prompt)

    def test_extract_message_text_strips_whitespace_from_string(self):
        self.assertEqual(self.module.extract_message_text("  {\"pass\":true} \n"), "{\"pass\":true}")

    def test_detects_multi_panel_layout(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "grid.png"
            image = Image.new("RGB", (300, 300), "#7fb36a")
            for x in range(97, 104):
                for y in range(300):
                    image.putpixel((x, y), (255, 255, 255))
            for x in range(197, 204):
                for y in range(300):
                    image.putpixel((x, y), (255, 255, 255))
            for y in range(97, 104):
                for x in range(300):
                    image.putpixel((x, y), (255, 255, 255))
            for y in range(197, 204):
                for x in range(300):
                    image.putpixel((x, y), (255, 255, 255))
            image.save(image_path)
            with Image.open(image_path) as loaded:
                self.assertTrue(self.module.looks_like_multi_panel_layout(loaded.convert("RGB")))

    def test_detects_offset_framed_collage_layout(self):
        image = Image.new("RGB", (360, 360), "#d9d2c6")
        panels = [
            ((18, 18, 110, 110), "#94c973"),
            ((128, 24, 252, 130), "#f6d36a"),
            ((268, 20, 340, 96), "#8ed1f0"),
            ((24, 140, 132, 252), "#f6a96a"),
            ((146, 150, 248, 248), "#9fd6b0"),
            ((266, 132, 342, 230), "#f08a8a"),
            ((30, 274, 154, 338), "#b6baf2"),
            ((176, 270, 336, 340), "#f5c57f"),
        ]
        border_rgb = ImageColor.getrgb("#ffffff")
        for (left, top, right, bottom), fill in panels:
            fill_rgb = ImageColor.getrgb(fill)
            for x in range(left + 3, right - 3):
                for y in range(top + 3, bottom - 3):
                    image.putpixel((x, y), fill_rgb)
            for x in range(left, right):
                for y in range(top, bottom):
                    if x in {left, left + 1, left + 2, right - 3, right - 2, right - 1} or y in {top, top + 1, top + 2, bottom - 3, bottom - 2, bottom - 1}:
                        image.putpixel((x, y), border_rgb)
        self.assertTrue(self.module.looks_like_multi_panel_layout(image))

    def test_single_subject_layout_is_not_flagged_as_multi_panel(self):
        image = Image.new("RGB", (300, 300), "#d7f0c8")
        for x in range(90, 210):
            for y in range(70, 250):
                image.putpixel((x, y), (237, 143, 70))
        self.assertFalse(self.module.looks_like_multi_panel_layout(image))

    def test_spotlight_single_subject_layout_is_not_flagged_as_multi_panel(self):
        image = Image.new("RGB", (320, 320), "#c7beb8")
        center_x = center_y = 160
        for x in range(320):
            for y in range(320):
                if (x - center_x) ** 2 + (y - center_y) ** 2 <= 105 ** 2:
                    image.putpixel((x, y), (248, 240, 225))
        for x in range(110, 210):
            for y in range(72, 260):
                image.putpixel((x, y), (155, 155, 165))
        self.assertFalse(self.module.looks_like_multi_panel_layout(image))

    def test_detects_busy_background_on_single_subject_card(self):
        image = Image.new("RGB", (320, 320), "#f2ede4")
        for x in range(96, 224):
            for y in range(72, 276):
                image.putpixel((x, y), (168, 120, 92))
        clutter_blocks = [
            ((0, 0, 72, 72), "#5b7fa9"),
            ((248, 0, 320, 72), "#d48b70"),
            ((0, 248, 72, 320), "#8a9f63"),
            ((248, 248, 320, 320), "#7f5aa5"),
            ((0, 118, 54, 202), "#d9c34c"),
            ((266, 110, 320, 210), "#5aa3a0"),
        ]
        for left, top, right, bottom in [block[0] for block in clutter_blocks]:
            fill = next(color for box, color in clutter_blocks if box == (left, top, right, bottom))
            fill_rgb = ImageColor.getrgb(fill)
            for x in range(left, right):
                for y in range(top, bottom):
                    image.putpixel((x, y), fill_rgb)
        self.assertTrue(self.module.has_busy_background(image))

    def test_clean_single_subject_background_is_not_flagged_busy(self):
        image = Image.new("RGB", (320, 320), "#f2ede4")
        for x in range(96, 224):
            for y in range(72, 276):
                image.putpixel((x, y), (168, 120, 92))
        self.assertFalse(self.module.has_busy_background(image))

    def test_generate_local_asset_retries_after_multi_panel_rejection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            out_dir = tmp_root / "out"
            spec = self.module.AssetSpec(
                slug="cat",
                prompt="cat prompt",
                out_dir=out_dir,
                filename="cat.png",
                asset_type="still",
                label="Cat",
                query="cat",
            )
            attempt_counter = {"count": 0}

            def fake_download_outputs(history, output_dir):
                output_dir.mkdir(parents=True, exist_ok=True)
                out_path = output_dir / "generated.png"
                if attempt_counter["count"] == 0:
                    image = Image.new("RGB", (300, 300), "#7fb36a")
                    for x in range(145, 156):
                        for y in range(300):
                            image.putpixel((x, y), (255, 255, 255))
                    for y in range(145, 156):
                        for x in range(300):
                            image.putpixel((x, y), (255, 255, 255))
                else:
                    image = Image.new("RGB", (300, 300), "#d7f0c8")
                    for x in range(90, 210):
                        for y in range(70, 250):
                            image.putpixel((x, y), (237, 143, 70))
                image.save(out_path)
                attempt_counter["count"] += 1
                return [out_path]

            with (
                mock.patch.object(self.module, "TMP_DIR", tmp_root / "tmp"),
                mock.patch.object(self.module, "build_comfyui_workflow", return_value={}),
                mock.patch.object(self.module, "comfyui_submit", side_effect=["attempt-1", "attempt-2"]) as submit_mock,
                mock.patch.object(self.module, "comfyui_wait", side_effect=[{"ok": 1}, {"ok": 2}]),
                mock.patch.object(self.module, "comfyui_download_outputs", side_effect=fake_download_outputs),
            ):
                self.module.generate_local_asset(
                    spec=spec,
                    checkpoint="sdxl.safetensors",
                    size="300x300",
                    max_attempts=2,
                    dry_run=False,
                    force=True,
                    gate_on_review=False,
                    review_url="http://127.0.0.1:18090/v1/chat/completions",
                    review_model="Nemotron",
                    review_timeout=1,
                    min_score=85,
                )

            self.assertEqual(submit_mock.call_count, 2)
            self.assertTrue(spec.out_path.exists())
            with Image.open(spec.out_path) as final_image:
                self.assertFalse(self.module.looks_like_multi_panel_layout(final_image.convert("RGB")))

    def test_generate_local_asset_retries_after_busy_background_rejection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            out_dir = tmp_root / "out"
            spec = self.module.AssetSpec(
                slug="cat",
                prompt="cat prompt",
                out_dir=out_dir,
                filename="cat.png",
                asset_type="still",
                label="Cat",
                query="cat",
            )
            attempt_counter = {"count": 0}

            def fake_download_outputs(history, output_dir):
                output_dir.mkdir(parents=True, exist_ok=True)
                out_path = output_dir / "generated.png"
                image = Image.new("RGB", (320, 320), "#f2ede4")
                for x in range(96, 224):
                    for y in range(72, 276):
                        image.putpixel((x, y), (168, 120, 92) if attempt_counter["count"] == 0 else (135, 108, 92))
                if attempt_counter["count"] == 0:
                    clutter_blocks = [
                        ((0, 0, 72, 72), "#5b7fa9"),
                        ((248, 0, 320, 72), "#d48b70"),
                        ((0, 248, 72, 320), "#8a9f63"),
                        ((248, 248, 320, 320), "#7f5aa5"),
                    ]
                    for (left, top, right, bottom), fill in clutter_blocks:
                        fill_rgb = ImageColor.getrgb(fill)
                        for x in range(left, right):
                            for y in range(top, bottom):
                                image.putpixel((x, y), fill_rgb)
                image.save(out_path)
                attempt_counter["count"] += 1
                return [out_path]

            with (
                mock.patch.object(self.module, "TMP_DIR", tmp_root / "tmp"),
                mock.patch.object(self.module, "build_comfyui_workflow", return_value={}),
                mock.patch.object(self.module, "comfyui_submit", side_effect=["attempt-1", "attempt-2"]) as submit_mock,
                mock.patch.object(self.module, "comfyui_wait", side_effect=[{"ok": 1}, {"ok": 2}]),
                mock.patch.object(self.module, "comfyui_download_outputs", side_effect=fake_download_outputs),
            ):
                self.module.generate_local_asset(
                    spec=spec,
                    checkpoint="sdxl.safetensors",
                    size="320x320",
                    max_attempts=2,
                    dry_run=False,
                    force=True,
                    gate_on_review=False,
                    review_url="http://127.0.0.1:18090/v1/chat/completions",
                    review_model="Nemotron",
                    review_timeout=1,
                    min_score=85,
                )

            self.assertEqual(submit_mock.call_count, 2)
            self.assertTrue(spec.out_path.exists())
            with Image.open(spec.out_path) as final_image:
                self.assertFalse(self.module.has_busy_background(final_image.convert("RGB")))

    def test_generate_local_asset_retries_after_review_rejection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            out_dir = tmp_root / "out"
            spec = self.module.AssetSpec(
                slug="cat",
                prompt="cat prompt",
                out_dir=out_dir,
                filename="cat.png",
                asset_type="still",
                label="Cat",
                query="cat",
            )
            attempt_counter = {"count": 0}
            review_counter = {"count": 0}

            def fake_download_outputs(history, output_dir):
                output_dir.mkdir(parents=True, exist_ok=True)
                out_path = output_dir / "generated.png"
                image = Image.new("RGB", (300, 300), "#d7f0c8")
                fill = (237, 143, 70) if attempt_counter["count"] == 0 else (90, 130, 210)
                for x in range(90, 210):
                    for y in range(70, 250):
                        image.putpixel((x, y), fill)
                image.save(out_path)
                attempt_counter["count"] += 1
                return [out_path]

            def fake_review_image(review_spec, *, qa_url, qa_model, timeout):
                del qa_url, qa_model, timeout
                with Image.open(review_spec.out_path) as reviewed_image:
                    pixel = reviewed_image.getpixel((120, 120))
                if review_counter["count"] == 0:
                    self.assertEqual(pixel, (237, 143, 70))
                    result = self.module.ReviewResult(
                        slug=review_spec.slug,
                        passed=False,
                        score=20,
                        reason="multi subject",
                        issues=("multi subject",),
                        reviewer="Nemotron",
                        reviewed_at="2026-05-23T00:00:00+00:00",
                    )
                else:
                    self.assertEqual(pixel, (90, 130, 210))
                    result = self.module.ReviewResult(
                        slug=review_spec.slug,
                        passed=True,
                        score=95,
                        reason="clear",
                        issues=(),
                        reviewer="Nemotron",
                        reviewed_at="2026-05-23T00:00:00+00:00",
                    )
                review_counter["count"] += 1
                return result

            with (
                mock.patch.object(self.module, "TMP_DIR", tmp_root / "tmp"),
                mock.patch.object(self.module, "build_comfyui_workflow", return_value={}),
                mock.patch.object(self.module, "comfyui_submit", side_effect=["attempt-1", "attempt-2"]) as submit_mock,
                mock.patch.object(self.module, "comfyui_wait", side_effect=[{"ok": 1}, {"ok": 2}]),
                mock.patch.object(self.module, "comfyui_download_outputs", side_effect=fake_download_outputs),
                mock.patch.object(self.module, "review_image", side_effect=fake_review_image),
            ):
                self.module.generate_local_asset(
                    spec=spec,
                    checkpoint="sdxl.safetensors",
                    size="300x300",
                    max_attempts=2,
                    dry_run=False,
                    force=True,
                    gate_on_review=True,
                    review_url="http://127.0.0.1:18090/v1/chat/completions",
                    review_model="Nemotron",
                    review_timeout=30,
                    min_score=85,
                )

            self.assertEqual(submit_mock.call_count, 2)
            self.assertEqual(review_counter["count"], 2)
            self.assertTrue(spec.out_path.exists())
            with Image.open(spec.out_path) as final_image:
                self.assertEqual(final_image.getpixel((120, 120)), (90, 130, 210))

    def test_generate_local_asset_retries_after_review_gate_rejection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            out_dir = tmp_root / "out"
            spec = self.module.AssetSpec(
                slug="cat",
                prompt="cat prompt",
                out_dir=out_dir,
                filename="cat.png",
                asset_type="still",
                label="Cat",
                query="cat",
            )
            review_fail = self.module.ReviewResult(
                slug="cat",
                passed=False,
                score=20,
                reason="multiple panels",
                issues=("multiple panels",),
                reviewer="Nemotron",
                reviewed_at="2026-05-23T00:00:00+00:00",
            )
            review_pass = self.module.ReviewResult(
                slug="cat",
                passed=True,
                score=95,
                reason="clear single cat",
                issues=(),
                reviewer="Nemotron",
                reviewed_at="2026-05-23T00:00:01+00:00",
            )

            def fake_download_outputs(history, output_dir):
                output_dir.mkdir(parents=True, exist_ok=True)
                out_path = output_dir / "generated.png"
                image = Image.new("RGB", (300, 300), "#d7f0c8")
                for x in range(90, 210):
                    for y in range(70, 250):
                        image.putpixel((x, y), (237, 143, 70))
                image.save(out_path)
                return [out_path]

            with (
                mock.patch.object(self.module, "TMP_DIR", tmp_root / "tmp"),
                mock.patch.object(self.module, "build_comfyui_workflow", return_value={}),
                mock.patch.object(self.module, "comfyui_submit", side_effect=["attempt-1", "attempt-2"]) as submit_mock,
                mock.patch.object(self.module, "comfyui_wait", side_effect=[{"ok": 1}, {"ok": 2}]),
                mock.patch.object(self.module, "comfyui_download_outputs", side_effect=fake_download_outputs),
                mock.patch.object(self.module, "review_image", side_effect=[review_fail, review_pass]) as review_mock,
            ):
                self.module.generate_local_asset(
                    spec=spec,
                    checkpoint="sdxl.safetensors",
                    size="300x300",
                    max_attempts=2,
                    dry_run=False,
                    force=True,
                    gate_on_review=True,
                    review_url="http://127.0.0.1:18090/v1/chat/completions",
                    review_model="Nemotron",
                    review_timeout=1,
                    min_score=85,
                )

            self.assertEqual(submit_mock.call_count, 2)
            self.assertEqual(review_mock.call_count, 2)
            self.assertTrue(spec.out_path.exists())


if __name__ == "__main__":
    unittest.main()
