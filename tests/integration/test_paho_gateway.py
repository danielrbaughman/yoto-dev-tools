"""PahoPlayerGateway against a fake paho client (no sockets)."""

import json

import pytest

from tests.fakes.fake_mqtt import FakeMqtt, FakeReasonCode
from yoto.adapters.mqtt.paho_gateway import PahoPlayerGateway
from yoto.domain.errors import AuthRequiredError, MqttError, OperationTimeout


class StaticProvider:
    def access_token(self) -> str:
        return "jwt-token"

    def on_unauthorized(self) -> str:
        raise AssertionError("not expected")


def make_gateway(harness: FakeMqtt, **kwargs) -> PahoPlayerGateway:
    return PahoPlayerGateway(
        host="broker.test",
        authorizer="PublicJWTAuthorizer",
        token_provider=StaticProvider(),
        client_factory=harness.factory,
        **kwargs,
    )


def test_connect_uses_the_documented_recipe():
    harness = FakeMqtt()
    gateway = make_gateway(harness)
    gateway.connect("dev123")
    client = harness.clients[0]
    assert client.init_kwargs["client_id"] == "DASHdev123"
    assert client.init_kwargs["transport"] == "websockets"
    assert client.ws_path == "/mqtt"
    assert client.tls is True
    assert client.username == "dev123?x-amz-customauthorizer-name=PublicJWTAuthorizer"
    assert client.password == "jwt-token"
    assert client.connect_args == ("broker.test", 443)
    assert client.connect_kwargs == {"keepalive": 300}
    assert set(client.subscribed) == {
        "device/dev123/data/events",
        "device/dev123/data/status",
        "device/dev123/response",
    }
    gateway.close()
    assert client.loop_stopped and client.disconnected


def test_send_waits_for_matching_ack():
    harness = FakeMqtt()
    harness.respond(
        "device/dev123/command/volume/set",
        "device/dev123/response",
        json.dumps({"status": {"volume": "OK", "req_body": '{"volume": 8}'}}).encode(),
    )
    gateway = make_gateway(harness)
    gateway.connect("dev123")
    ack = gateway.send("dev123", "volume/set", {"volume": 8}, timeout=1.0)
    assert ack.ok is True
    assert ack.resource == "volume"
    topic, payload, qos = harness.clients[0].published[-1]
    assert topic == "device/dev123/command/volume/set"
    assert json.loads(payload) == {"volume": 8}
    assert qos == 1


def test_send_ignores_unrelated_acks_and_times_out():
    harness = FakeMqtt()
    harness.respond(
        "device/dev123/command/card/pause",
        "device/dev123/response",
        json.dumps({"status": {"volume": "OK"}}).encode(),  # wrong resource
    )
    gateway = make_gateway(harness)
    gateway.connect("dev123")
    with pytest.raises(OperationTimeout, match="card/pause"):
        gateway.send("dev123", "card/pause", {}, timeout=0.4)


def test_request_status_parses_report():
    harness = FakeMqtt()
    harness.respond(
        "device/dev123/command/status/request",
        "device/dev123/data/status",
        json.dumps({"status": {"batteryLevel": 55, "charging": 0}}).encode(),
    )
    gateway = make_gateway(harness)
    gateway.connect("dev123")
    status = gateway.request_status("dev123", timeout=1.0)
    assert status.battery_level == 55


def test_events_stream_yields_parsed_events():
    harness = FakeMqtt()
    gateway = make_gateway(harness)
    gateway.connect("dev123")
    client = harness.clients[0]
    client.deliver(
        "device/dev123/data/events",
        json.dumps({"cardId": "abc12", "playbackStatus": "playing"}).encode(),
    )
    event = next(gateway.events("dev123"))
    assert event.card_id == "abc12"
    # the stream primes the device with an events request
    assert client.published[0][0] == "device/dev123/command/events/request"


def test_not_authorized_maps_to_auth_required_with_scope_hint():
    harness = FakeMqtt()
    harness.connect_rc = FakeReasonCode(failure=True, text="Not authorized")
    with pytest.raises(AuthRequiredError, match="family:devices:control"):
        make_gateway(harness).connect("dev123")


def test_other_connack_failures_are_mqtt_errors():
    harness = FakeMqtt()
    harness.connect_rc = FakeReasonCode(failure=True, text="Server unavailable")
    with pytest.raises(MqttError, match="Server unavailable"):
        make_gateway(harness).connect("dev123")


def test_connect_timeout_when_no_connack():
    harness = FakeMqtt()
    harness.fire_on_connect = False
    with pytest.raises(MqttError, match="Timed out"):
        make_gateway(harness, connect_timeout=0.2).connect("dev123")


def test_connect_socket_failure_is_mqtt_error():
    harness = FakeMqtt()

    def broken_factory(**kwargs):
        client = harness.factory(**kwargs)

        def refuse(*args, **kw):
            raise OSError("no route to host")

        client.connect = refuse  # ty: ignore[invalid-assignment]
        return client

    gateway = PahoPlayerGateway(
        host="broker.test",
        authorizer="PublicJWTAuthorizer",
        token_provider=StaticProvider(),
        client_factory=broken_factory,
    )
    with pytest.raises(MqttError, match="Cannot reach"):
        gateway.connect("dev123")


def test_status_timeout_asks_if_player_is_online():
    harness = FakeMqtt()  # no responder scripted: the report never arrives
    gateway = make_gateway(harness)
    gateway.connect("dev123")
    with pytest.raises(OperationTimeout, match="online"):
        gateway.request_status("dev123", timeout=0.3)


def test_commands_before_connect_are_mqtt_errors():
    gateway = make_gateway(FakeMqtt())
    with pytest.raises(MqttError, match="Not connected"):
        gateway.request_status("dev123", timeout=0.1)
