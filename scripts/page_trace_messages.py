import functools
import json

import pydantic
import streamlit as st
from str_or_none import str_or_none

from anyot.clients.tempo_client import TempoClient

KEY_TRACE_ID = "__anyot_trace_id"
KEY_MESSAGE_LIST = "__anyot_message_list"

tempo_client = TempoClient()


class Message(pydantic.BaseModel):
    role: str | None = None
    content: str | None = None

    @property
    def content_json(self) -> dict | None:
        if self.content is None:
            return None
        try:
            return json.loads(self.content)
        except json.JSONDecodeError:
            return None

    @functools.cached_property
    def is_content_json(self) -> bool:
        return self.content_json is not None

    @functools.cached_property
    def tool_name(self) -> str | None:
        if self.content_json is None:
            return None
        return str_or_none(self.content_json.get("name"))


def search_trace_messages(trace_id: str) -> list[Message]:
    _message_list = []
    trace_response = tempo_client.get_trace(trace_id)
    for _rs in trace_response.trace.resourceSpans:
        for _ss in _rs.scopeSpans:
            for _span in _ss.spans:
                if _span.name == "message.created":
                    _role = None
                    _content = None
                    for _attr in _span.attributes:
                        if _attr.key == "role":
                            _role = _attr.value.stringValue
                        if _attr.key == "content":
                            _content = _attr.value.stringValue
                    _message_list.append(Message(role=_role, content=_content))
    return _message_list


def on_click_search_trace_messages() -> None:
    __might_trace_id = str_or_none(st.session_state.get(KEY_TRACE_ID))
    if __might_trace_id is None:
        st.error("Trace ID is required")
        return

    trace_id = __might_trace_id

    messages = search_trace_messages(trace_id)

    st.session_state[KEY_MESSAGE_LIST] = messages


def show_trace_messages() -> None:
    messages = st.session_state.get(KEY_MESSAGE_LIST, [])
    for message in messages:
        _st_message = (
            st.chat_message(message.role, avatar="⚙️")
            if message.role == "tool"
            else st.chat_message(message.role)  # type: ignore
        )
        # Tool call
        if message.tool_name:
            _tool_name = message.tool_name
            with _st_message.expander(f"⚙️ Tool Call:【{_tool_name}】", expanded=False):
                if message.content_json:
                    st.json(message.content_json)
                else:
                    st.markdown(str(message.content))
        # Tool output
        elif message.role == "tool":
            with _st_message.expander("⚙️ Tool Output", expanded=False):
                st.markdown(str(message.content))
        # Normal message
        else:
            _st_message.markdown(str(message.content))


def main():
    st.title("Trace Messages")

    st.text_input(
        "Trace ID",
        placeholder="Input trace ID",
        key=KEY_TRACE_ID,
    )
    st.button("Search", on_click=on_click_search_trace_messages)

    show_trace_messages()


if __name__ == "__main__":
    main()
