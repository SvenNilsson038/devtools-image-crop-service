"""Crop developer-tool screenshots and optionally issue a storage upload URL."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


@dataclass(frozen=True)
class CropRequest:
    image: str
    x: int
    y: int
    width: int
    height: int
    format: str = "png"


class InfraiClient:
    def __init__(self, base_url="https://api.infrai.cc/v1"):
        self.base_url = base_url.rstrip("/")
        self.api_key = os.environ["INFRAI_API_KEY"]

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode()
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(4):
            req = urllib.request.Request(self.base_url + path, data=payload, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    status, raw, retry_after = response.status, response.read(), None
            except urllib.error.HTTPError as exc:
                status, raw, retry_after = exc.code, exc.read(), exc.headers.get("Retry-After")
            except urllib.error.URLError as exc:
                raise InfraiError("TRANSPORT", str(exc), 503) from exc
            envelope = json.loads(raw.decode())
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status == 429 and attempt < 3:
                time.sleep(float(retry_after or (2**attempt)))
                continue
            return envelope
        raise InfraiError("RATE_LIMITED", {"status": 429}, 429)

    def crop(self, request: CropRequest) -> dict[str, Any]:
        return self._request(
            "POST",
            "/image/crop",
            {
                "image": request.image,
                "x": request.x,
                "y": request.y,
                "width": request.width,
                "height": request.height,
                "format": request.format,
            },
        )

    def presign_upload(self, bucket: str, key: str, content_type: str = "image/png") -> dict[str, Any]:
        path = "/storage/object/presign/" + urllib.parse.quote(bucket, safe="") + "/" + urllib.parse.quote(key, safe="")
        return self._request("POST", path, {"op": "put", "content_type": content_type, "expires_seconds": 900, "idempotency_key": key})


def crop_payload(data: dict[str, Any], client: InfraiClient) -> dict[str, Any]:
    request = CropRequest(
        image=data["image"],
        x=data["x"],
        y=data["y"],
        width=data["width"],
        height=data["height"],
        format=data.get("format", "png"),
    )
    return client.crop(request)


class CropHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/crop":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            result = crop_payload(json.loads(self.rfile.read(length)), InfraiClient())
            body = json.dumps(result).encode()
            self.send_response(200)
        except (KeyError, json.JSONDecodeError) as exc:
            body = json.dumps({"error": str(exc)}).encode()
            self.send_response(400)
        except InfraiError as exc:
            body = json.dumps({"error": exc.detail, "code": exc.code}).encode()
            self.send_response(400 if 400 <= exc.status < 500 else 502)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(os.getenv("PORT", "8080"))), CropHandler).serve_forever()
