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
        
        # Process and display events AND save to history
        data = str(event["data"])
        
        if name in ("EVENT_START_LLM", "EVENT_SAVE_CODE", "EVENT_RUN_CODE", "EVENT_AI_MESSAGE"):
            container.info(data)
            st.session_state.event_history.append({"type": "info", "content": data})
        
        if name == "EVENT_RECEIVE_RESPONSE_LLM":
            container.markdown(data)
            st.session_state.event_history.append({"type": "markdown", "content": data})
            
        if name == "EVENT_ERROR_CODE":
            container.error(data)
            st.session_state.event_history.append({"type": "error", "content": data})
            
        if name == "EVENT_ASK_TO_WAIT":
            container.write(data)
            st.session_state.event_history.append({"type": "write", "content": data})
            
        if name in ("EVENT_CORRECT_CODE", "EVENT_END_GRAPH"):
            container.success(data, icon="✅")
            st.session_state.event_history.append({"type": "success", "content": data})
        
        if name == "EVENT_WORKING_OUTPUT":
            container.markdown(data)
            st.session_state.event_history.append({"type": "markdown", "content": data})
        
        # Check for interrupts AFTER displaying the event
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
                    st.session_state.workflow_paused = True
                    # Add pause message to history
                    st.session_state.event_history.append({
                        "type": "write", 
                        "content": "---\n⏸️ Workflow paused - waiting for user input..."
                    })
                    st.rerun()

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
    
    # Create a persistent container for events that won't be cleared
    if "event_history" not in st.session_state:
        st.session_state.event_history = []
    
    # Display event history from previous runs
    event_container = st.container()
    for event_msg in st.session_state.event_history:
        if event_msg['type'] == 'info':
            event_container.info(event_msg['content'])
        elif event_msg['type'] == 'error':
            event_container.error(event_msg['content'])
        elif event_msg['type'] == 'success':
            event_container.success(event_msg['content'], icon="✅")
        elif event_msg['type'] == 'markdown':
            event_container.markdown(event_msg['content'])
        elif event_msg['type'] == 'write':
            event_container.write(event_msg['content'])
    
    placeholder = st.container()
    shared_state = {"graph_resume": st.session_state.workflow_resume}
    
    # Check if workflow is paused and waiting for user input
    if st.session_state.get("workflow_paused", False) and st.session_state.interrupt_data:
        st.write("**Workflow paused for user input:**")
        st.write(st.session_state.interrupt_data.get("message", "Please make a choice:"))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Continue", key="continue_btn"):
                # Update the graph state with user's choice
                thread_config = {"configurable": {"thread_id": st.session_state.thread_id}}
                graph.update_state(thread_config, {"user_choice": "continue"})
                
                # Clear interrupt data and resume workflow
                st.session_state.interrupt_data = None
                st.session_state.workflow_paused = False
                st.session_state.graph_resume = True
                st.session_state.is_processing = True
                st.rerun()
        
        with col2:
            if st.button("Stop", key="stop_btn"):
                # Update the graph state with user's choice
                thread_config = {"configurable": {"thread_id": st.session_state.thread_id}}
                graph.update_state(thread_config, {"user_choice": "stop"})
                
                # Clear interrupt data and stop workflow
                st.session_state.interrupt_data = None
                st.session_state.workflow_paused = False
                st.session_state.is_processing = False
                st.rerun()
        
        # Don't run the graph while paused
        return
    
    elif not st.session_state.get("is_processing", False):
        # Show the "Recommencer" button when not processing
        if st.button("🔄 Recommencer", use_container_width=True):
            # Reset workflow state
            for key in ['workflow_step', 'selected_use_case', 'sas_code_step',
                       'sas_file_name', 'input_file_content', 'input_file_name',
                       'has_input_file', 'workflow_status', 'workflow_paused',
                       'interrupt_data', 'event_history']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.is_processing = True
            st.rerun()
    
    else:
        # Run the graph if we're processing and not paused
        with st.spinner("🔄 Workflow is running..."):
            asyncio.run(invoke_graph(initial_state, placeholder, shared_state, 
                                   thread_id=st.session_state.thread_id))
            
            # After execution, if not paused by interrupt, mark as not processing
            if not st.session_state.get("workflow_paused", False):
                st.session_state.is_processing = False

# Initialize session state variables
if "interrupt_data" not in st.session_state:
    st.session_state.interrupt_data = None
if "workflow_paused" not in st.session_state:
    st.session_state.workflow_paused = False
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False
if "graph_resume" not in st.session_state:
    st.session_state.graph_resume = False
if "event_history" not in st.session_state:
    st.session_state.event_history = []

# Call main function
if __name__ == "__main__":
    main()