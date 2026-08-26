"""PlayerGateway implementation over paho-mqtt (AWS IoT websockets).

Connection recipe (from yoto.dev players-mqtt docs):
- wss to the AWS IoT broker, port 443, websocket path /mqtt
- client id  DASH{deviceId}
- username   {deviceId}?x-amz-customauthorizer-name=PublicJWTAuthorizer
- password   a Yoto access token with the family:devices:control scope
"""

import contextlib
import json
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt import MQTTException

from yoto.adapters.mqtt import topics
from yoto.application.ports import TokenProvider
from yoto.domain.errors import AuthRequiredError, MqttError, OperationTimeout
from yoto.domain.player import CommandAck, PlaybackEvent, PlayerStatus

logger = logging.getLogger("yoto.mqtt")

# Returns an mqtt.Client in production; typed loosely so tests can inject a
# structural fake through the same seam.
ClientFactory = Callable[..., Any]

_POLL_SECONDS = 0.25


def _default_client_factory(**kwargs: Any) -> mqtt.Client:
    return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, **kwargs)


def _is_failure(reason_code: object) -> bool:
    is_failure = getattr(reason_code, "is_failure", None)
    if is_failure is not None:
        return bool(is_failure)
    return bool(reason_code)


class PahoPlayerGateway:
    def __init__(
        self,
        *,
        host: str,
        authorizer: str,
        token_provider: TokenProvider,
        client_factory: ClientFactory | None = None,
        connect_timeout: float = 15.0,
    ) -> None:
        self._host = host
        self._authorizer = authorizer
        self._token_provider = token_provider
        self._client_factory = client_factory or _default_client_factory
        self._connect_timeout = connect_timeout
        self._client: mqtt.Client | None = None
        self._connected = threading.Event()
        self._connect_reason: object | None = None
        self._events: queue.Queue[bytes] = queue.Queue()
        self._status: queue.Queue[bytes] = queue.Queue()
        self._responses: queue.Queue[bytes] = queue.Queue()

    def connect(self, device_id: str) -> None:
        token = self._token_provider.access_token()
        client = self._client_factory(
            client_id=f"DASH{device_id}",
            transport="websockets",
            protocol=mqtt.MQTTv311,
        )
        client.ws_set_options(path="/mqtt")
        client.tls_set()
        client.username_pw_set(
            f"{device_id}?x-amz-customauthorizer-name={self._authorizer}", token
        )
        routes = {
            topics.events_topic(device_id): self._events,
            topics.status_topic(device_id): self._status,
            topics.response_topic(device_id): self._responses,
        }

        def on_connect(
            _client: mqtt.Client,
            _userdata: object,
            _flags: object,
            reason_code: object,
            _properties: object = None,
        ) -> None:
            self._connect_reason = reason_code
            if not _is_failure(reason_code):
                for topic in routes:
                    _client.subscribe(topic)
            self._connected.set()

        def on_message(
            _client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage
        ) -> None:
            target = routes.get(message.topic)
            logger.debug("mqtt <- %s %s", message.topic, message.payload[:200])
            if target is not None:
                target.put(message.payload)

        client.on_connect = on_connect
        client.on_message = on_message
        self._client = client
        try:
            client.connect(self._host, 443, keepalive=300)
        except (OSError, mqtt.WebsocketConnectionError) as exc:
            raise MqttError(f"Cannot reach the MQTT broker: {exc}") from exc
        client.loop_start()
        if not self._connected.wait(self._connect_timeout):
            self.close()
            raise MqttError(f"Timed out connecting to the MQTT broker ({self._host}).")
        reason = self._connect_reason
        if reason is not None and _is_failure(reason):
            self.close()
            if "authoriz" in str(reason).lower():
                raise AuthRequiredError(
                    "MQTT authentication failed. Player control needs the "
                    "family:devices:control scope — check your client's scopes "
                    "and run `yoto auth login` again."
                )
            raise MqttError(f"MQTT connect failed: {reason}")

    def close(self) -> None:
        if self._client is not None:
            self._client.loop_stop()
            with contextlib.suppress(OSError, MQTTException):
                self._client.disconnect()
            self._client = None

    def send(
        self, device_id: str, command: str, payload: dict[str, Any], *, timeout: float
    ) -> CommandAck:
        client = self._require_client()
        _drain(self._responses)
        resource = topics.command_resource(command)
        topic = topics.command_topic(device_id, command)
        body = json.dumps(payload)
        logger.debug("mqtt -> %s %s", topic, body)
        client.publish(topic, body, qos=1)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise OperationTimeout(
                    f"No acknowledgement for '{command}' within {timeout:.0f}s. "
                    "Is the player online (and not in Bluetooth mode)?"
                )
            try:
                raw = self._responses.get(timeout=min(_POLL_SECONDS, remaining))
            except queue.Empty:
                continue
            ack = topics.parse_ack(raw)
            if ack is not None and ack.resource == resource:
                return ack

    def request_status(self, device_id: str, *, timeout: float) -> PlayerStatus:
        client = self._require_client()
        _drain(self._status)
        client.publish(topics.command_topic(device_id, "status/request"), "{}", qos=1)
        try:
            raw = self._status.get(timeout=timeout)
        except queue.Empty:
            raise OperationTimeout(
                f"No status report within {timeout:.0f}s. Is the player online?"
            ) from None
        return topics.parse_status(raw)

    def events(self, device_id: str) -> Iterator[PlaybackEvent]:
        client = self._require_client()
        client.publish(topics.command_topic(device_id, "events/request"), "{}", qos=1)
        while True:
            try:
                raw = self._events.get(timeout=1.0)  # short poll keeps Ctrl-C snappy
            except queue.Empty:
                continue
            yield topics.parse_event(raw)

    def _require_client(self) -> mqtt.Client:
        if self._client is None:
            raise MqttError("Not connected — call connect() first.")
        return self._client


def _drain(target: queue.Queue[bytes]) -> None:
    while True:
        try:
            target.get_nowait()
        except queue.Empty:
            return
