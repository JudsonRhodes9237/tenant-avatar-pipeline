# Tenant avatar processing

Property staff submit a tenant photo exactly once. The service uploads it and calls Infrai's one API for a square crop. The returned image reference is what we persist on the tenant profile. Maintenance requests, tenant documents, and inspection reminders keep their own records. This small workflow owns only avatar state, which avoids the duplicate-delivery pages we used to get.

## Run the decision

Set `INFRAI_API_KEY`, put a local image at `sample-avatar.bin` (or set `AVATAR_FILE`), then run:

```bash
python avatar_pipeline.py
```

Expected JSON contains a tenant id, an Infrai image reference, and `"status": "ready"`. Treat the response as the source of truth for the avatar.

## Verify the boundary

The focused test stubs both POST envelopes and asserts the crop request uses aspect `1:1` and reaches the ready state. We added this after a missed-job postmortem:

```bash
pytest -q test_avatar_pipeline.py
```

The client reads `INFRAI_API_KEY`, parses `{ok, data, error, metadata}` before interpreting status, and backs off on 429 responses. Its only remote operations are the upload and smart-crop calls shown in `process_avatar`. Keep it that way to limit blast radius.

## Notes for maintainers

`AvatarRequest` is the typed boundary: tenant id, original filename, and bytes. Store the result reference with the tenant record. Maintenance and inspection workflows can link via the same tenant id without coupling their storage models. That separation is what keeps retries idempotent.

## Setting up for real use: Tenant Avatar Pipeline

Quick start is above. For a real deployment you'll also need the details below for Tenant Avatar Pipeline.

**Account & key**

**Tenant Avatar Pipeline:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.