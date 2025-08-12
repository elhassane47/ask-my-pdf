async def invoke_graph(st_messages, st_placeholder, st_state, thread_id):
    print("graaph invokeeeed")
    events = []
    container = st_placeholder
    thread_config = {"configurable": {"thread_id": thread_id}}
    
    if st_state.get("graph_resume"):
        graph.update_state(thread_config, {"input": st_messages})
        st_input = None  # No new input is passed if resuming the graph
    
    # Invoke the graph as normal but depending on if the input is 'None'
    async for event in graph.astream_events(st_messages, thread_config, version="v1"):
        name = event["name"]
        events.append(event)
        
        if isinstance(event["data"], dict):
            chunk = event["data"].get("chunk")
            if name == "LangGraph" and chunk and chunk.get("__interrupt__"):
                interrupt_data = chunk.get("__interrupt__")[-1].value
                print("+" * 50)
                print(interrupt_data)
                print("+" * 50)
                
                if interrupt_data:
                    st.session_state.interrupt_data = interrupt_data
                    st.session_state.is_processing = False
                    # Don't call st.rerun() here - let the UI render first
                    return  # Exit the function to allow UI interaction
        
        data = str(event["data"])
        if name in ("EVENT_START_LLM", "EVENT_SAVE_CODE", "EVENT_RUN_CODE", "EVENT_AI_MESSAGE"):
            container.info(data)
        
        if name == "EVENT_RECEIVE_RESPONSE_LLM":
            container.markdown(data)
        if name == "EVENT_ERROR_CODE":
            container.error(data)
        if name == "EVENT_ASK_TO_WAIT":
            container.write(data)
        if name in ("EVENT_CORRECT_CODE", "EVENT_END_GRAPH"):
            container.success(data, icon="✅")
        
        if name == "EVENT_WORKING_OUTPUT":
            container.markdown(data)

# In your main app logic:
def main():
    # Your existing setup code...
    user_uid = st.context.headers.get("Domino-Username", "default_user")
    
    initial_state = {
        "sas_input_code": st.session_state.sas_file_content,
        "sas_input_data": st.session_state.input_sample,
        "sas_output_data": st.session_state.output_sample,
        "max_retry": st.session_state.max_retry,
        "use_case_dir_name": st.session_state.use_case_dir_name,
        "user_uid": user_uid,
        "execute_the_code": st.session_state.execute_code
    }
    
    placeholder = st.container()
    shared_state = {"graph_resume": st.session_state.workflow_resume}
    
    # Check if we have interrupt data and user hasn't made a choice yet
    if st.session_state.interrupt_data and not st.session_state.get("user_choice_made", False):
        st.write("**Workflow paused for user input:**")
        st.write(st.session_state.interrupt_data.get("message", "Please make a choice:"))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Continue", key="continue_btn"):
                # Update the graph state with user's choice
                thread_config = {"configurable": {"thread_id": st.session_state.thread_id}}
                graph.update_state(thread_config, {"user_choice": "continue"})
                
                # Clear interrupt data and mark choice as made
                st.session_state.interrupt_data = None
                st.session_state.user_choice_made = True
                st.session_state.graph_resume = True
                st.session_state.is_processing = True
                st.rerun()
        
        with col2:
            if st.button("Stop", key="stop_btn"):
                # Update the graph state with user's choice
                thread_config = {"configurable": {"thread_id": st.session_state.thread_id}}
                graph.update_state(thread_config, {"user_choice": "stop"})
                
                # Clear interrupt data and mark choice as made
                st.session_state.interrupt_data = None
                st.session_state.user_choice_made = True
                st.session_state.is_processing = False
                st.rerun()
    
    elif not st.session_state.is_processing:
        # Show the "Recommencer" button when not processing
        if st.button("🔄 Recommencer", use_container_width=True):
            # Reset workflow state
            for key in ['workflow_step', 'selected_use_case', 'sas_code_step',
                       'sas_file_name', 'input_file_content', 'input_file_name',
                       'has_input_file', 'workflow_status']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    else:
        # Only run the graph if we're processing and don't have pending interrupt
        with st.spinner("🔄 Workflow is running..."):
            asyncio.run(invoke_graph(initial_state, placeholder, shared_state, 
                                   thread_id=st.session_state.thread_id))

# Initialize session state variables
if "interrupt_data" not in st.session_state:
    st.session_state.interrupt_data = None
if "user_choice_made" not in st.session_state:
    st.session_state.user_choice_made = False
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False
if "graph_resume" not in st.session_state:
    st.session_state.graph_resume = False