import json

from yoto.adapters.mqtt import topics


def test_topic_builders_have_no_leading_slash():
    assert (
        topics.command_topic("dev1", "volume/set") == "device/dev1/command/volume/set"
    )
    assert topics.events_topic("dev1") == "device/dev1/data/events"
    assert topics.status_topic("dev1") == "device/dev1/data/status"
    assert topics.response_topic("dev1") == "device/dev1/response"


def test_command_resource():
    assert topics.command_resource("volume/set") == "volume"
    assert topics.command_resource("card/start") == "card"
    assert topics.command_resource("reboot") == "reboot"


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
