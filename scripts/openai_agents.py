import typing

import agents.items
import logfire
import openai
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


def main():
    from agents import Agent, Runner

    thinking_agent = Agent(
        name="Thinking Professor",
        instructions="You are a Professor good at thinking, provide a detailed plan for the main agent to follow",  # noqa: E501
        model="gpt-4o-mini",
    )

    main_agent = Agent(
        name="Main Agent",
        instructions="You are a concise assistant. Let Thinking Professor think first, then follow the plan to answer the user's question.",  # noqa: E501
        model="gpt-4o-mini",
        handoffs=[thinking_agent],
    )

    input_messages: typing.List[agents.items.TResponseInputItem] = []
    for _input in ["Hello, world!", "What I just said?"]:
        input_messages.append(
            EasyInputMessageParam(role="user", content=_input, type="message")
        )

        result = Runner.run_sync(main_agent, input_messages)

        input_messages = result.to_input_list()

    for item in input_messages:
        print(item)


if __name__ == "__main__":
    main()
