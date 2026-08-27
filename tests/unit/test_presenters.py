"""Presenter smoke tests: human rendering never crashes and shows key fields."""

from tests.conftest import load_fixture
from yoto.adapters.cli import presenters
from yoto.adapters.cli.output import stdout_console
from yoto.domain.content import Card
from yoto.domain.player import PlaybackEvent, PlayerStatus


def render(renderable) -> str:
    with stdout_console.capture() as capture:
        stdout_console.print(renderable)
    return capture.get()


def test_show_card_renders_chapters_and_metadata(capsys):
    card = Card.model_validate(load_fixture("card_full.json"))
    presenters.show_card(card)
    out = capsys.readouterr().out
    assert card.title in out


def test_show_status_renders_key_fields(capsys):
    presenters.show_status(
        PlayerStatus(volume=8, user_volume=8, battery_level=55, charging=0)
    )
    out = capsys.readouterr().out
    assert "55" in out


def test_event_row_and_table_render():
    event = PlaybackEvent(
        card_id="abc12",
        track_title="Moon",
        playback_status="playing",
        position=3,
        track_length=60,
        volume=8,
    )
    table = presenters.event_table([presenters.event_row(event)])
    text = render(table)
    assert "Moon" in text and "playing" in text


def test_event_line_handles_sparse_events():
    text = render(presenters.event_line(PlaybackEvent()))
    assert text.strip()  # renders something even with every field missing
