from apexmind.replay import StintSegment, build_replay_html, stints_to_segments
from apexmind.safety_car import SafetyCarEpisode


def test_stints_to_segments_converts_lap_counts_to_lap_ranges() -> None:
    stints = (
        {"compound": "MEDIUM", "lap_count": 20},
        {"compound": "SOFT", "lap_count": 37},
    )

    segments = stints_to_segments(stints)

    assert segments == (
        StintSegment(compound="MEDIUM", start_lap=1, end_lap=20),
        StintSegment(compound="SOFT", start_lap=21, end_lap=57),
    )


def test_build_replay_html_includes_race_and_evidence_content() -> None:
    html = build_replay_html(
        benchmark_id="bahrain-2024",
        total_laps=57,
        safety_car_episodes=(SafetyCarEpisode(episode_type="SC", start_lap=20, end_lap=22),),
        chosen_strategy_name="optimiser (medium20/soft37)",
        chosen_segments=(
            StintSegment(compound="MEDIUM", start_lap=1, end_lap=20),
            StintSegment(compound="SOFT", start_lap=21, end_lap=57),
        ),
        evidence=(
            {"id": "regulation", "title": "Article B6.3.6", "evidence_class": "observed"},
            {"id": "chosen_strategy", "title": "Optimiser's plan", "evidence_class": "inferred"},
        ),
        explanation_text="Paragraph one.\n\nParagraph two.",
        citations=(
            {"text": "Article B6.3.6 requires two compounds", "evidence_ids": ["regulation"]},
        ),
    )

    assert "bahrain-2024" in html
    assert "57 laps" in html
    assert "optimiser (medium20/soft37)" in html
    assert "SC, laps 20-22" in html
    assert "Article B6.3.6" in html
    assert "Paragraph one." in html
    assert "Paragraph two." in html
    assert "requires two compounds" in html
    # Every segment's width is a real percentage of the race distance, not
    # a placeholder -- the SOFT stint (37 of 57 laps) should be the widest.
    assert "64.9123%" in html  # 37 / 57 * 100, to 4 decimal places


def test_build_replay_html_escapes_untrusted_text() -> None:
    html = build_replay_html(
        benchmark_id="bahrain-2024",
        total_laps=10,
        safety_car_episodes=(),
        chosen_strategy_name="<script>alert(1)</script>",
        chosen_segments=(StintSegment(compound="SOFT", start_lap=1, end_lap=10),),
        evidence=(),
        explanation_text="fine",
        citations=(),
    )

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_build_replay_html_handles_no_safety_car_episodes() -> None:
    html = build_replay_html(
        benchmark_id="bahrain-2024",
        total_laps=10,
        safety_car_episodes=(),
        chosen_strategy_name="1-stop",
        chosen_segments=(StintSegment(compound="SOFT", start_lap=1, end_lap=10),),
        evidence=(),
        explanation_text="fine",
        citations=(),
    )

    assert "100.0000%" in html
