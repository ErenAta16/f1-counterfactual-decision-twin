"""Phase 5 minimal replay interface: one static HTML page per benchmark.

The roadmap calls for a "minimal replay interface" so an independent
reviewer can trace every claim in a decision back to data, a model
output, or an explicit assumption (`docs/PROJECT_PLAN.md`'s Phase 5 exit
criterion). This module renders exactly that, as a single self-contained
HTML file with no server and no JavaScript framework — consistent with
this project's Phase 3 decision to substitute a seeded CLI command for a
notebook rather than add UI tooling this project does not otherwise use.

The page has three parts, stacked so a reader moves from raw evidence to
conclusion in the same order this project's pipeline computes them:

1. The real per-lap track-status timeline (observed — Phase 1 data,
   Safety Car/VSC episodes from `apexmind.safety_car`), with the chosen
   strategy's compound stints aligned underneath it.
2. The evidence ledger (Phase 5), each item tagged observed / inferred /
   simulated.
3. The cited explanation text itself, with each citation's evidence link
   visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from apexmind.safety_car import SafetyCarEpisode

TRACK_STATUS_COLOR = "#3ecf8e"
EPISODE_COLORS = {"SC": "#e0a83e", "VSC": "#e8c876"}
COMPOUND_COLORS = {
    "SOFT": "#d64545",
    "MEDIUM": "#e0b23e",
    "HARD": "#e7ecf2",
    "INTERMEDIATE": "#3ecf8e",
    "WET": "#4fb3e8",
}
EVIDENCE_CLASS_COLORS = {"observed": "#4fb3e8", "inferred": "#e0a83e", "simulated": "#b47fe0"}

_STYLE = """
body { background:#0b0f14; color:#e7ecf2; font-family:Georgia,serif; margin:0; }
.page { max-width:880px; margin:0 auto; padding:40px 20px; }
h1 { font-family:ui-monospace,monospace; font-size:22px; }
.subtitle {
  color:#92a0b0; font-family:ui-monospace,monospace;
  font-size:13px; margin-bottom:28px;
}
.timeline-label {
  font-family:ui-monospace,monospace; font-size:12px;
  color:#92a0b0; margin:18px 0 4px;
}
.timeline {
  display:flex; height:22px; border:1px solid #232b35;
  border-radius:3px; overflow:hidden;
}
.segment { height:100%; }
.legend {
  font-family:ui-monospace,monospace; font-size:11px;
  color:#5c6a7a; margin-top:6px;
}
.evidence-row, .citation-row {
  font-family:ui-monospace,monospace; font-size:12.5px;
  padding:6px 0; border-bottom:1px solid #232b35;
}
.tag {
  display:inline-block; width:90px;
  text-transform:uppercase; letter-spacing:0.04em;
}
.evidence-title { color:#e7ecf2; }
.citation-row { color:#92a0b0; }
h2 { font-family:ui-monospace,monospace; font-size:15px; margin-top:36px; }
p { line-height:1.6; font-size:15.5px; }
"""


@dataclass(frozen=True)
class StintSegment:
    """One stint of the chosen strategy, in lap numbers, for the timeline overlay."""

    compound: str
    start_lap: int
    end_lap: int  # inclusive


def stints_to_segments(stints: tuple[dict[str, object], ...]) -> tuple[StintSegment, ...]:
    """Convert a decision report's stint list (compound, lap_count) into lap-number ranges."""

    segments: list[StintSegment] = []
    lap = 1
    for stint in stints:
        compound = str(stint["compound"])
        lap_count = int(stint["lap_count"])  # type: ignore[arg-type]
        segments.append(StintSegment(compound=compound, start_lap=lap, end_lap=lap + lap_count - 1))
        lap += lap_count
    return tuple(segments)


def _timeline_html(total_laps: int, segments: list[tuple[int, int, str, str]]) -> str:
    """Render one horizontal timeline as a row of proportionally-sized <div> cells."""

    cells = []
    for segment_start, segment_end, color, label in segments:
        width_pct = (segment_end - segment_start + 1) / total_laps * 100
        cells.append(
            f'<div class="segment" style="width:{width_pct:.4f}%;background:{color}" '
            f'title="{escape(label)}"></div>'
        )
    return "".join(cells)


def _safety_car_timeline_segments(
    total_laps: int, episodes: tuple[SafetyCarEpisode, ...]
) -> list[tuple[int, int, str, str]]:
    segments: list[tuple[int, int, str, str]] = []
    cursor = 1
    for episode in sorted(episodes, key=lambda e: e.start_lap):
        if episode.start_lap > cursor:
            segments.append(
                (cursor, episode.start_lap - 1, TRACK_STATUS_COLOR, "Green flag")
            )
        color = EPISODE_COLORS.get(episode.episode_type, "#999999")
        segments.append(
            (
                episode.start_lap,
                episode.end_lap,
                color,
                f"{episode.episode_type}, laps {episode.start_lap}-{episode.end_lap}",
            )
        )
        cursor = episode.end_lap + 1
    if cursor <= total_laps:
        segments.append((cursor, total_laps, TRACK_STATUS_COLOR, "Green flag"))
    return segments


def _stint_timeline_segments(segments: tuple[StintSegment, ...]) -> list[tuple[int, int, str, str]]:
    return [
        (
            segment.start_lap,
            segment.end_lap,
            COMPOUND_COLORS.get(segment.compound, "#999999"),
            f"{segment.compound}, laps {segment.start_lap}-{segment.end_lap}",
        )
        for segment in segments
    ]


def build_replay_html(
    *,
    benchmark_id: str,
    total_laps: int,
    safety_car_episodes: tuple[SafetyCarEpisode, ...],
    chosen_strategy_name: str,
    chosen_segments: tuple[StintSegment, ...],
    evidence: tuple[dict[str, str], ...],
    explanation_text: str,
    citations: tuple[dict[str, object], ...],
) -> str:
    """Render the single-file replay page. Pure function: no file or network I/O."""

    track_segments = _safety_car_timeline_segments(total_laps, safety_car_episodes)
    stint_segments = _stint_timeline_segments(chosen_segments)

    evidence_rows = "".join(
        f'<div class="evidence-row">'
        f'<span class="tag" style="color:'
        f'{EVIDENCE_CLASS_COLORS.get(item["evidence_class"], "#999")}">'
        f'{escape(item["evidence_class"])}</span>'
        f'<span class="evidence-title">{escape(item["title"])}</span>'
        f"</div>"
        for item in evidence
    )

    citation_rows = "".join(
        f'<div class="citation-row">"{escape(str(citation["text"]))}" '
        f'&rarr; {escape(", ".join(str(i) for i in citation["evidence_ids"]))}</div>'
        for citation in citations
    )

    explanation_html = "".join(
        f"<p>{escape(paragraph)}</p>" for paragraph in explanation_text.split("\n\n") if paragraph
    )

    subtitle = f"{total_laps} laps &middot; chosen strategy: {escape(chosen_strategy_name)}"
    sc_legend = (
        "green = green flag &middot; amber = Safety Car / VSC "
        "(real episodes extracted from race-control messages)"
    )
    citations_html = citation_rows or '<p class="legend">No citations available.</p>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Replay: {escape(benchmark_id)}</title>
<style>
{_STYLE}
</style>
</head>
<body>
<div class="page">
  <h1>Race replay: {escape(benchmark_id)}</h1>
  <div class="subtitle">{subtitle}</div>

  <div class="timeline-label">Track status (observed race-control data)</div>
  <div class="timeline">{_timeline_html(total_laps, track_segments)}</div>
  <div class="legend">{sc_legend}</div>

  <div class="timeline-label">Chosen strategy: {escape(chosen_strategy_name)}</div>
  <div class="timeline">{_timeline_html(total_laps, stint_segments)}</div>
  <div class="legend">red = SOFT &middot; gold = MEDIUM &middot; white = HARD</div>

  <h2>Evidence ledger</h2>
  {evidence_rows}

  <h2>Explanation</h2>
  {explanation_html}

  <h2>Citations</h2>
  {citations_html}
</div>
</body>
</html>
"""
