def invoke_test_our_graph(initial_state, streamlit_component, thread_id):
    container = streamlit_component
    thread_config = {"configurable": {"thread_id": thread_id}}

    # MINIMAL FIX: Add these 3 lines to prevent restarting the graph
    if 'graph_started' not in st.session_state:
        st.session_state.graph_started = False
    if 'interrupt_event' not in st.session_state:
        st.session_state.interrupt_event = None

    # Only start the graph if we haven't started it yet
    if not st.session_state.graph_started:
        st.session_state.graph_started = True

        # Invoke the graph as normal but depending on if the input is 'Won
        for event in graph.stream(initial_state, thread_config):
            if "__interrupt__" in event:
                # Save the interrupt event and stop
                st.session_state.interrupt_event = event
                st.rerun()  # Refresh to show the UI
                return  # Exit the function

        # If no interrupt, the graph completed normally
        return

    # Handle the interrupt (this runs after the rerun)
    if st.session_state.interrupt_event:
        event = st.session_state.interrupt_event
        print(f"Resume event: {event}")

        # Handle nested interrupt for human review
        if "__interrupt__" in event:
            nested_interrupt = event["__interrupt__"]
            if "task" in nested_interrupt:
                print(nested_interrupt["task"])

                # MINIMAL FIX: Use a form to prevent auto-rerun on typing
                with st.form("review_form"):
                    edited_content = st.text_area(
                        "Éditez le contenu si nécessaire:",
                        value="generated_content",  # Replace with your actual content
                        height=300,
                        key="content_editor"
                    )

                    col1, col2 = st.columns(2)

                    with col1:
                        approve_button = st.form_submit_button("✅ Approuver", use_container_width=True)

                    with col2:
                        reject_button = st.form_submit_button("❌ Rejeter", use_container_width=True)

                # Handle button clicks
                if approve_button:
                    user_response = "yes"
                    print(f"Resuming with decision: {user_response}")

                    for resume_event in graph.stream(
                            Command(resume=user_response),
                            config=thread_config
                    ):
                        print(f"Final event: {resume_event}")
                        container.success("✅ Processus terminé!")
                        container.json(resume_event)  # Show the final result

                        # Reset for next run
                        st.session_state.graph_started = False
                        st.session_state.interrupt_event = None
                        break

                elif reject_button:
                    user_response = "no"
                    print(f"Resuming with decision: {user_response}")

                    for resume_event in graph.stream(
                            Command(resume=user_response),
                            config=thread_config
                    ):
                        print(f"Final event: {resume_event}")
                        container.success("✅ Processus terminé!")
                        container.json(resume_event)

                        # Reset for next run
                        st.session_state.graph_started = False
                        st.session_state.interrupt_event = None
                        break
        else:
            # Handle other types of events
            name = str(event)
            print(f"Other event: {name}")


# ALTERNATIVE: Even more minimal fix - just wrap the text area in a form
def invoke_test_our_graph_minimal(initial_state, streamlit_component, thread_id):
    container = streamlit_component
    thread_config = {"configurable": {"thread_id": thread_id}}

    # SUPER MINIMAL: Just add this check
    if 'in_review' not in st.session_state:
        st.session_state.in_review = False

    if not st.session_state.in_review:
        # Invoke the graph as normal
        for event in graph.stream(initial_state, thread_config):
            if "__interrupt__" in event:
                # Store event and mark as in review
                st.session_state.review_event = event
                st.session_state.in_review = True
                st.rerun()
                return
        return

    # We're in review mode
    event = st.session_state.review_event
    nested_interrupt = event["__interrupt__"]

    if "task" in nested_interrupt:
        print(nested_interrupt["task"])

        # ONLY CHANGE: Wrap in form
        with st.form("content_form"):
            edited_content = st.text_area(
                "Éditez le contenu si nécessaire:",
                value="generated_content",
                height=300,
                key="content_editor"
            )

            edited_content = edited_content.strip()
            col1, col2 = st.columns(2)

            with col1:
                if st.form_submit_button("✅ Approuver", use_container_width=True):
                    # Resume and complete
                    for final_event in graph.stream(
                            Command(resume="yes"),
                            config=thread_config
                    ):
                        print(f"Final event: {final_event}")
                        container.success(final_event)

                        # Reset
                        st.session_state.in_review = False
                        del st.session_state.review_event
                        st.rerun()

            with col2:
                if st.form_submit_button("❌ Rejeter", use_container_width=True):
                    # Resume and complete
                    for final_event in graph.stream(
                            Command(resume="no"),
                            config=thread_config
                    ):
                        print(f"Final event: {final_event}")
                        container.success(final_event)

                        # Reset
                        st.session_state.in_review = False
                        del st.session_state.review_event
                        st.rerun()