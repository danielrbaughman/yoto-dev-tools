"""Composition root: the only place adapters are wired together."""

from collections.abc import Callable

import httpx

from yoto.adapters.http.auth_httpx import BearerAuth
from yoto.adapters.http.client import ApiHttp
from yoto.adapters.http.content_api import HttpContentGateway
from yoto.adapters.http.devices_api import HttpDeviceGateway
from yoto.adapters.http.icons_api import HttpIconGateway
from yoto.adapters.http.library_api import HttpFamilyImageGateway, HttpLibraryGateway
from yoto.adapters.http.media_api import HttpMediaGateway
from yoto.adapters.http.oauth import Auth0Gateway
from yoto.adapters.storage.token_store import FileTokenStore
from yoto.adapters.system import SystemClock, WebBrowserOpener
from yoto.application.auth import AuthSession, LoginFlow, StaticTokenProvider
from yoto.application.ports import PlayerGateway, TokenProvider
from yoto.settings import YotoSettings


class Services:
    """Wired adapters + shared config, handed to the CLI layer."""

    def __init__(self, settings: YotoSettings | None = None) -> None:
        self.settings = settings or YotoSettings()
        self.clock = SystemClock()
        self.browser = WebBrowserOpener()
        self.token_store = FileTokenStore(self.settings.tokens_path)
        self.auth_gateway = Auth0Gateway(
            auth_url=self.settings.auth_url,
            client_id=self.settings.client_id,
            clock=self.clock,
        )
        self.token_provider: TokenProvider = (
            StaticTokenProvider(self.settings.access_token)
            if self.settings.access_token
            else AuthSession(self.token_store, self.auth_gateway, self.clock)
        )
        api_client = httpx.Client(
            base_url=self.settings.api_url,
            timeout=httpx.Timeout(self.settings.timeout, connect=10.0),
            auth=BearerAuth(self.token_provider),
            headers={"Accept": "application/json"},
        )
        self._http = ApiHttp(api_client, sleep=self.clock.sleep)
        # Presigned S3 PUTs must not carry an Authorization header.
        self._bare_client = httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0))
        self.content = HttpContentGateway(self._http)
        self.media = HttpMediaGateway(self._http, self._bare_client)
        self.icons = HttpIconGateway(self._http)
        self.devices = HttpDeviceGateway(self._http)
        self.library = HttpLibraryGateway(self._http)
        self.family_images = HttpFamilyImageGateway(self._http)
        self._player: PlayerGateway | None = None

    def login_flow(self, notify: Callable[[str], None]) -> LoginFlow:
        from yoto.adapters.http.loopback import LoopbackCodeReceiver

        return LoginFlow(
            auth_gateway=self.auth_gateway,
            receiver=LoopbackCodeReceiver(self.settings.redirect_port),
            browser=self.browser,
            store=self.token_store,
            auth_url=self.settings.auth_url,
            audience=self.settings.api_url,
            client_id=self.settings.client_id,
            scopes=self.settings.scopes,
            notify=notify,
        )

    @property
    def player(self) -> PlayerGateway:
        """Built lazily so REST-only commands never touch MQTT."""
        if self._player is None:
            from yoto.adapters.mqtt.paho_gateway import PahoPlayerGateway

            self._player = PahoPlayerGateway(
                host=self.settings.mqtt_host,
                authorizer=self.settings.mqtt_authorizer,
                token_provider=self.token_provider,
            )
        return self._player

    def close(self) -> None:
        if self._player is not None:
            self._player.close()
        self._http.close()
        self._bare_client.close()
        self.auth_gateway.close()


def build_services(settings: YotoSettings | None = None) -> Services:
    return Services(settings)
