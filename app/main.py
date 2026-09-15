import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .config import Settings
from .controller import ControllerClient
from .service import TimeEngine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


settings = Settings()
engine = TimeEngine(settings)
controller = ControllerClient()


def controller_status_data() -> dict:
    """
    Build a small JSON-safe management-plane status payload.

    Do not send the complete source_observations structure to the
    controller. Detailed timing evidence remains available through
    edge-time's own APIs and attestation mechanism.
    """
    response = engine.response()

    return {
        "role": settings.role,
        "device_id": settings.effective_device_id,
        "selected_source": response.get("selected_source"),
        "authority_mode": response.get("authority_mode"),
        "state": response.get("state"),
        "uncertainty_ms": response.get("uncertainty_ms"),
        "authority_id": response.get("authority_id"),
    }


async def controller_registration_loop():
    """
    Maintain the management-plane relationship with edge-controller.

    Registration is attempted at startup and retried only when necessary.

    Once registered, only service status is updated periodically.

    Controller availability must never stop or degrade edge-time itself.
    """
    registered = False

    while True:
        try:
            if not registered:
                registered = controller.register()

            if registered:
                status_ok = controller.update_status(
                    "running",
                    controller_status_data(),
                )

                if not status_ok:
                    registered = False

        except Exception as exc:
            registered = False

            logger.warning(
                "Controller integration error: %s",
                exc,
            )

        await asyncio.sleep(max(1, settings.poll_seconds))


@asynccontextmanager
async def lifespan(app: FastAPI):
    controller_task = asyncio.create_task(
        controller_registration_loop()
    )

    try:
        yield

    finally:
        controller_task.cancel()

        try:
            await controller_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="edge-time",
    version="${SER_VER}",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "edge-time",
        "role": settings.role,
        "device_id": settings.effective_device_id,
    }


@app.get("/status")
def status():
    return engine.response()


@app.get("/time")
def time_now():
    return engine.response()


@app.get("/time/sources")
def sources():
    engine.collect()

    return {
        "sources": [
            observation.model_dump(mode="json")
            for observation in engine.observations
        ]
    }


@app.get("/time/attestation")
def attestation():
    return engine.attest()


@app.get("/authority")
def authority():
    return {
        "authority_id": settings.authority_id
        or (
            settings.effective_device_id
            if settings.is_authority
            else None
        ),
        "authority_url": settings.authority_url or None,
        "role": settings.role,
        "device_id": settings.effective_device_id,
        "is_authority": settings.is_authority,
    }


@app.get("/authority/time")
def authority_time():
    if not settings.is_authority:
        raise HTTPException(
            status_code=409,
            detail="This edge-time instance is not an authority",
        )

    return engine.authority_response()


@app.put("/authority")
def set_authority(body: dict):
    settings.authority_id = body.get(
        "authority_id",
        settings.authority_id,
    )

    settings.authority_url = body.get(
        "authority_url",
        settings.authority_url,
    )

    return authority()