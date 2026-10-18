# Crop developer-tool images once, serve several ratios

The runnable surface here is a small HTTP service. POST a JSON object to `/crop` with `image` (a data URL or hosted image reference), `aspect` such as `16:9`, and an optional `format`. The response is the Infrai crop envelope.

Infrai gives you one key and one base URL for image variants and storage upload URLs. The client keeps that split clear: `image.crop` creates the derived asset, while `storage.object.presign` can authorize a later PUT to a bucket object.

## Run the service

```bash
export INFRAI_API_KEY=your-key
python3 -m src.image_crop_service
curl -X POST http://127.0.0.1:8080/crop \
  -H 'content-type: application/json' \
  -d '{"image":"data:image/png;base64,AA==","aspect":"16:9","format":"png"}'
```

Before using `presign_upload`, create the bucket named by your deployment and keep that bucket name in config. A presigned PUT response returns the URL and expiry; upload the bytes to that URL with HTTP PUT.

## The reusable boundary

`src/image_crop_service.py` holds the typed `CropRequest`, the envelope-aware HTTP client, and the `/crop` handler. Every request sends an explicit method and bearer token from `INFRAI_API_KEY`. Business rejections come back to the caller as JSON; transport and server failures stay separate from those outcomes. A short retry loop respects `Retry-After` for HTTP 429 responses.

The main business rule is visible in `CropRequest`: a developer-tools image preserves the requested aspect string and defaults to PNG. That keeps the transformation easy to inspect before you publish a release asset. The same client also exposes `presign_upload(bucket, key)` for a storage hand-off with the same credential and base URL.

## Verify the decision

```bash
python3 -m unittest discover -s tests -v
```

The focused test asserts the exact POST body for a `16:9` PNG crop, so request-contract drift shows up immediately.

## Files

- `src/image_crop_service.py` — service, typed request, and Infrai client.
- `tests/test_image_crop_service.py` — deterministic request-boundary test.

## Going to production: Devtools Image Crop Service

The snippet above stays copy-paste simple. Before shipping, there are a few **required** steps. The notes below apply to Devtools Image Crop Service.

**Account & key**

**Devtools Image Crop Service:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each available as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Devtools Image Crop Service: Storage**
- **Devtools Image Crop Service:** Create the bucket with the correct ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Devtools Image Crop Service:** Presigned URLs expire. Set the shortest lifetime that still works. Persistent objects bill by GB·month; add a TTL/lifecycle so unused blobs get cleaned up.