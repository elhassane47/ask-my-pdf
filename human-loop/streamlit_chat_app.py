import streamlit as st
import uuid
from typing import TypedDict, Optional
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver


# Define state type
class State(TypedDict):
    summary: str
    review_decision: Optional[str]  # 'yes' or 'no'


# Step 1: Generate summary
def generate_summary(state: State) -> State:
    return {"summary": "The cat sat on the mat and looked at the stars."}


# Step 2: Ask human if they want to review (via interrupt)
def ask_for_review(state: State) -> State:
    result = interrupt({
        "message": "🧐 Would you like to review the summary?",
        "summary": state["summary"],
        "options": ["yes", "no"],
        "interruption_name": "ask_for_review",
    })
    # The result will be None during the interrupt,
    # but will contain the resume value when resumed
    if result is not None:
        return {"review_decision": result}
    return state


# Step 3: Human review (also uses interrupt)
def human_review(state: State) -> State:
    result = interrupt({
        "task": "✍️ Please edit this summary:",
        "generated_summary": state["summary"]
    })
    # When resumed, result will contain the edited summary
    if result is not None:
        return {"summary": result}
    return state


# Step 4: Finish node
def finish(state: State) -> State:
    return state


# Route based on human response
def route_based_on_decision(state: State) -> str:
    if state.get("review_decision", "").lower() == "yes":
        return "review"
    return "skip"


# --- Build the graph ---
@st.cache_resource
def build_graph():
    builder = StateGraph(State)

    # Add nodes
    builder.add_node("generate_summary", generate_summary)
    builder.add_node("ask_for_review", ask_for_review)
    builder.add_node("human_review", human_review)
    builder.add_node("finish", finish)

    # Set entry point
    builder.set_entry_point("generate_summary")

    # Edges
    builder.add_edge("generate_summary", "ask_for_review")

    # Conditional edges
    builder.add_conditional_edges("ask_for_review", route_based_on_decision, {
        "review": "human_review",
        "skip": "finish"
    })

    builder.add_edge("human_review", "finish")

    # Compile with memory
    memory = MemorySaver()
    return builder.compile(checkpointer=memory)


def invoke_graph(graph, config, initial_state=None):
    """
    Invoke the graph and return the events and any interrupt data.
    
    Args:
        graph: The compiled LangGraph
        config: Configuration for the graph execution
        initial_state: Initial state for the graph (default: empty dict)
    
    Returns:
        tuple: (events, interrupt_data, final_summary)
    """
    events = []
    interrupt_data = None
    final_summary = None
    
    try:
        for event in graph.stream(initial_state or {}, config=config):
            events.append(event)
            
            if "__interrupt__" in event:
                interrupt_data = event["__interrupt__"][-1].value
                break
                
    except Exception as e:
        st.error(f"Error in graph execution: {e}")
        return events, None, None
    
    return events, interrupt_data, final_summary


def resume_graph(graph, config, resume_value):
    """
    Resume the graph with a given value and return the events and final summary.
    
    Args:
        graph: The compiled LangGraph
        config: Configuration for the graph execution
        resume_value: Value to resume the graph with
    
    Returns:
        tuple: (events, final_summary)
    """
    events = []
    final_summary = None
    
    try:
        for event in graph.stream(Command(resume=resume_value), config=config):
            events.append(event)
            
            # Check if this is the final event (no more interrupts)
            if isinstance(event, dict):
                # If we have a summary in the event, use it
                if "summary" in event:
                    final_summary = event["summary"]
                    break
                # If this is the final state, extract summary from it
                elif "finish" in event:
                    finish_state = event["finish"]
                    if isinstance(finish_state, dict) and "summary" in finish_state:
                        final_summary = finish_state["summary"]
                        break
            
            # If we reach here and no more events are coming, use the resume value
            # This handles the case where the graph completes without returning a specific event
            if not event or (isinstance(event, dict) and not event):
                final_summary = resume_value
                break
                
    except Exception as e:
        st.error(f"Error in graph resume: {e}")
        # Fallback: use the resume value
        final_summary = resume_value
    
    return events, final_summary


def main():
    st.title("🤖 AI Summary Generator with Human Review")
    st.write("This app demonstrates the same logic as the `run_graph` function using Streamlit.")
    
    # Initialize session state
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if 'current_state' not in st.session_state:
        st.session_state.current_state = {}
    if 'graph_events' not in st.session_state:
        st.session_state.graph_events = []
    if 'waiting_for_input' not in st.session_state:
        st.session_state.waiting_for_input = False
    if 'interrupt_data' not in st.session_state:
        st.session_state.interrupt_data = None
    if 'final_summary' not in st.session_state:
        st.session_state.final_summary = None

    # Build graph
    graph = build_graph()
    config = {"configurable": {"thread_id": st.session_state.session_id}}

    # Sidebar for controls
    with st.sidebar:
        st.header("Controls")
        if st.button("🔄 Start New Session"):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.current_state = {}
            st.session_state.graph_events = []
            st.session_state.waiting_for_input = False
            st.session_state.interrupt_data = None
            st.session_state.final_summary = None
            st.rerun()

    # Main chat area
    st.header("Chat History")
    
    # Display chat history
    for event in st.session_state.graph_events:
        if isinstance(event, dict):
            if "summary" in event:
                st.info(f"📝 **Generated Summary:** {event['summary']}")
            elif "review_decision" in event:
                st.success(f"✅ **Review Decision:** {event['review_decision']}")
            elif "final_summary" in event:
                st.success(f"🎉 **Final Summary:** {event['final_summary']}")

    # Main interaction area
    if not st.session_state.waiting_for_input and not st.session_state.final_summary:
        if st.button("🚀 Start Summary Generation"):
            st.session_state.waiting_for_input = True
            st.session_state.graph_events = []
            
            # Start the graph execution using the helper function
            events, interrupt_data, _ = invoke_graph(graph, config)
            st.session_state.graph_events.extend(events)
            
            if interrupt_data:
                st.session_state.interrupt_data = interrupt_data
                st.rerun()

    # Handle interrupts
    if st.session_state.waiting_for_input and st.session_state.interrupt_data:
        interrupt_data = st.session_state.interrupt_data
        
        if "options" in interrupt_data:  # ask_for_review interrupt
            st.subheader("🤔 Review Decision")
            st.write(interrupt_data["message"])
            st.info(f"**Summary:** {interrupt_data['summary']}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes, review it"):
                    # Resume with the user's decision using helper function
                    events, final_summary = resume_graph(graph, config, "yes")
                    st.session_state.graph_events.extend(events)
                    
                    if final_summary:
                        st.session_state.final_summary = final_summary
                        st.session_state.waiting_for_input = False
                        st.session_state.interrupt_data = None
                        st.rerun()
                    else:
                        # Check if we got another interrupt (nested interrupt)
                        for event in events:
                            if "__interrupt__" in event:
                                nested_interrupt = event["__interrupt__"][-1].value
                                if "task" in nested_interrupt:
                                    st.session_state.interrupt_data = nested_interrupt
                                    st.rerun()
                                    break
            
            with col2:
                if st.button("❌ No, skip review"):
                    # Resume with the user's decision using helper function
                    events, final_summary = resume_graph(graph, config, "no")
                    st.session_state.graph_events.extend(events)
                    
                    if final_summary:
                        st.session_state.final_summary = final_summary
                        st.session_state.waiting_for_input = False
                        st.session_state.interrupt_data = None
                        st.rerun()

        elif "task" in interrupt_data:  # human_review interrupt
            st.subheader("✍️ Edit Summary")
            st.write(interrupt_data["task"])
            st.info(f"**Original Summary:** {interrupt_data['generated_summary']}")
            
            edited_summary = st.text_area(
                "Edit the summary:",
                value=interrupt_data['generated_summary'],
                height=100
            )
            
            if st.button("💾 Save Edited Summary"):
                # Resume with edited summary using helper function
                events, final_summary = resume_graph(graph, config, edited_summary)
                st.session_state.graph_events.extend(events)
                
                if final_summary:
                    st.session_state.final_summary = final_summary
                    st.session_state.waiting_for_input = False
                    st.session_state.interrupt_data = None
                    st.rerun()

    # Display final result
    if st.session_state.final_summary:
        st.success("🎉 **Process Complete!**")
        st.info(f"**Final Summary:** {st.session_state.final_summary}")
        
        if st.button("🔄 Start New Session"):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.current_state = {}
            st.session_state.graph_events = []
            st.session_state.waiting_for_input = False
            st.session_state.interrupt_data = None
            st.session_state.final_summary = None
            st.rerun()

    # Debug information (collapsible)
    with st.expander("🔧 Debug Information"):
        st.write(f"**Session ID:** {st.session_state.session_id}")
        st.write(f"**Current State:** {st.session_state.current_state}")
        st.write(f"**Waiting for Input:** {st.session_state.waiting_for_input}")
        st.write(f"**Interrupt Data:** {st.session_state.interrupt_data}")
        st.write(f"**Graph Events:** {len(st.session_state.graph_events)} events")
        
        # Show the last few events for debugging
        if st.session_state.graph_events:
            st.write("**Last 3 Events:**")
            for i, event in enumerate(st.session_state.graph_events[-3:], 1):
                st.write(f"Event {i}: {event}")
        
        # Show final summary if available
        if st.session_state.final_summary:
            st.write(f"**Final Summary:** {st.session_state.final_summary}")


if __name__ == "__main__":
    main()
