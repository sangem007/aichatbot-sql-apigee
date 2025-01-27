import time
from datetime import datetime
import json
import os
import fun_def, support_fun

import streamlit as st
import openai
import streamlit_toggle as tog
from google.cloud import bigquery

workingDir = os.path.dirname(os.path.abspath(__file__))
configData = json.load(open(f"{workingDir}/config.json"))

BIGQUERY_DATASET_ID = "iInsights_analytic_logs"
openai.api_key = configData["OPENAI_API_KEY"]
available_fun_list = ["dataset_id", "table_id", "query"]

st.set_page_config(
    page_title="iInsight-OpenAI",
    page_icon="intelliswift.jpeg",
    layout="wide",
)

col1, col2, col3 = st.columns([6, 1, 1])
with col1:
    st.image("intelliswift.jpeg", width=200)
with col2:
    logToggle = tog.st_toggle_switch(label="Display Log", 
                    key="Key1", 
                    default_value=False, 
                    label_after = False, 
                    inactive_color = '#D3D3D3', 
                    active_color="#11567f", 
                    track_color="#29B5E8"
                    )
with col3:
    if st.button("Clear Chat"):
        st.session_state["chat_history"] = st.session_state["chat_history"].clear()

st.title("iInsights")
st.subheader("An AI powered API Analytics Tool")

with st.expander("Start with few, I have lot more ability to access you", expanded=True):
    st.write(
        """
        - How many apiproxies are there?
        - Can you tell me number of transactions corresponding to each developer?
        - Can you tell me number of transactions corresponding to each app?
        - Which api has the highest error rate?
        - Which app got most traffic?
    """
    )

# Initialize session state for chat history if it doesn't exist
if 'chat_history' not in st.session_state or st.session_state['chat_history'] is None:
    st.session_state['chat_history'] = []
if "conv" not in st.session_state:
    st.session_state.conv = []

# shows chat messages for each turn
for message in st.session_state.conv:
    with st.chat_message(message['role']):
        st.markdown(message["content"].replace("$", "\$"))  # noqa: W605
        try:
            if logToggle and message["backend_details"] != '':
                with st.expander("Function calls, parameters, and responses"):
                    st.markdown(message["backend_details"])
        except KeyError:
            pass

def model_call(chat_history):
    model_response = openai.chat.completions.create(
            model = "gpt-4-turbo",
            messages = [
                {"role": "system", "content": "You are a helpful assistant that provides detaila about API Analytics for Apigee from logs stored in Big query. No need to invoke function calls if user asks about chatbot capabilities and what can you do. Use function calls to retrieve details from Bigquery by creating sql queries. When user asks something, use the function call you have available. Format answer based on the result returned from Big query, like as multi line response or tabular format."},
                *chat_history
            ],
            tools=fun_def.definitions,
            tool_choice="auto",
            parallel_tool_calls=bool("false")
        )
    return model_response

if prompt := st.chat_input("Ask me things you are looking for..."):
    
    #inserting user prompt to message history list
    st.session_state['chat_history'].append({
        "role": "user",
        "content": prompt,
    })

    #inserting user prompt to conversation list
    st.session_state.conv.append({
        "role": "user",
        "content": prompt,
    })

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            message_placeholder = st.empty()

            t_b_first_modelres = datetime.now()
            response = model_call(st.session_state.chat_history)
            t_a_first_modelres = datetime.now()
            print("time diff of first model call---" , t_a_first_modelres - t_b_first_modelres)
            print("first model response")
            print(response)

            modelRes = response.choices[0].message

            #check where response contains none
            modelContent = support_fun.responseContentCheck(modelRes)

            #adding model response to session history
            st.session_state['chat_history'].append(
                {
                    "role": "assistant",
                    "content": modelContent,
                    "tool_calls": modelRes.tool_calls
                }
            )
            print("added into chat history")
            print(st.session_state.chat_history)
            if response.choices[0].finish_reason == "stop" and modelRes.tool_calls is None:
                function_calling_in_process = False
            else:
                with message_placeholder.container():
                    st.markdown("Searching for the information you requested. Please wait a moment. . . . . .")
                function_calling_in_process = True

            api_requests_and_responses = []
            backend_details = ""
            while function_calling_in_process:
                try:
                    params = {}
                    fun_name = modelRes.tool_calls[0].function.name
                    fun_args = modelRes.tool_calls[0].function.arguments
                    if any(key in fun_args for key in available_fun_list):
                        args = json.loads(fun_args)
                        for key in args:
                            params[key] = args[key]

                    t_b_list_datasets = datetime.now()
                    #calling functions based on function name returned from model response
                    if hasattr(fun_def, fun_name):
                        function_response, api_requests_and_responses = getattr(fun_def, fun_name)(modelRes,api_requests_and_responses,params)
                        #adding function details into session history
                        st.session_state['chat_history'].append(
                            {
                                "role": "tool",
                                "name": fun_name,
                                "content": function_response,
                                "tool_call_id": modelRes.tool_calls[0].id
                            }
                        )
                    t_a_list_datasets = datetime.now()
                    print("time diff - ",fun_name, "-->", t_a_list_datasets - t_b_list_datasets)

                    t_b_sec_modelres = datetime.now()
                    response = model_call(st.session_state.chat_history)
                    t_a_sec_modelres = datetime.now()
                    print("time diff second model res--" , t_a_sec_modelres - t_b_sec_modelres)
                    print("second model res")
                    print(response)

                    modelRes = response.choices[0].message
                    modelContent = support_fun.responseContentCheck(modelRes)
                    #adding model response to session history
                    st.session_state['chat_history'].append(
                        {
                            "role": "assistant",
                            "content": modelContent,
                            "tool_calls": modelRes.tool_calls
                        }
                    )
                    print(st.session_state.chat_history)
                    print("******",api_requests_and_responses)

                    #populating backend details to show user when show logs button is enabled
                    backend_details += "- Function call:\n"
                    backend_details += (
                        "   - Function name: ```"
                        + str(api_requests_and_responses[-1][0])
                        + "```"
                    )
                    backend_details += "\n\n"
                    backend_details += (
                        "   - Function parameters: ```"
                        + str(api_requests_and_responses[-1][1])
                        + "```"
                    )
                    backend_details += "\n\n"
                    backend_details += (
                        "   - API response: ```"
                        + str(api_requests_and_responses[-1][2])
                        + "```"
                    )
                    backend_details += "\n\n"
                    if response.choices[0].finish_reason == "stop" and modelRes.tool_calls is None:
                        function_calling_in_process = False
                except AttributeError as ae:
                    print("inside attribute exception")
                    print(ae)
                    function_calling_in_process = False

            with message_placeholder.container():
                st.markdown(modelContent.replace("$", "\$"))  # noqa: W605
                if logToggle and backend_details != '':
                    with st.expander("Function calls, parameters, and responses:"):
                        st.markdown(backend_details)
                st.session_state.conv.append(
                    {
                        "role": "assistant",
                        "content": modelContent,
                        "backend_details": backend_details,
                    }
                )
            t_for_whole_con_end = datetime.now()
            print("time diff whole conversation --" , t_for_whole_con_end - t_b_first_modelres)

        except openai.AuthenticationError as authError:
            print("inside auth error exception")
            print(authError)
            
            error_message = f"""
                Apologies, Something went wrong! We encountered an unexpected error while
                trying to process your request. Please try rephrasing your
                question. Details:

                {str(authError)}"""
            with message_placeholder.container():
                backend_details = ""
                st.markdown(error_message)  # noqa: W605
            st.session_state.conv.append(
                {
                    "role": "assistant",
                    "content": error_message,
                    "backend_details": backend_details,
                }
            )
        except Exception as e:
            print("inside exception")
            print(e)

            st.session_state['chat_history'].append(
                {
                    "role": "tool",
                    "name": fun_name,
                    "content": function_response,
                    "tool_call_id": modelRes.tool_calls[0].id
                }
            )
            error_message = f"""
                Apologies, Something went wrong! We encountered an unexpected error while
                trying to process your request. Please try rephrasing your
                question. Details:

                {str(e)}"""
            with message_placeholder.container():
                backend_details = ""
                st.markdown(error_message)  # noqa: W605
            st.session_state.conv.append(
                {
                    "role": "assistant",
                    "content": error_message,
                    "backend_details": backend_details,
                }
            )