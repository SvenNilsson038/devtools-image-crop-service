import os
import unittest
from unittest.mock import patch

from src.image_crop_service import CropRequest, InfraiClient


class InfraiClientTest(unittest.TestCase):
    @patch.dict(os.environ, {"INFRAI_API_KEY": "test-key"})
    @patch.object(InfraiClient, "_request")
    def test_crop_sends_coordinates_and_format(self, request):
        request.return_value = {"ok": True, "data": {"asset_id": "cropped"}}
        client = InfraiClient()
        client.crop(CropRequest(image="data:image/png;base64,AA==", x=0, y=0, width=1, height=1))
        request.assert_called_once_with(
            "POST",
            "/image/crop",
            {
                "image": "data:image/png;base64,AA==",
                "x": 0,
                "y": 0,
                "width": 1,
                "height": 1,
                "format": "png",
            },
        )

    @patch.dict(os.environ, {"INFRAI_API_KEY": "test-key"})
    @patch.object(InfraiClient, "_request")
    def test_presign_upload_uses_path_below_base_version(self, request):
        request.return_value = {"ok": True, "data": {"url": "https://example.test"}}
        client = InfraiClient()
        client.presign_upload("bucket", "path/image.png")
        request.assert_called_once_with(
            "POST",
            "/storage/object/presign/bucket/path%2Fimage.png",
            {
                "op": "put",
                "content_type": "image/png",
                "expires_seconds": 900,
                "idempotency_key": "path/image.png",
            },
        )
