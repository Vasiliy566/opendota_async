# opendota-async

Production-oriented **async** client for the [OpenDota API](https://www.opendota.com/) (Dota 2 stats), built on [**Niquests**](https://github.com/jawah/niquests): HTTP/1.1, HTTP/2, and HTTP/3 with connection pooling and optional multiplexed fan-out.

## Install

```bash
pip install opendota-async
```

HTTP/3 (QUIC) extras (when you need wheels/protocol guarantees):

```bash
pip install 'opendota-async[http3]'
```

## Quickstart (30 seconds)

```python
import asyncio
from opendota_async import OpenDotaClient


async def main():
    async with OpenDotaClient() as client:
        profile = await client.players.get(86745912)
        print(profile.model_dump())


asyncio.run(main())
```

### API key

Register at [OpenDota API keys](https://www.opendota.com/api-keys) and pass a key (query param `api_key` or Bearer header — both are supported):

```python
async with OpenDotaClient(api_key="YOUR_KEY") as client:
    ...
# or
async with OpenDotaClient(bearer_token="YOUR_KEY") as client:
    ...
```

Environment variables (logged when used, never silently): `OPENDOTA_API_KEY`, `OPENDOTA_BASE_URL`, `OPENDOTA_TIMEOUT`, … — see `OpenDotaClientConfig.from_env()`.

### Multiplexed fan-out

`gather_get` temporarily enables Niquests multiplexing, issues parallel GETs, calls
`session.gather()`, then parses JSON. Use it for fan-out; ordinary `request()` calls keep
multiplexing off so responses are not lazy `ResponsePromise` objects.

```python
profiles = await client.players.gather_get([86745912, 302214028, 105248644])
```

### Error handling

```python
from opendota_async import NotFoundError, RateLimitError, OpenDotaClient


async def safe():
    try:
        async with OpenDotaClient() as c:
            await c.players.get(1)
    except NotFoundError as e:
        print(e.status_code, e.negotiated_protocol, e.response_body)
    except RateLimitError as e:
        print("retry after", e.retry_after)
```

### Pagination

```python
async with OpenDotaClient() as client:
    async for m in client.players.matches(86745912, hero_id=74):
        print(m.match_id)
```

### Sync usage

A blocking `OpenDotaSyncClient` shares the same configuration model and serializers:

```python
from opendota_async import OpenDotaSyncClient

with OpenDotaSyncClient() as c:
    p = c.players.get(86745912)
```

## Design notes

- **Lifecycle**: Always use `async with OpenDotaClient(...) as c:` or `await client.aclose()`. Do not rely on `__del__`.
- **Event loops**: One client per event loop; Niquests sessions are not safe across loops.
- **Retries**: Idempotent verbs retry on connection errors, timeouts, 429, and 502/503/504 with backoff + jitter; POST retries for status codes are opt-in via `retry_post=True` on `RetryPolicy` / config.
- **Types**: Responses are Pydantic models; use `.model_dump()` for raw dicts. `client.last_raw_response` is per-async-task for `OpenDotaClient` and per-thread for `OpenDotaSyncClient` (safe under concurrent tasks/threads).

## Testing

`pytest` runs unit tests and **live** checks against `https://api.opendota.com` (no key required). To skip network calls (e.g. offline CI), set `OPENDOTA_OFFLINE=1`.

## Documentation

Full docs (MkDocs Material / Read the Docs) will expand on streaming, SSE/WebSockets where applicable. See `docs/index.md` for the deprecation policy.

## Publishing (GitHub → PyPI)

CI and release workflows live in `.github/workflows/`. Step-by-step instructions: **[docs/publishing.md](docs/publishing.md)** (tag a `v*` release after bumping `version` in `pyproject.toml`).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT
