import streamlit as st
import uuid
import asyncio
from st_graph import graph
from langgraph.types import Command

st.set_page_config(page_title="LangGraph Human-in-the-Loop Demo", page_icon="📝")
st.title("LangGraph Human-in-the-Loop Demo")

# Session state for thread/config
def init_session():
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "interrupt_result" not in st.session_state:
        st.session_state.interrupt_result = None
    if "final_result" not in st.session_state:
        st.session_state.final_result = None
    if "step" not in st.session_state:
        st.session_state.step = "start"

init_session()

config = {"configurable": {"thread_id": st.session_state.thread_id}}

async def run_graph_stream():
    placeholder = st.empty()
    async for event in graph.astream({}, config=config):
        # If we hit an interrupt, store it and break
        if "__interrupt__" in event:
            st.session_state.interrupt_result = event["__interrupt__"]
            st.session_state.step = "interrupt"
            break
        # Optionally show progress
        placeholder.info("Processing... (streaming)")

if st.session_state.step == "start":
    st.write("### 1. Generate a summary with LLM, then review/edit it.")
    if st.button("Start Workflow", type="primary"):
        asyncio.run(run_graph_stream())
        st.rerun()

elif st.session_state.step == "interrupt":
    interrupt = st.session_state.interrupt_result
    st.info(interrupt[0].value["task"])
    st.write("**Generated summary:**")
    st.write(interrupt[0].value["generated_summary"])
    edited = st.text_area("Edit the summary as needed:", value=interrupt[0].value["generated_summary"], key="edit_summary")
    if st.button("Submit Edited Summary", type="primary"):
        resumed_result = graph.invoke(
            Command(resume={"edited_summary": edited}),
            config=config
        )
        st.session_state.final_result = resumed_result["summary"]
        st.session_state.step = "done"
        st.rerun()

elif st.session_state.step == "done":
    st.success("Workflow complete!")
    st.write("**Final summary used downstream:**")
    st.write(st.session_state.final_result)
    if st.button("Restart", type="secondary"):
        for k in ["interrupt_result", "final_result", "step", "thread_id"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun() 