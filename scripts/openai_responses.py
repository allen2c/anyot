import datetime
import json
import typing
import zoneinfo

import json_repair
import logfire
import openai
from openai.types.responses.easy_input_message_param import EasyInputMessageParam
from openai.types.responses.function_tool import FunctionTool
from openai.types.responses.response import Response
from openai.types.responses.response_input_param import (
    FunctionCallOutput,
    ResponseInputParam,
)
from opentelemetry import trace

import anyot

tracer = trace.get_tracer(__name__)

anyot.configure(
    otel_resource_attributes=anyot.OtelResourceAttributes(
        service_name="anyot"
    ).to_string()
)


openai_client = openai.OpenAI()

logfire.instrument_openai(openai_client)


tool_get_time_now = FunctionTool(
    type="function",
    name="get_time_now",
    description="Get the current time simply",
    parameters={
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "default": "Asia/Taipei",
                "description": "Optional. The timezone for the current time. Default is Asia/Taipei.",  # noqa: E501
            },
        },
        "required": [],
    },
)


def get_time_now(timezone: str = "Asia/Taipei") -> str:
    dt_now = datetime.datetime.now(zoneinfo.ZoneInfo(timezone))
    dt_now = dt_now.replace(microsecond=0)
    return dt_now.isoformat()


tools: typing.Dict[str, typing.Tuple[FunctionTool, typing.Callable[..., str]]] = {
    "get_time_now": (tool_get_time_now, get_time_now),
}


def handle_function_call(name: str, arguments: typing.Dict[str, typing.Any]) -> str:
    with tracer.start_as_current_span("handle_function_call"):
        if name not in tools:
            raise ValueError(f"Function {name} not found")
        return tools[name][1](**arguments)


def handel_openai_response_output(
    response: Response,
    *,
    message: ResponseInputParam,
    instructions: str | None = None,
) -> Response:
    while response.output[0].type == "function_call":
        tool_call = response.output[0]
        message.append(tool_call.model_dump())  # type: ignore

        print(
            f"\nFunction call: {tool_call.name}, " + f"arguments: {tool_call.arguments}"
        )
        _tool_output = handle_function_call(
            tool_call.name,
            json_repair.loads(tool_call.arguments),  # type: ignore
        )
        print(f"\nTool output: {_tool_output}")

        message.append(
            FunctionCallOutput(
                call_id=tool_call.call_id,
                output=str(_tool_output).strip(),
                type="function_call_output",
            )
        )

        response = openai_client.responses.create(
            input=message,
            model="gpt-4o-mini",
            instructions=instructions,
            tools=[json.loads(tool[0].model_dump_json()) for tool in tools.values()],
            previous_response_id=response.previous_response_id,
        )

    return response


def main():
    instructions = "You are a concise assistant."
    previous_response_id: str | None = None

    with tracer.start_as_current_span("openai-responses"):

        for _input in [
            "Hello, world!",
            "What I just said?",
            "What time is it in Taipei?",
        ]:
            print(f"\nUser: {_input}")

            input_message: ResponseInputParam = []
            input_message.append(EasyInputMessageParam(role="user", content=_input))

            openai_responses = openai_client.responses.create(
                input=input_message,
                model="gpt-4o-mini",
                instructions=instructions,
                tools=[
                    json.loads(tool[0].model_dump_json()) for tool in tools.values()
                ],
                previous_response_id=previous_response_id,
            )

            previous_response_id = openai_responses.id

            openai_responses = handel_openai_response_output(
                openai_responses,
                message=input_message,
                instructions=instructions,
            )

            if openai_responses.output[0].type == "message":
                print(
                    "\nAssistant: "
                    + "\n".join(
                        [
                            _content.text
                            for _content in openai_responses.output[0].content
                            if _content.type == "output_text"
                        ]
                    )
                )


if __name__ == "__main__":
    main()
