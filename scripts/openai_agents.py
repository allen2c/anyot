import asyncio
import datetime
import typing
import zoneinfo

import agents.items
import json_repair
import logfire
import openai
import pydantic
from agents import Agent, FunctionTool, RunContextWrapper, Runner, handoff
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions
from openai.types.responses.easy_input_message_param import EasyInputMessageParam
from rich import print

import anyot

anyot.configure(
    otel_resource_attributes=anyot.OtelResourceAttributes(
        service_name="anyot",
    ),
)


client = openai.OpenAI()

logfire.instrument_openai(client)
logfire.instrument_openai_agents()


class FunctionArgsGetTimeNow(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")

    timezone: str = pydantic.Field(
        default="Asia/Taipei",
        description="Optional. The timezone for the current time. Default is Asia/Taipei.",  # noqa: E501
    )


async def get_time_now(ctx: RunContextWrapper[typing.Any], args: str) -> str:
    await asyncio.sleep(0)
    args_model = FunctionArgsGetTimeNow.model_validate(json_repair.loads(args))

    dt_now = datetime.datetime.now(zoneinfo.ZoneInfo(args_model.timezone))
    dt_now = dt_now.replace(microsecond=0)
    return dt_now.isoformat()


tool_get_time_now = FunctionTool(
    name="get_time_now",
    description="Get the current time simply",
    params_json_schema=FunctionArgsGetTimeNow.model_json_schema(),
    on_invoke_tool=get_time_now,
)
tools = [tool_get_time_now]

# Remove all default attributes from the tools, because OpenAI will not accept them
for tool in tools:
    if "required" not in tool.params_json_schema:
        tool.params_json_schema["required"] = []
    if "properties" in tool.params_json_schema:
        for prop_key, prop_value in tool.params_json_schema["properties"].items():
            if "default" in prop_value:
                prop_value.pop("default")

            tool.params_json_schema["required"].append(prop_key)


def main():
    translation_agent = Agent(
        name="Translation Professor",
        instructions=prompt_with_handoff_instructions(
            "You are a Professor good at multiple languages translation, provide precise translate result."  # noqa: E501
        ),
        model="gpt-4.1-nano",
    )

    main_agent = Agent(
        name="Main Agent",
        instructions=prompt_with_handoff_instructions("You are a concise assistant"),
        model="gpt-4.1-nano",
        handoffs=[handoff(translation_agent)],
        tools=[tool_get_time_now],
    )

    input_messages: typing.List[agents.items.TResponseInputItem] = []
    for _input in [
        "Hello, world!",
        "What I just said?",
        "Translate 'Hello, world!' to Chinese",
        "What is the time now?",
    ]:
        input_messages.append(
            EasyInputMessageParam(role="user", content=_input, type="message")
        )

        result = Runner.run_sync(main_agent, input_messages)

        input_messages = result.to_input_list()

    for item in input_messages:
        print(item)


if __name__ == "__main__":
    with logfire.span("openai-agents"):
        main()
