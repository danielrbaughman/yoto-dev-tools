import json

from yoto.adapters.mqtt import topics


def test_topic_builders_have_no_leading_slash():
    assert (
        topics.command_topic("dev1", "volume/set") == "device/dev1/command/volume/set"
    )
    assert topics.events_topic("dev1") == "device/dev1/data/events"
    assert topics.status_topic("dev1") == "device/dev1/data/status"
    assert topics.response_topic("dev1") == "device/dev1/response"


def test_ack_matches_via_req_body_echo():
    # Real v2.23.3 firmware echoes the exact request body.
    ack = topics.parse_ack(
        b'{"status":{"set-volume":"OK","req_body":"{\\"volume\\": 4}"}}'
    )
    assert ack is not None
    assert topics.ack_matches(ack, "volume/set", '{"volume": 4}')
    assert not topics.ack_matches(ack, "volume/set", '{"volume": 9}')


def test_ack_matches_falls_back_to_resource_name_variants():
    from yoto.domain.player import CommandAck

    # docs-style bare resource
    assert topics.ack_matches(
        CommandAck(resource="volume", ok=True), "volume/set", "{}"
    )
    # observed inverted verb-noun form
    assert topics.ack_matches(
        CommandAck(resource="set-volume", ok=True), "volume/set", "{}"
    )
    # observed literal command form
    assert topics.ack_matches(
        CommandAck(resource="status/request", ok=True), "status/request", "{}"
    )
    # observed slash->dash form with EMPTY req_body echo (real card/stop ack)
    stop_ack = topics.parse_ack(b'{"status":{"card-stop":"OK","req_body":""}}')
    assert stop_ack is not None
    assert topics.ack_matches(stop_ack, "card/stop", "{}")
    # unrelated resource does not match
    assert not topics.ack_matches(
        CommandAck(resource="set-volume", ok=True), "card/pause", "{}"
    )


def test_parse_ack_regular_command():
    payload = json.dumps({"status": {"volume": "OK", "req_body": "{}"}}).encode()
    ack = topics.parse_ack(payload)
    assert ack is not None
    assert ack.resource == "volume"
    assert ack.ok is True
    assert ack.req_body == "{}"


def test_parse_ack_status_doubled_key_and_fail():
    payload = json.dumps({"status": {"status": "FAIL"}}).encode()
    ack = topics.parse_ack(payload)
    assert ack is not None
    assert ack.resource == "status"
    assert ack.ok is False


def test_parse_ack_garbage_returns_none():
    assert topics.parse_ack(b"not json") is None
    assert topics.parse_ack(b"{}") is None
    assert topics.parse_ack(json.dumps({"status": {"req_body": "x"}}).encode()) is None


def test_parse_status_unwraps_inner_object():
    payload = json.dumps(
        {"status": {"batteryLevel": 87, "charging": 1, "fwVersion": "2.1.0", "als": 3}}
    ).encode()
    status = topics.parse_status(payload)
    assert status.battery_level == 87
    assert status.charging == 1
    assert status.fw_version == "2.1.0"
    assert status.to_api()["als"] == 3  # unknown field kept


def test_parse_event():
    payload = json.dumps(
        {
            "cardId": "abc12",
            "chapterKey": "01",
            "trackTitle": "The Moon",
            "position": 12,
            "trackLength": 185,
            "playbackStatus": "playing",
            "volume": 8,
            "source": "remote",
        }
    ).encode()
    event = topics.parse_event(payload)
    assert event.card_id == "abc12"
    assert event.playback_status == "playing"
    assert event.track_length == 185


def test_parsers_tolerate_junk():
    assert topics.parse_status(b"").battery_level is None
    assert topics.parse_event(b"[1,2]").card_id is None
