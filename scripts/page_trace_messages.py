import json
import typing

import streamlit as st
from str_or_none import str_or_none

from anyot.clients.tempo_client import TempoClient

KEY_TRACE_ID = "__anyot_trace_id"

tempo_client = TempoClient()


def might_dict(data: typing.Any) -> dict | None:
    if isinstance(data, dict):
        return data
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None


def search_and_show_trace_messages():
    __might_trace_id = str_or_none(st.session_state.get(KEY_TRACE_ID))
    if __might_trace_id is None:
        st.error("Trace ID is required")
        return

    trace_id = __might_trace_id

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
                    _content_json = might_dict(_content)
                    _might_tool_name = _content_json and _content_json.get("name")

                    _message = (
                        st.chat_message(_role, avatar="⚙️")
                        if _role == "tool"
                        else st.chat_message(_role)  # type: ignore
                    )
                    # Tool call
                    if _might_tool_name:
                        _tool_name = _might_tool_name
                        with _message.expander(
                            f"⚙️ Tool Call:【{_tool_name}】", expanded=False
                        ):
                            if _content_json:
                                st.json(_content_json)
                            else:
                                st.markdown(str(_content))
                    # Tool output
                    elif _role == "tool":
                        with _message.expander("⚙️ Tool Output", expanded=False):
                            st.markdown(str(_content))
                    # Normal message
                    else:
                        _message.markdown(str(_content))


def main():
    st.title("Trace Messages")

    st.text_input(
        "Trace ID",
        placeholder="Input trace ID",
        key=KEY_TRACE_ID,
    )
    st.button("Search", on_click=search_and_show_trace_messages)


if __name__ == "__main__":
    main()
