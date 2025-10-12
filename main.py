# Upload Video from given URL
import requests
from dotenv import load_dotenv
import os

load_dotenv()

API_KEY = os.getenv("MEMORIES_AI_API_KEY")

headers = {"Authorization": API_KEY}  # API key
file_path = "Cat_Skateboarding_Video_Generated.mp4"
# Video file details
files = {
    "file": (os.path.basename(file_path), open(file_path, 'rb'), "video/mp4")
}

# Optional callback URL for task status notifications
data = {"unique_id": "123456"} # Optional

response = requests.post(
    "https://api.memories.ai/serve/api/v1/upload",
    files=files,
    data=data,
    headers=headers
)

# print(response.json())

video_no = response.json().get("data", {}).get("videoNo", "")
print(video_no)

# Chat with Video -> Non-Streaming Mode
chat_headers = {
    "Authorization": API_KEY,
    "Content-Type": "application/json",
}
