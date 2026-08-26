import base64
import hashlib
import re

from yoto.application.auth import build_authorize_url, pkce_pair


def test_verifier_is_urlsafe_and_long_enough():
    verifier, _ = pkce_pair()
    assert re.fullmatch(r"[A-Za-z0-9_-]{43,128}", verifier)


def test_challenge_is_s256_of_verifier():
    verifier, challenge = pkce_pair()
    digest = hashlib.sha256(verifier.encode()).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert challenge == expected


def test_pairs_are_unique():
    assert pkce_pair() != pkce_pair()


def test_build_authorize_url_contains_required_params():
    url = build_authorize_url(
        auth_url="https://login.example",
        audience="https://api.example",
        client_id="cid",
        scopes="openid offline_access",
        redirect_uri="http://127.0.0.1:8787/callback",
        state="st4te",
        challenge="ch4llenge",
    )
    assert url.startswith("https://login.example/authorize?")
    for fragment in [
        "audience=https%3A%2F%2Fapi.example",
        "scope=openid+offline_access",
        "response_type=code",
        "client_id=cid",
        "redirect_uri=http%3A%2F%2F127.0.0.1%3A8787%2Fcallback",
        "state=st4te",
        "code_challenge=ch4llenge",
        "code_challenge_method=S256",
    ]:
        assert fragment in url
