# PYTHONPATH=. fastapi dev scripts/fastapi_app.py
import asyncio

import fastapi
import logfire
from opentelemetry import trace

import anyot

tracer = trace.get_tracer(__name__)

anyot.configure(
    otel_resource_attributes=anyot.OtelResourceAttributes(service_name="anyot"),
    use_logfire=True,
    send_to_logfire=False,
)


app = fastapi.FastAPI()


logfire.instrument_fastapi(app)


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

        return None


@app.get("/")
async def read_root(request: fastapi.Request):
    await handle_request(request)
    return {"message": "Hello, World!"}
