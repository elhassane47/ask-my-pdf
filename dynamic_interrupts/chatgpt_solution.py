import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage
import asyncio

from astream_events_handler import invoke_our_graph  # Utility for graph events

# Sidebar navigation for two pages
tab = st.sidebar.selectbox("Choose a page:", [
    "Graph of Jokes",
    "Pair Number"
])

if tab == "Graph of Jokes":
    # ===========================
    # Page: Graph of Jokes
    # ===========================
    st.title("Graph of Jokes")

    # Session state keys specific to graph page
    if "expander_open_graph" not in st.session_state:
        st.session_state.expander_open_graph = True
    if "graph_resume_graph" not in st.session_state:
        st.session_state.graph_resume_graph = False
    if "messages_graph" not in st.session_state:
        st.session_state.messages_graph = [
            AIMessage(content="Please provide me with a word smaller than 5 letters?")
        ]

    prompt = st.chat_input()
    if prompt is not None:
        st.session_state.expander_open_graph = False

    with st.expander(label="Dynamic Interrupts", expanded=st.session_state.expander_open_graph):
        st.write(
            "This page uses NodeInterrupt and dispatch_custom_event to dynamically ask for a new response."
        )

    # Render chat history
    for msg in st.session_state.messages_graph:
        if isinstance(msg, AIMessage):
            st.chat_message("assistant").write(msg.content)
        elif isinstance(msg, HumanMessage):
            st.chat_message("user").write(msg.content)

    # Handle new prompt
    if prompt:
        st.session_state.messages_graph.append(HumanMessage(content=prompt))
        st.chat_message("user").write(prompt)

        with st.chat_message("assistant"):
            placeholder = st.container()
            shared_state = {"graph_resume": st.session_state.graph_resume_graph}
            response = asyncio.run(invoke_our_graph(prompt, placeholder, shared_state))
            st.session_state.graph_resume_graph = False

            if isinstance(response, dict):
                op = response.get("op")
                msg = response.get("msg", "")
                if op == "on_waiting_user_resp":
                    st.session_state.messages_graph.append(AIMessage(content=msg))
                    st.write(msg)
                    st.session_state.graph_resume_graph = True
                elif op == "on_new_graph_msg":
                    st.session_state.messages_graph.append(AIMessage(content=msg))
                    st.write(msg)
                else:
                    st.error("Unexpected response: " + str(response))
            else:
                st.error("Invalid response type from graph: " + str(response))

elif tab == "Pair Number":
    # ===========================
    # Page: Pair Number
    # ===========================
    st.title("Pair Number")

    # Session state keys specific to pair page
    if "expander_open_pair" not in st.session_state:
        st.session_state.expander_open_pair = True
    if "graph_resume_pair" not in st.session_state:
        st.session_state.graph_resume_pair = False
    if "messages_pair" not in st.session_state:
        st.session_state.messages_pair = [
            AIMessage(content="Please provide me with a word smaller than 5 letters?")
        ]

    prompt2 = st.chat_input()
    if prompt2 is not None:
        st.session_state.expander_open_pair = False

    with st.expander(label="Dynamic Interrupts", expanded=st.session_state.expander_open_pair):
        st.write(
            "This page duplicates the graph interaction but with its own state keys."
        )

    # Render chat history
    for msg in st.session_state.messages_pair:
        if isinstance(msg, AIMessage):
            st.chat_message("assistant").write(msg.content)
        elif isinstance(msg, HumanMessage):
            st.chat_message("user").write(msg.content)

    # Handle new prompt on pair page
    if prompt2:
        st.session_state.messages_pair.append(HumanMessage(content=prompt2))
        st.chat_message("user").write(prompt2)

        with st.chat_message("assistant"):
            placeholder2 = st.container()
            shared_state2 = {"graph_resume": st.session_state.graph_resume_pair}
            response2 = asyncio.run(invoke_our_graph(prompt2, placeholder2, shared_state2))
            st.session_state.graph_resume_pair = False

            if isinstance(response2, dict):
                op2 = response2.get("op")
                msg2 = response2.get("msg", "")
                if op2 == "on_waiting_user_resp":
                    st.session_state.messages_pair.append(AIMessage(content=msg2))
                    st.write(msg2)
                    st.session_state.graph_resume_pair = True
                elif op2 == "on_new_graph_msg":
                    st.session_state.messages_pair.append(AIMessage(content=msg2))
                    st.write(msg2)
                else:
                    st.error("Unexpected response: " + str(response2))
            else:
                st.error("Invalid response type from graph: " + str(response2))
