"""Local test receiver for the webhook relay.

Not part of the production system. It's a stand-in for a real
subscriber's server, so we can (a) see deliveries actually arrive and
(b) force the failure and timeout paths on deman. Runs as its own Compose
service, reusing the project image with a different command."""

import asyncio
import logging

from fastapi import FastAPI, Request, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("receiver")

app = FastAPI(title="Webhook Relay - Test Receiver")

# /slow blocks for this long before answering. Keep it ABOVE the relay's
# outbound request timeout so it reliably trips the timeout branch.
SLOW_DELAY_SECONDS = 30


@app.post("/hook")
async def receive_hook(request: Request) -> dict[str, str]:
    """Happy path: accept the delivery, log it, return 200."""
    # Logging the full body is the point here - this is a debug tool.
    # The relay must never do this; it has a different job.
    body = await request.json()
    logger.info("Received Webhook: %s", body)
    return {"status": "received"}


@app.post("/fail")
async def always_fail(request: Request) -> dict[str, str]:
    """Always 500, so a subscription pointed here deterministically
    exercises the relay's retry logic."""
    return Response(status_code=500, content="simulated failure")


@app.post("/slow")
async def slow_hook(request: Request) -> dict[str, str]:
    """Blocks past the relay's request timeout, to exercise the timeout branch.
    `asyncio.sleep (not time.sleep) so the slow request/endpoint doesn't freeze
    the whole reciever"""
    await asyncio.sleep(SLOW_DELAY_SECONDS)
    return {"status": "eventually"}
