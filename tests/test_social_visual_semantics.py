from __future__ import annotations

import json
import hashlib
from pathlib import Path

from PIL import ImageChops, ImageStat

from scripts.render_social_animations import build_render_plan, draw_frame, scene_plan


ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = json.loads((ROOT / "data" / "social_dialogues.json").read_text())
ITEMS = {(item.story_id, item.turn_id): item for item in build_render_plan(DOCUMENT, ROOT)}


def plan(story: str, turn: str, phase: float = 0.5) -> dict:
    return scene_plan(ITEMS[(story, turn)], phase)


def test_toy_requests_preserve_ownership_until_acceptance() -> None:
    assert plan("toy_car", "request")["owner"] == "leo"
    assert plan("toy_car", "request")["requester_hand"] == "ask"
    assert plan("toy_car", "accept", 0.0)["owner"] == "leo"
    assert plan("toy_car", "accept", 1.0)["owner"] == "mia"
    assert plan("toy_car", "next_turn")["future_turn"] == "mia"


def test_joining_and_building_show_two_active_participants() -> None:
    assert set(plan("join_play", "thanks")["active_children"]) == {"mia", "leo"}
    assert plan("join_play", "thanks")["build_shape"] == "shared_tower"
    assert plan("accept_yes", "thanks")["build_shape"] == "bridge"


def test_waiting_and_next_turn_are_not_drawn_as_immediate_transfer() -> None:
    accepted = plan("take_turns", "accept", 1.0)
    assert accepted["owner"] == "leo"
    assert accepted["future_turn"] == "mia"
    assert plan("wait_calmly", "wait")["waiting_child"] == "leo"
    assert plan("next_turn", "decline")["queued_before"] == "mia"
    assert plan("borrow_toy", "thanks")["return_to"] == "leo"
    assert plan("take_turns", "decline")["busy_more_time"] == "leo"
    assert plan("take_turns", "thanks")["future_turn"] == "mia"
    assert plan("take_turns", "thanks")["confirmed_future_turn"] is True
    assert plan("wait_calmly", "setup")["fixed_equipment"] == "swing"
    assert plan("wait_calmly", "accept", 0.0)["seated_children"] == ["mia"]
    assert plan("wait_calmly", "accept", 1.0)["seated_children"] == ["leo"]
    assert plan("wait_calmly", "thanks")["seated_children"] == ["leo"]
    assert plan("next_turn", "thanks")["ready_child"] == "mia"
    assert plan("next_turn", "wait")["queued_before"] == "mia"


def test_sharing_and_alternatives_have_distinct_visible_results() -> None:
    assert plan("share_materials", "accept")["crayon_allocation"] == {"mia": 3, "leo": 3}
    assert plan("share_materials", "thanks")["highlight_color"] == "blue"
    assert plan("share_materials", "wait")["crayon_allocation"] == {"mia": 3, "leo": 3}
    assert plan("polite_no", "decline")["alternative"] == "book"
    assert plan("polite_no", "wait")["quiet_children"] == ["mia", "leo"]
    assert plan("accept_yes", "decline")["alternative"] == "drawing"
    assert plan("accept_yes", "wait")["alternative"] == "drawing"


def test_seating_and_personal_space_change_body_geometry() -> None:
    assert plan("accept_no", "setup")["seated_children"] == ["mia"]
    assert set(plan("accept_no", "accept")["seated_children"]) == {"mia", "leo"}
    assert plan("accept_no", "wait")["separate_seat"] == "leo"
    assert plan("personal_space", "accept", 1.0)["distance"] > plan("personal_space", "request")["distance"]


def test_seated_children_put_their_weight_on_the_seat_and_feet_below_it() -> None:
    bench_frame = draw_frame(ITEMS[("accept_no", "setup")], 18)
    swing_frame = draw_frame(ITEMS[("wait_calmly", "setup")], 18)
    pants = (49, 91, 154)

    # Bench seat top is y=330; seated legs must continue below it.
    assert bench_frame.getpixel((288, 360)) == pants
    # Swing seat is y=370; the rider's bent legs must continue below it.
    assert swing_frame.getpixel((318, 400)) == pants


def test_swing_has_a_fixed_overhead_frame_and_two_ropes() -> None:
    setup = draw_frame(ITEMS[("wait_calmly", "setup")], 18)
    accepted = draw_frame(ITEMS[("wait_calmly", "thanks")], 18)
    frame_color = (73, 80, 87)

    for image in (setup, accepted):
        assert image.getpixel((360, 100)) == frame_color
        assert image.getpixel((335, 205)) == frame_color
        assert image.getpixel((385, 205)) == frame_color
        assert image.getpixel((292, 370)) == (255, 146, 43)
        assert image.getpixel((428, 370)) == (255, 146, 43)


def test_help_prop_stays_with_the_child_who_requests_help() -> None:
    frame = draw_frame(ITEMS[("ask_for_help", "setup")], 18)
    mia_region = frame.crop((145, 285, 265, 430))
    leo_region = frame.crop((455, 285, 575, 430))
    jar_blue = (116, 192, 252)

    assert list(mia_region.get_flattened_data()).count(jar_blue) > 50
    assert list(leo_region.get_flattened_data()).count(jar_blue) == 0


def test_boundary_story_has_a_cause_stop_and_visible_relief() -> None:
    assert plan("please_stop", "setup")["intrusion"] is True
    assert plan("please_stop", "request")["boundary_hand"] == "mia"
    assert plan("please_stop", "accept", 1.0)["intrusion"] is False
    assert plan("please_stop", "decline", 1.0)["intrusion"] is False
    assert plan("please_stop", "thanks")["comfortable"] is True
    assert plan("please_stop", "accept")["accepted_stop"] is True
    assert plan("please_stop", "decline")["apology"] is True
    assert plan("please_stop", "thanks")["gratitude"] is True
    assert plan("please_stop", "wait")["relief"] is True


def test_help_and_repair_stories_show_action_not_only_final_state() -> None:
    assert plan("ask_for_help", "setup")["owner"] == "mia"
    assert plan("ask_for_help", "setup")["jar_open"] is False
    assert plan("ask_for_help", "accept", 0.0)["jar_open"] is False
    assert plan("ask_for_help", "accept", 1.0)["jar_open"] is True
    assert set(plan("offer_help", "accept", 0.5)["active_children"]) == {"mia", "leo"}
    assert plan("offer_help", "accept", 0.0)["blocks_state"] == "scattered"
    assert plan("offer_help", "accept", 1.0)["blocks_state"] == "stacked"
    assert plan("offer_help", "wait", 1.0)["blocks_state"] == "partial"
    assert plan("apologize", "setup", 0.0)["blocks_state"] == "stacked"
    assert plan("apologize", "setup", 1.0)["blocks_state"] == "scattered"


def test_play_and_work_outcomes_match_each_branch() -> None:
    assert plan("invite_friend", "accept")["ball_exchange"] is True
    assert plan("invite_friend", "decline")["alternative"] == "book"
    assert plan("invite_friend", "wait")["owner"] == "mia"
    assert plan("invite_friend", "wait")["alternative"] == "book"
    assert plan("work_together", "accept")["build_shape"] == "bridge"
    assert plan("work_together", "decline")["build_shape"] == "tower"
    assert plan("work_together", "wait")["passing_blocks"] is True


def test_reviewed_future_transfer_has_explicit_correct_direction() -> None:
    future = plan("toy_car", "next_turn")
    assert future["direction_from"] == "leo"
    assert future["direction_to"] == "mia"


def test_reviewed_crayon_branches_conserve_six_crayons() -> None:
    for turn in ("accept", "thanks", "wait"):
        allocation = plan("share_materials", turn)["crayon_allocation"]
        assert allocation == {"mia": 3, "leo": 3}
        assert sum(allocation.values()) == 6


def test_reviewed_highlight_keeps_leos_other_two_crayons_visible() -> None:
    state = plan("share_materials", "thanks")
    assert state["drawing_with_blue"] is True
    frame = draw_frame(ITEMS[("share_materials", "thanks")], 18)
    assert frame.getpixel((489, 380)) == (77, 171, 247)   # blue
    assert frame.getpixel((515, 380)) == (132, 94, 247)  # purple
    assert frame.getpixel((541, 380)) == (255, 146, 43)  # orange
    assert frame.getpixel((380, 360)) == (255, 255, 255)  # drawing paper
    assert frame.getpixel((420, 340)) == (77, 171, 247)   # visible blue mark


def test_reviewed_build_acceptances_show_progress_before_the_result() -> None:
    for story in ("accept_yes", "work_together"):
        assert plan(story, "accept", 0.0)["blocks_state"] == "scattered"
        assert plan(story, "accept", 0.5)["blocks_state"] == "partial"
        assert plan(story, "accept", 1.0)["blocks_state"] == "bridge"
        assert plan(story, "accept", 0.5)["joint_build"] is True
        start = draw_frame(ITEMS[(story, "accept")], 0)
        end = draw_frame(ITEMS[(story, "accept")], 35)
        assert start.getpixel((360, 267)) != end.getpixel((360, 267))


def test_reviewed_tag_acceptance_and_result_have_chase_motion() -> None:
    for turn in ("accept", "thanks"):
        state = plan("polite_no", turn, 0.5)
        assert state["motion"] == "chase"
        assert state["running_children"] == ["mia", "leo"]
        assert state["chaser"] == "leo"
        assert state["runner"] == "mia"
        assert state["chase_gap"] >= 160


def test_reviewed_stop_story_shows_the_unwanted_action_before_relief() -> None:
    for turn in ("setup", "request"):
        state = plan("please_stop", turn, 0.5)
        assert state["unwanted_action"] == "tower_interference"
        assert state["unwanted_actor"] == "leo"
    assert plan("please_stop", "accept", 1.0)["unwanted_action"] is None


def test_reviewed_personal_space_branch_preserves_continuity_and_book_owner() -> None:
    for turn in ("setup", "request", "accept", "thanks", "decline", "wait", "next_turn"):
        assert plan("personal_space", turn)["owner"] == "mia"
    assert plan("personal_space", "decline", 1.0)["distance"] == plan("personal_space", "wait", 0.0)["distance"]
    assert plan("personal_space", "wait", 1.0)["distance"] > plan("personal_space", "wait", 0.0)["distance"]


def test_reviewed_jar_help_has_joint_grip_and_decline_stays_closed() -> None:
    accepting = plan("ask_for_help", "accept", 0.5)
    assert accepting["joint_grip"] is True
    assert set(accepting["gripping_children"]) == {"mia", "leo"}
    assert plan("ask_for_help", "decline", 0.0)["jar_open"] is False
    assert plan("ask_for_help", "decline", 1.0)["jar_open"] is False


def test_reviewed_declined_help_shows_mia_making_independent_progress() -> None:
    assert plan("offer_help", "decline", 0.0)["blocks_state"] == "scattered"
    assert plan("offer_help", "decline", 1.0)["blocks_state"] == "partial"
    assert plan("offer_help", "decline", 0.5)["independent_builder"] == "mia"


def test_every_request_keeps_the_prop_stable_while_asking() -> None:
    for story in DOCUMENT["stories"]:
        start = plan(story["id"], "request", 0.0)
        end = plan(story["id"], "request", 1.0)
        assert start["owner"] == end["owner"], story["id"]
        assert start["requester_hand"] == "ask", story["id"]


def test_every_story_has_visually_distinct_branch_outcomes() -> None:
    for story in DOCUMENT["stories"]:
        accept = draw_frame(ITEMS[(story["id"], "accept")], 27)
        decline = draw_frame(ITEMS[(story["id"], "decline")], 27)
        positive = draw_frame(ITEMS[(story["id"], "thanks")], 27)
        respectful = draw_frame(ITEMS[(story["id"], "wait")], 27)

        branch_difference = sum(ImageStat.Stat(ImageChops.difference(accept, decline)).mean) / 3
        outcome_difference = sum(ImageStat.Stat(ImageChops.difference(positive, respectful)).mean) / 3
        assert branch_difference > 2.0, (story["id"], branch_difference)
        assert outcome_difference > 2.0, (story["id"], outcome_difference)


def test_every_turn_has_a_distinct_three_frame_visual_signature() -> None:
    signatures = set()
    for item in ITEMS.values():
        frames = b"".join(draw_frame(item, frame).tobytes() for frame in (0, 18, 35))
        signatures.add(hashlib.sha256(frames).hexdigest())

    assert len(signatures) == len(ITEMS) == 110
