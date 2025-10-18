import streamlit as st
import requests
import time
import json
from typing import Any, List, Mapping, Optional
from dotenv import load_dotenv
import os

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

# --- PART 1: CONFIGURATION & API SECRETS ---
st.set_page_config(page_title="SOP Compliance Monitor", layout="wide")
st.title("✅ SOP Compliance Monitor")

# Get the API key from Streamlit's secrets management
MEMORIES_AI_API_KEY = os.getenv("MEMORIES_AI_API_KEY")
MEMORIES_AI_BASE_URL = "https://api.memories.ai/serve/api/v1"

# --- PART 2: MEMORIES.AI API COMMUNICATION ---
def upload_video_to_memories_ai(uploaded_file):
    """Uploads a video file to the memories.ai API and returns the video ID."""
    if not MEMORIES_AI_API_KEY:
        st.error("API key not found. Please add it to your Streamlit secrets.")
        return None

    headers = {"Authorization": MEMORIES_AI_API_KEY}
    files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
    unique_id = "25505"
    data = {"unique_id": unique_id}

    uploaded_url = f"{MEMORIES_AI_BASE_URL}/upload"

    try:
        with st.spinner(f"Uploading {uploaded_file.name}..."):
            response = requests.post(
                uploaded_url,
                files=files,
                headers=headers,
                data=data,
            )
            response_data = response.json()
            video_id = response_data.get("data", {}).get("videoNo", "")
            print(f"Video ID: {video_id}")
            response.raise_for_status()

        if not video_id:
            st.error("Upload successful, but no video ID was returned.")
            return None

        # Poll for processing status (simple implementation)
        with st.spinner("Video is processing... This may take a few minutes."):
            video_is_ready = False
            while not video_is_ready:
                json_body = {
                    "video_no": video_id,
                    "unique_id": unique_id,
                }
                list_video_url = f"{MEMORIES_AI_BASE_URL}/list_videos"
                status_response = requests.post(list_video_url, headers=headers, json=json_body)

                if status_response.status_code != 200:
                    # If the status check fails, wait and try again
                    time.sleep(10)
                    continue

                status_response_data = status_response.json()
                videos = status_response_data.get("data", {}).get("videos", )

                for video in videos:
                    if video.get("video_no") == video_id:
                        status = video.get("status", "")
                        if status == "PARSE":
                            video_is_ready = True  # Set the flag to exit the while loop
                            break  # Exit the for loop

                if not video_is_ready:
                    time.sleep(10)  # Wait before the next poll

            return video_id

    except requests.exceptions.RequestException as e:
        st.error(f"An API error occurred: {e}")
        st.error(f"Response body: {e.response.text if e.response else 'No response'}")
        return None

class MemoriesAIVLM(LLM):
    video_id: str

    @property
    def _llm_type(self) -> str:
        return "memories_ai_vlm"

    def _call(
        self,
        prompt: str,
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        if not MEMORIES_AI_API_KEY:
            raise ValueError("Memories.ai API key not found.")
        if not self.video_id:
            raise ValueError("Video ID is not set.")

        headers = {
            "Authorization": MEMORIES_AI_API_KEY,
            "Content-Type": "application/json",
        }

        unique_id = "25505"

        payload = {
            "video_nos": [self.video_id],  # List of video IDs to chat about
            "prompt": prompt,  # User query
            "session_id": "123",  # Chat session ID
            "unique_id": unique_id,
        }

        chat_url = f"{MEMORIES_AI_BASE_URL}/chat"

        try:
            response = requests.post(
                chat_url,
                headers=headers,
                json=payload,
                stream=False,
            )
            response.raise_for_status()
            content = response.json().get("data", {}).get("content", "")
            return content
        except requests.exceptions.RequestException as e:
            return f"API Error: {e}"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {"video_id": self.video_id}

# --- PART 3: UI & APPLICATION LOGIC ---
# Define the SOP checklist (your "trigger points")
SOP_CHECKLIST = [
    "Employee greets the customer upon entry.",
    "Employee asks clarifying questions to understand the customer's needs.",
    "Employee shows the requested item or a suitable alternative.",
    "Employee directs the customer to the billing counter.",
    "Employee correctly scans all items.",
    "Employee processes the payment successfully.",
    "Employee hands the items to the customer after payment.",
    "Employee thanks the customer as they leave."
]

if "video_id" not in st.session_state:
    st.session_state.video_id = None
if "analysis_complete" not in st.session_state:
    st.session_state.analysis_complete = False
if "results" not in st.session_state:
    st.session_state.results = {}
if "summary" not in st.session_state:
    st.session_state.summary = ""

# --- Main App Layout ---
col1, col2 = st.columns([1, 2])

with col1:
    st.header("Video Upload")
    uploaded_file = st.file_uploader("Choose a video file", type=["mp4", "mov", "avi"])

    if uploaded_file is not None:
        if st.session_state.get("uploaded_filename") != uploaded_file.name:
            st.session_state.video_id = None
            st.session_state.analysis_complete = False
            st.session_state.results = {}
            st.session_state.summary = ""
            st.session_state.uploaded_filename = uploaded_file.name

        if not st.session_state.video_id:
            video_id = upload_video_to_memories_ai(uploaded_file)
            if video_id:
                st.session_state.video_id = video_id
                st.success(f"Video processed successfully! ID: `{video_id}`")
            else:
                st.error("Video processing failed. Please try again.")

    if st.session_state.video_id and not st.session_state.analysis_complete:
        if st.button("Analyze Employee Performance", type="primary"):
            with st.spinner("Analyzing video against SOP checklist..."):
                vlm = MemoriesAIVLM(video_id=st.session_state.video_id)

                # This joins each item in your SOP_CHECKLIST into a single string with newlines
                checklist_string = "\n".join(f"- {item}" for item in SOP_CHECKLIST)

                template = """
                You are an expert retail operations analyst. Your task is to watch the provided video of an employee-customer interaction and determine if the employee followed the Standard Operating Procedures (SOPs).

                Analyze the video and for each of the following SOP points, determine if it was completed ('Yes'), not completed ('No'), or if it's not possible to determine from the video ('N/A').

                SOP Checklist:
                {checklist}

                After checking each point, provide a brief overall summary of the employee's performance. 
                Provide timestamp for each SOPs also when they happened. It is present on the Top left corner of the video.

                Please provide your response ONLY in a valid JSON format with two keys: "checklist_results" and "summary".
                The "checklist_results" should be an object where each key is the SOP point and the value is "Yes", "No", or "N/A".

                Example format:
                {{
                  "checklist_results": {{
                    "Employee greets the customer upon entry.": "Yes",
                    "Employee asks clarifying questions to understand the customer's needs.": "No"
                  }},
                  "summary": "The employee greeted the customer well but failed to ask questions to understand their needs."
                }}
                """

                prompt = PromptTemplate.from_template(template)
                chain = prompt | vlm | StrOutputParser()
                response_str = chain.invoke({"checklist": checklist_string})

                try:
                    # The model might wrap the JSON in markdown, so we clean it up
                    clean_response_str = response_str.strip().replace("```json", "").replace("```", "")
                    response_json = json.loads(clean_response_str)
                    st.session_state.results = response_json.get("checklist_results", {})
                    st.session_state.summary = response_json.get("summary", "No summary provided.")
                    st.session_state.analysis_complete = True
                    st.rerun()
                except (json.JSONDecodeError, AttributeError):
                    st.error(
                        "Failed to parse the analysis from the VLM. The model may have returned an invalid format.")
                    st.write("Raw response from model:", response_str)

with col2:
    st.header("Analysis Results")
    if not st.session_state.video_id:
        st.info("Please upload a video to begin the analysis.")
    elif not st.session_state.analysis_complete:
        st.info("Video is ready. Click the 'Analyze Employee Performance' button to see the results.")
    else:
        st.subheader("📋 SOP Compliance Checklist")

        results = st.session_state.results
        for item in SOP_CHECKLIST:
            status = results.get(item, "Not Analyzed")
            if status == "Yes":
                st.success(f"✅ {item}")
            elif status == "No":
                st.error(f"❌ {item}")
            else:
                st.warning(f"⚪ {item} (N/A)")

        st.subheader("📝 Overall Summary")
        st.write(st.session_state.summary)
