"""LoopbackCodeReceiver against a real http.server on an ephemeral port."""

import httpx
import pytest

from yoto.adapters.http.loopback import LoopbackCodeReceiver
from yoto.domain.errors import OAuthFlowError, OperationTimeout


@pytest.fixture
def receiver():
    instance = LoopbackCodeReceiver(port=0)  # ephemeral port
    yield instance
    instance.close()


def test_receives_code_and_validates_state(receiver):
    uri = receiver.start()
    response = httpx.get(uri, params={"code": "c0de", "state": "st"})
    assert response.status_code == 200
    assert "close this tab" in response.text
    assert receiver.wait_for_code(expected_state="st", timeout=5.0) == "c0de"


def test_state_mismatch_raises(receiver):
    uri = receiver.start()
    httpx.get(uri, params={"code": "c0de", "state": "evil"})
    with pytest.raises(OAuthFlowError, match="state mismatch"):
        receiver.wait_for_code(expected_state="expected", timeout=5.0)


def test_error_callback_raises_with_description(receiver):
    uri = receiver.start()
    response = httpx.get(
        uri,
        params={
            "error": "access_denied",
            "error_description": "User cancelled",
            "state": "st",
        },
    )
    assert response.status_code == 200
    with pytest.raises(OAuthFlowError, match="access_denied") as excinfo:
        receiver.wait_for_code(expected_state="st", timeout=5.0)
    assert excinfo.value.error == "access_denied"


def test_missing_code_raises(receiver):
    uri = receiver.start()
    httpx.get(uri, params={"state": "st"})
    with pytest.raises(OAuthFlowError, match="no authorization code"):
        receiver.wait_for_code(expected_state="st", timeout=5.0)


def test_other_paths_are_404_and_ignored(receiver):
    uri = receiver.start()
    root = uri.rsplit("/", 1)[0]
    assert httpx.get(f"{root}/favicon.ico").status_code == 404
    with pytest.raises(OperationTimeout):
        receiver.wait_for_code(expected_state="st", timeout=0.2)


def test_timeout(receiver):
    receiver.start()
    with pytest.raises(OperationTimeout, match="No login callback"):
        receiver.wait_for_code(expected_state="st", timeout=0.2)
