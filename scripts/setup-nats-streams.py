from __future__ import annotations

import asyncio
import os

import nats


AD_SUBJECTS = [
    "cortex.ad.drifts",
    "cortex.ad.actions",
    "cortex.ad.verifications",
    "cortex.ad.snapshots",
    "cortex.ad.kerberos.alerts",
    "cortex.ad.bloodhound.paths",
]


async def main() -> None:
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    nc = await nats.connect(nats_url)
    js = nc.jetstream()
    try:
        await js.stream_info("CORTEX_AD")
    except Exception:
        await js.add_stream(name="CORTEX_AD", subjects=AD_SUBJECTS, max_age=365 * 24 * 3600)
    await nc.drain()


if __name__ == "__main__":
    asyncio.run(main())
