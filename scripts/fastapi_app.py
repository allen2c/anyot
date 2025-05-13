# scripts/fastapi_app.py
import asyncio

import fastapi
import httpx
import logfire
from opentelemetry import trace

import anyot

tracer = trace.get_tracer(__name__)

anyot.configure(
    otel_resource_attributes=anyot.OtelResourceAttributes(service_name="anyot"),
    use_logfire=True,
    send_to_logfire=False,
    distributed_tracing=True,
)

app = fastapi.FastAPI()

logfire.instrument_fastapi(app)
logfire.instrument_httpx()


async def handle_request(request: fastapi.Request):
    with tracer.start_as_current_span("handle_request") as span:
        span.set_attribute("http.url", str(request.url))
        span.set_attribute("http.method", request.method)

        print(f"{request.url=}")
        print(f"{request.method=}")
        print(f"{request.headers=}")
        print(f"{request.path_params=}")
        print(f"{request.query_params=}")
        body = await request.body()
        print(f"{body[:300]=}")
        span.set_attribute("request.body_length", len(body))
        print(f"{request.client=}")
        print(f"{request.state._state=}")
        print(f"{request.cookies=}")

        await asyncio.sleep(0.5)


@app.get("/")
async def read_root(request: fastapi.Request):
    await handle_request(request)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            str(request.url.replace(path="/callback")), timeout=1
        )
        response.raise_for_status()

    return {"message": "Hello, World!"}


@app.get("/callback")
async def read_callback(request: fastapi.Request):
    return {"message": "Callback received"}
