"""A fake paho client for PahoPlayerGateway tests (no sockets).

Usage: create a FakeMqtt, pass fake.factory as client_factory, script
responses with fake.respond(publish_topic, respond_topic, payload).
"""

from typing import Any


class FakeReasonCode:
    def __init__(self, failure: bool = False, text: str = "Success") -> None:
        self.is_failure = failure
        self._text = text

    def __str__(self) -> str:
        return self._text


class FakeMessage:
    def __init__(self, topic: str, payload: bytes) -> None:
        self.topic = topic
        self.payload = payload


class FakeMqtt:
    def __init__(self) -> None:
        self.clients: list[FakePahoClient] = []
        self.connect_rc = FakeReasonCode()
        self.fire_on_connect = True  # False simulates a connect that hangs
        # (publish_topic, respond_topic, payload_bytes)
        self.responders: list[tuple[str, str, bytes]] = []

    def respond(self, publish_topic: str, respond_topic: str, payload: bytes) -> None:
        self.responders.append((publish_topic, respond_topic, payload))

    def factory(self, **kwargs: Any) -> FakePahoClient:
        client = FakePahoClient(self, **kwargs)
        self.clients.append(client)
        return client


class FakePahoClient:
    def __init__(self, harness: FakeMqtt, **kwargs: Any) -> None:
        self.harness = harness
        self.init_kwargs = kwargs
        self.on_connect: Any = None
        self.on_message: Any = None
        self.ws_path: str | None = None
        self.tls = False
        self.username: str | None = None
        self.password: str | None = None
        self.connect_args: tuple[Any, ...] | None = None
        self.connect_kwargs: dict[str, Any] = {}
        self.subscribed: list[str] = []
        self.published: list[tuple[str, Any, int]] = []
        self.loop_started = False
        self.loop_stopped = False
        self.disconnected = False

    def ws_set_options(self, path: str) -> None:
        self.ws_path = path

    def tls_set(self) -> None:
        self.tls = True

    def username_pw_set(self, username: str, password: str) -> None:
        self.username = username
        self.password = password

    def connect(self, *args: Any, **kwargs: Any) -> None:
        self.connect_args = args
        self.connect_kwargs = kwargs

    def loop_start(self) -> None:
        self.loop_started = True
        if self.harness.fire_on_connect and self.on_connect is not None:
            self.on_connect(self, None, {}, self.harness.connect_rc, None)

    def subscribe(self, topic: str) -> None:
        self.subscribed.append(topic)

    def publish(self, topic: str, payload: Any = None, qos: int = 0) -> None:
        self.published.append((topic, payload, qos))
        for match, respond_topic, respond_payload in self.harness.responders:
            if match == topic and self.on_message is not None:
                self.on_message(self, None, FakeMessage(respond_topic, respond_payload))

    def deliver(self, topic: str, payload: bytes) -> None:
        assert self.on_message is not None
        self.on_message(self, None, FakeMessage(topic, payload))

    def loop_stop(self) -> None:
        self.loop_stopped = True

    def disconnect(self) -> None:
        self.disconnected = True
