# API Contracts v1 (Core Deliberation + Sessions)

## Zakres

Ten dokument opisuje ujednolicony kontrakt błędów dla endpointów core:

- `POST /api/deliberate`
- `POST /api/deliberate/v2`
- `GET /api/sessions`
- `GET /api/sessions/{session_id}`
- `GET /api/sessions/{session_id}/export`
- `POST /api/share`
- `GET /api/shared/{token}`

## Stałe elementy diagnostyczne

Każda odpowiedź z powyższych endpointów zawiera nagłówek:

- `X-Trace-Id: <trace_id>`

W odpowiedziach błędów trace id jest też dostępne w JSON (`meta.trace_id`).

## Kontrakt błędów (wspólny envelope)

```json
{
  "ok": false,
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": []
  },
  "meta": {
    "trace_id": "f9a2d2d4c94e4c40b28d7f6f1e8e67df",
    "timestamp": "2026-04-20T21:12:34.123456+00:00"
  },
  "detail": "Request validation failed"
}
```

Uwagi:

- `detail` jest utrzymane dla kompatybilności wstecznej.
- `error.details` jest opcjonalne i zależy od typu błędu.

## Kontrakty sukcesu (bez breakingu)

### `POST /api/deliberate` (v1)

Sukces pozostaje bez zmian (dotychczasowy kształt `DeliberationResult`), np.:

```json
{
  "query": "test query",
  "timestamp": "2026-04-20T10:00:00",
  "agent_responses": [],
  "synthesis": null,
  "sources": [],
  "total_agents": 0,
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "total_cost": 0.0
  }
}
```

### `POST /api/deliberate/v2`

Sukces pozostaje w envelope v2 (`ok=true`, `data`, `meta`, `diagnostics`).

### `GET /api/sessions*`, `POST /api/share`, `GET /api/shared/{token}`

Sukces pozostaje zgodny z dotychczasowym zachowaniem endpointów (bez zmian w polach payloadu).

## Kody błędów

| HTTP | `error.code` | Opis |
|---|---|---|
| 400 | `bad_request` | Nieprawidłowy request biznesowy |
| 401 | `unauthorized` | Brak autoryzacji / nieprawidłowa sesja |
| 403 | `forbidden` | Dostęp zabroniony |
| 404 | `not_found` | Zasób nie istnieje |
| 409 | `conflict` | Konflikt stanu |
| 413 | `payload_too_large` | Za duży request |
| 422 | `validation_error` | Błąd walidacji danych wejściowych |
| 429 | `rate_limit` | Przekroczony limit zapytań |
| 5xx | `internal_error` | Błąd serwera |

## Przykłady

### Przykład: brak sesji

`GET /api/sessions/not-found-session`:

```json
{
  "ok": false,
  "error": {
    "code": "not_found",
    "message": "Session not found"
  },
  "meta": {
    "trace_id": "c2baf85b58fe4ed8ae1d0dc2a81c6b7a",
    "timestamp": "2026-04-20T21:15:01.111222+00:00"
  },
  "detail": "Session not found"
}
```

### Przykład: rate limit

```json
{
  "ok": false,
  "error": {
    "code": "rate_limit",
    "message": "Too many requests in short time. Please slow down."
  },
  "meta": {
    "trace_id": "f4ce94d8d68d4326b786fca95013d7f8",
    "timestamp": "2026-04-20T21:16:55.445566+00:00"
  },
  "detail": "Too many requests in short time. Please slow down."
}
```
