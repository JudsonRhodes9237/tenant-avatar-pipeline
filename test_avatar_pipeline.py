import base64
import io
import json
from urllib.error import HTTPError

import pytest

from avatar_pipeline import AvatarRequest, InfraiClient, InfraiError, process_avatar


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self.payload = json.dumps(payload).encode()

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_tenant_avatar_is_square_and_ready():
    calls = []

    def opener(req):
        calls.append((req.method, req.full_url, json.loads(req.data)))
        if len(calls) == 1:
            return FakeResponse({"ok": True, "data": {"image": "upload-7"}, "error": None, "metadata": {}})
        return FakeResponse({"ok": True, "data": {"image": "avatar-7"}, "error": None, "metadata": {}})

    result = process_avatar(InfraiClient("test-key", opener), AvatarRequest("t-7", "face.jpg", b"bytes"))
    assert result.tenant_id == "t-7"
    assert result.image == "avatar-7"
    assert result.status == "ready"
    assert calls[0][0] == calls[1][0] == "POST"
    assert calls[0][2] == {"file": "data:image/jpeg;base64," + base64.b64encode(b"bytes").decode(), "filename": "face.jpg"}
    assert calls[1][2] == {"image": "upload-7", "aspect": "1:1"}


def test_http_429_envelope_retries(monkeypatch):
    calls = []
    monkeypatch.setattr("avatar_pipeline.time.sleep", lambda delay: calls.append(delay))

    def opener(req):
        if not calls:
            payload = json.dumps({"ok": False, "error": {"code": "RATE_LIMITED"}}).encode()
            raise HTTPError(req.full_url, 429, "rate limited", {}, io.BytesIO(payload))
        return FakeResponse({"ok": True, "data": {"image": "upload-7"}})

    assert InfraiClient("test-key", opener).upload(b"bytes", "face.jpg") == {"image": "upload-7"}
    assert calls == [1]


def test_http_error_envelope_is_reported():
    def opener(req):
        payload = json.dumps({"ok": False, "error": {"code": "BAD_IMAGE"}}).encode()
        raise HTTPError(req.full_url, 400, "bad request", {}, io.BytesIO(payload))

    with pytest.raises(InfraiError) as error:
        InfraiClient("test-key", opener).upload(b"bytes", "face.jpg")
    assert (error.value.code, error.value.status) == ("BAD_IMAGE", 400)
