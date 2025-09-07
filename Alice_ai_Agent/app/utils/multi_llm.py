from groq import Groq
from utils.config import GROQ_API_KEY

class MultiLLMManager:
    def __init__(self):
        self.client = Groq(api_key=GROQ_API_KEY)
        
    async def workflow_planner(self, user_request: str):
        # Fast model for step planning
        response = self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": f"Plan steps for: {user_request}"}],
            max_tokens=512,
            temperature=0.3
        )
        return response.choices[0].message.content
        
    async def visual_analyzer(self, screenshot_b64: str, context: str):
        # Vision model for screenshot analysis
        response = self.client.chat.completions.create(
            model="llama-3.2-11b-vision-preview", 
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": context},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
                ]
            }],
            max_tokens=800,
            temperature=0.1
        )
        return response.choices[0].message.content
