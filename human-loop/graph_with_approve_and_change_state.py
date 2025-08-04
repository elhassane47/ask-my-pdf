from typing import TypedDict, Optional
import uuid
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
    print(f"✅ Final summary: {state['summary']}")
    return state


# Route based on human response
def route_based_on_decision(state: State) -> str:
    print(f"Debug: review_decision = {state.get('review_decision')}")
    if state.get("review_decision", "").lower() == "yes":
        return "review"
    return "skip"


# --- Build the graph ---
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
graph = builder.compile(checkpointer=memory)


# Run the graph
def run_graph():
    # Use consistent session ID
    session_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    print("Starting graph execution...")

    # Initial run
    for event in graph.stream({}, config=config):
        print(f"Event: {event}")

        if "__interrupt__" in event:
            interrupt_data = event["__interrupt__"][-1].value
            print(f"Interrupt data: {interrupt_data}")

            # Handle ask_for_review interrupt
            if "options" in interrupt_data:
                print(interrupt_data["message"])
                print("Summary:", interrupt_data["summary"])
                print("Options:", interrupt_data["options"])
                user_response = input("Your choice (yes/no): ").strip().lower()

                # Resume with the user's decision
                print(f"Resuming with decision: {user_response}")
                for resume_event in graph.stream(
                        Command(resume=user_response),
                        config=config
                ):
                    print(f"Resume event: {resume_event}")

                    # Handle nested interrupt for human review
                    if "__interrupt__" in resume_event:
                        nested_interrupt = resume_event["__interrupt__"][-1].value
                        if "task" in nested_interrupt:
                            print(nested_interrupt["task"])
                            print("Original summary:", nested_interrupt["generated_summary"])
                            edited = input("✏️ Enter your edited summary: ").strip()

                            # Resume with edited summary
                            print(f"Resuming with edited summary: {edited}")
                            for final_event in graph.stream(
                                    Command(resume=edited),
                                    config=config
                            ):
                                print(f"Final event: {final_event}")

            # Handle human_review interrupt (if it occurs at top level)
            elif "task" in interrupt_data:
                print(interrupt_data["task"])
                print("Original summary:", interrupt_data["generated_summary"])
                edited = input("✏️ Enter your edited summary: ").strip()

                # Resume with edited summary
                for resume_event in graph.stream(
                        Command(resume=edited),
                        config=config
                ):
                    print(f"Resume event: {resume_event}")


if __name__ == "__main__":
    run_graph()