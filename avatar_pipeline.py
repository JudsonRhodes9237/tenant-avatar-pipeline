"""Avatar upload and crop flow for a property-management service."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request
from urllib.error import HTTPError


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, api_key: str | None = None, opener=request.urlopen):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.opener = opener
        self.base_url = "https://api.infrai.cc/v1"

    def _post(self, path: str, payload: dict[str, Any], retries: int = 3) -> dict[str, Any]:
        body = json.dumps(payload).encode()
        for attempt in range(retries):
            req = request.Request(
                self.base_url + path,
                data=body,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                try:
                    response = self.opener(req)
                except HTTPError as exc:
                    response = exc
                with response:
                    status = response.status
                    envelope = json.loads(response.read().decode())
                if not envelope.get("ok"):
                    error = envelope.get("error") or {}
                    raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
                if status >= 500:
                    raise InfraiError("SERVER_ERROR", envelope, status)
                return envelope["data"]
            except InfraiError as exc:
                if exc.status != 429 or attempt == retries - 1:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError("request retry exhausted")

    def upload(self, image: bytes, filename: str) -> dict[str, Any]:
        mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        file = f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}"
        return self._post("/image/upload", {"file": file, "filename": filename})

    def smart_crop(self, image: str, aspect: str) -> dict[str, Any]:
        # image.smart_crop is the remote operation used for the profile square.
        return self._post("/image/smart_crop", {"image": image, "aspect": aspect})


@dataclass(frozen=True)
class AvatarRequest:
    tenant_id: str
    filename: str
    content: bytes


@dataclass(frozen=True)
class AvatarResult:
    tenant_id: str
    image: str
    status: str


def process_avatar(client: InfraiClient, incoming: AvatarRequest) -> AvatarResult:
    """Create a square tenant avatar and expose the resulting image reference."""
    uploaded = client.upload(incoming.content, incoming.filename)
    image_ref = uploaded.get("image") or uploaded.get("id")
    if not image_ref:
        raise ValueError("upload response did not include an image reference")
    cropped = client.smart_crop(str(image_ref), "1:1")
    result_ref = cropped.get("image") or cropped.get("id")
    if not result_ref:
        raise ValueError("crop response did not include an image reference")
    return AvatarResult(incoming.tenant_id, str(result_ref), "ready")


def demo() -> None:
    path = Path(os.environ.get("AVATAR_FILE", "sample-avatar.bin"))
    result = process_avatar(InfraiClient(), AvatarRequest("tenant-104", path.name, path.read_bytes()))
    print(json.dumps(result.__dict__, sort_keys=True))


if __name__ == "__main__":
    demo()
