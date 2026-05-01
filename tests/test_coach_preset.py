"""Coach preset YAML loading and turn extraction."""

from pathlib import Path

from harness.coach_preset import coach_turn_from_preset, load_coach_preset


def test_load_preset_and_turn(tmp_path: Path):
    p = tmp_path / "p.yaml"
    p.write_text(
        """
id: test_preset
turns:
  "1":
    narrative: hello
    channel_posts:
      - "Short line"
      - content: "Second"
        channel: "#x"
    vital_nudges:
      - character_id: alex
        vital_name: stress
        delta: -2
""",
        encoding="utf-8",
    )
    data = load_coach_preset(p)
    assert data["id"] == "test_preset"
    out = coach_turn_from_preset(data, 1, default_channel="#war-room")
    assert "hello" in out.narrative
    assert len(out.channel_posts) == 2
    assert out.channel_posts[0].channel == "#war-room"
    assert out.channel_posts[1].channel == "#x"
    assert len(out.vital_nudges) == 1

    empty = coach_turn_from_preset(data, 99, default_channel="#war-room")
    assert "no entry" in empty.narrative.lower()
