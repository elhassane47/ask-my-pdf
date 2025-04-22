from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables.config import RunnableConfig
#  https://api.python.langchain.com/en/latest/callbacks/langchain_core.callbacks.manager.adispatch_custom_event.html
from langchain_core.callbacks import adispatch_custom_event
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import NodeInterrupt  # interrupt for human-in-the-loop intervention

# Define the state to include file payload keys
class State(TypedDict):
    sas_content: str
    input_content: str
    output_content: str

async def step_1(state: State, config: RunnableConfig) -> State:
    print("---Step 1---")
    # Dispatch a custom event to notify about the initialization with file contents
    await adispatch_custom_event(
        "on_init_files",
        {
            "sas_content": state["sas_content"],
            "input_content": state["input_content"],
            "output_content": state["output_content"]
        },
        config=config
    )
    # No-op write to satisfy Pregel's requirement
    state["sas_content"] = state["sas_content"]
    return state

async def step_2(state: State, config: RunnableConfig) -> State:
    print("---Step 2---")
    # Example check: ensure input_content is not empty
    if not state["input_content"]:
        await adispatch_custom_event(
            "on_waiting_user_resp",
            "Input file appears empty, please upload valid content.",
            config=config
        )
        # Write before interrupt
        state["input_content"] = state["input_content"]
        raise NodeInterrupt("Empty input_content: user intervention required.")
    else:
        await adispatch_custom_event(
            "on_conditional_check",
            {"input_length": len(state["input_content"])},
            config=config
        )
        # No-op update
        state["input_content"] = state["input_content"]
    return state

async def step_3(state: State, config: RunnableConfig) -> State:
    print("---Step 3---")
    # Dispatch an event indicating completion with payload summary
    summary = {
        "sas_len": len(state["sas_content"]),
        "input_len": len(state["input_content"]),
        "output_len": len(state["output_content"])
    }
    await adispatch_custom_event("on_complete_files", summary, config=config)
    # No-op write to satisfy requirement
    state["output_content"] = state["output_content"]
    return state

# Define graph nodes and edges
builder = StateGraph(State)
builder.add_node("step_1", step_1)
builder.add_node("step_2", step_2)
builder.add_node("step_3", step_3)

builder.add_edge(START, "step_1")
builder.add_edge("step_1", "step_2")
builder.add_edge("step_2", "step_3")
builder.add_edge("step_3", END)

# Create a memory saver to store graph states by thread and allow state recovery
memory = MemorySaver()

graph_with_files = builder.compile(checkpointer=memory)
