import logfire
import openai
from opentelemetry import trace

import anyot

tracer = trace.get_tracer(__name__)

anyot.configure(
    otel_resource_attributes=anyot.OtelResourceAttributes(
        service_name="ggwp"
    ).to_string()
)


openai_client = openai.OpenAI()

logfire.instrument_openai(openai_client)

instructions = "You are a concise assistant."
previous_response_id: str | None = None

with tracer.start_as_current_span("openai-responses") as span:

    for _input in ["Hello, world!", "What I just said?"]:
        print(f"\nUser: {_input}")

        responses_res = openai_client.responses.create(
            input=_input,
            model="gpt-4o-mini",
            instructions=instructions,
            previous_response_id=previous_response_id,
        )

        previous_response_id = responses_res.id

        for _output in responses_res.output:
            if _output.type == "message":
                print(
                    "\nAssistant: "
                    + "\n".join(
                        [
                            _content.text
                            for _content in _output.content
                            if _content.type == "output_text"
                        ]
                    )
                )
            else:
                print(_output)
