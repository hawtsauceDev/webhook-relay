# Known Limitations

Documented trade-offs of the MVP. Each entry has an ID, the impact, and a status:

- **Accepted**: decided not to fix; reasoning recorded.
- **v2**: planned for a later version.
- **Open**: needs a decision or verification.

## Security

| ID | Limitation | Impact | Status |
|---|---|---|---|
| SEC-1 | **SSRF via `target_url`.** The relay POSTs to any http/https URL it is given, including internal hosts. | A subscriber could make the worker call internal services. | v2 (URL allow/deny rules, block private ranges) |
| SEC-2 | **No authentication** on the API. | Anyone who can reach it can register subscriptions and post events. | v2 |
| SEC-3 | **Webhook URLs stored in plaintext.** URLs often carry secrets. | A database leak exposes subscriber secrets. | v2 (encrypt at rest) |
| SEC-4 | **URL leaks through logs.** The `target_url` list filter puts the URL in the request line (Uvicorn access log), and Postgres puts key values in error `DETAIL` lines. | Secrets can appear in infrastructure logs. | Open: confirm `log_error_verbosity=terse` is applied on the Postgres container |
| SEC-5 | **Outbound requests are not signed.** | Subscribers cannot verify a request came from the relay. | v2 (HMAC signing) |
| SEC-6 | **No request body-size limit.** | A huge payload can consume memory and storage. | v2 |

## Input and API behavior

| ID | Limitation | Impact | Status |
|---|---|---|---|
| API-1 | **Deeply nested payloads** (thousands of levels) raise `RecursionError` in the payload validator and return 500. | A malformed request gets a 500 instead of a 422. | Accepted |
| API-2 | **Exact-match event types.** No wildcards or prefix matching. | Subscribers must register each event type. | Accepted |
| API-3 | **Offset pagination** on `GET /subscriptions`. | Slower and less stable on large or changing tables. | v2 (keyset pagination) |
| API-4 | **Read endpoints have no DB-error handling.** Only writes translate failures into domain errors. | A database failure on a read returns a raw 500. | Accepted |
| API-5 | **No endpoint to inspect events or deliveries.** `EventRead` and `DeliveryRead` schemas exist but are unused. | Delivery status can only be checked through `psql`. | Open: decide whether to build `GET /events/{id}` |
| API-6 | **Redirects are not followed** by the delivery client, so a 3xx counts as a failed attempt. | Subscribers that redirect will never succeed. | Accepted |

## Fan-out and data model

| ID | Limitation | Impact | Status |
|---|---|---|---|
| DATA-1 | **Snapshot fan-out.** Fan-out sees the subscriptions committed at query time (READ COMMITTED). | A subscription created a moment later misses that event. | Accepted |
| DATA-2 | **Linear fan-out cost.** One event creates N delivery rows and N enqueues inside one request. | Events with many subscribers make the request slow. | v2 (batch or move fan-out to a worker) |
| DATA-3 | **No trace for events posted while a subscription is inactive.** Fan-out creates no `skipped` row for them. | The audit log cannot show "this subscriber was inactive for this event." | v2 (create the delivery as `skipped` at fan-out) |
| DATA-4 | **Bounded `String(n)` on some model columns** differs from the unbounded database column. Limits are enforced by Pydantic. | The model and the schema disagree about length. | Accepted |
| DATA-5 | **Alembic autogenerate misses VARCHAR length changes** (seen on Alembic 1.19). | An empty autogenerate is weaker proof of no drift for column lengths. | Accepted (check length changes by hand) |

## Delivery pipeline

| ID | Limitation | Impact | Status |
|---|---|---|---|
| PIPE-1 | **Enqueue failures leave orphaned `pending` deliveries.** The enqueue happens after the commit; if the broker is down, the rows exist but no task does, and `POST /events` still answers 201. | Some deliveries are never attempted. | v2 (sweeper or transactional outbox) |
| PIPE-2 | **Deliveries can get stuck in `processing`.** Causes: recording the attempt fails repeatedly, a soft time limit fires outside the POST block, an unexpected exception escapes the task (e.g. `httpx.InvalidURL`), or the worker dies past its retries. | The row looks in-progress forever. | v2 (sweeper that resets old `processing` rows) |
| PIPE-3 | **Duplicate POSTs are possible.** If the POST succeeds but recording the attempt fails, the task retries and POSTs again. | Subscribers can receive the same event twice. | Accepted (at-least-once). Subscribers should deduplicate by `event_id`. |
| PIPE-4 | **Concurrent workers on one delivery.** Visibility-timeout redelivery under `acks_late` can run two workers at once. | Both POST. The SQL increment keeps `attempt_count` correct, but `status` is last-writer-wins. | Accepted. Stronger fix: `SELECT ... FOR UPDATE` or a version column. |
| PIPE-5 | **Hard time limit is not redelivered by default.** A child process killed by `task_time_limit` is acknowledged and reported failed, and `task_reject_on_worker_lost` is not set. | The row stays `processing` and nothing retries it. | Open: verify against the docs, decide whether to set `task_reject_on_worker_lost` (risk: poison-message loop) |
| PIPE-6 | **Fixed retry delay, no backoff.** 3 retries (4 attempts), 10 seconds apart. | A subscriber that is down longer than about 30 seconds exhausts its retries. | v2 (exponential backoff with jitter) |
| PIPE-7 | **4xx responses are retried** like any other failure. | Permanent client errors waste attempts. | v2 (retry only transient failures) |
| PIPE-8 | **No dead-letter queue.** Exhausted deliveries end as `failed` with no re-drive mechanism. | Failed deliveries need manual handling. | v2 |
| PIPE-9 | **No replay of skipped deliveries.** `SKIPPED` is terminal, so reactivating a subscription does not resend. | Events skipped while inactive are never delivered. | v2 (explicit replay action; it must reset the status itself) |
| PIPE-10 | **No connection pooling.** Each delivery uses a one-shot `httpx.post`. | New connection per request. Fine at MVP volume. | v2 (shared `httpx.Client`) |

## Operations and testing

| ID | Limitation | Impact | Status |
|---|---|---|---|
| OPS-2 | **`/health` checks only the database.** It does not check Redis, and the worker has no health check. | A dead broker or worker is not reported. | Accepted |
| OPS-3 | **Postgres and Redis ports are published to the host.** | Fine for local debugging, wrong for production. | Accepted (dev-only compose file) |
| OPS-4 | **The test receiver depends on the bind mount.** It is not part of the installed package. | It only works in the dev setup. | Accepted (dev-only tool) |
| OPS-5 | **No CI.** | Checks depend on running them by hand. | v2 |