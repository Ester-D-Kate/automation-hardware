import os
from dotenv import load_dotenv
from typing import Annotated
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.responses import PlainTextResponse # Import PlainTextResponse
from groq import Groq
from groq.types.chat import ChatCompletionMessageParam
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY environment variable not set. "
        "Please set your Groq API key before running the application."
    )

client = Groq(api_key=GROQ_API_KEY)

AI_SYSTEM_PROMPT = """You are an AI assistant, and your name is Alice, you live right now with me in India, Punjab, Amritsar,
                      created by Ester D. Kate.
                      I will provide you with transcribed audio text that you need to analyze to help the person.
                      
                      You are integrated into a server and have two main capabilities:
                      
                      1.  **Controlling my computer:**
                          The server is connected to an ESP, which makes requests to a Raspberry Pi Pico Zero (Waveshare version) configured as a USB Rubber Ducky.
                          When the user requests a computer action, you must output a **rubber ducky script** inside `[{{}}]`.
                          After providing the script, continue with a normal, natural language assistant response.
                          Example:
                          User says: "Alice, open Notepad and type 'Hello World'."
                          Your response: `[{{DELAY 1000\\nGUI r\\nSTRING notepad.exe\\nENTER\\nDELAY 500\\nSTRING Hello World\\nENTER}}]`
                          Okay, I've sent the command to open Notepad and type 'Hello World' on your computer.
                          also if suppose i ask you something which you dont have access to you can use my computer to access that
                          info like you can open chrome then there search it and take screen shot and take that as refrence infput
                          and then give me result
                      
                      2.  **Controlling smart home devices (lights, etc.) using relays:**
                          For this, you need to output **ONLY** a JSON object (no other text before or after it) to control devices.
                          The JSON object should use the exact device names and desired states as specified below, with no changes to capitalization or spacing.
                          The device names are:
                          - "soldering station"
                          - "lights of table"
                          - "lights of bed"
                          - "warm lighting"
                      
                          Format example for device control:
                          `{{"device1": "on", "device2": "off"}}`
                          (Where "device1" and "device2" are replaced by actual device names like "lights of table", and "on"/"off" are the states.)
                      
                      Now, here is the transcribed text you need to process: "{transcribed_text}"
                      """



app = FastAPI(
    title="Alice AI Assistant Backend",
    description="Backend for Alice AI assistant, integrating Groq ASR and LLM.",
    version="0.1.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

conversation_history: list[ChatCompletionMessageParam] = []

@app.post("/process_audio_input", response_class = PlainTextResponse) 
async def process_audio_input(audio_file: Annotated[UploadFile, File(description="The audio file to process.")]) -> str: 
    """
    Processes an audio file: transcribes it using Groq Whisper,
    then sends the transcribed text to Groq's Llama 4 Scout LLM for a response.
    """
    if not audio_file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Please upload an audio file."
        )

    try:
        audio_buffer = BytesIO(await audio_file.read())
        audio_buffer.name = audio_file.filename

        print(f"Transcribing audio with Groq Whisper: {audio_file.filename}")
        transcription = client.audio.transcriptions.create(
            file=(audio_buffer.name, audio_buffer.getvalue()),
            model="whisper-large-v3-turbo",
            response_format="json"
        )
        transcribed_text = transcription.text
        print(f"Transcription: {transcribed_text}")

        if not transcribed_text:
            return "I didn't hear anything. Please try again." 

        full_llm_prompt = AI_SYSTEM_PROMPT.format(transcribed_text=transcribed_text)

        messages_for_llm: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": full_llm_prompt},
            {"role": "user", "content": transcribed_text}
        ]
        
        print("Sending to Groq Llama 4 Scout LLM for response...")
        chat_completion = client.chat.completions.create(
            messages=messages_for_llm,
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            temperature=0.7,
            max_tokens=1024,
            top_p=1,
            stop=None,
            stream=False
        )

        llm_response_content = chat_completion.choices[0].message.content
        print(f"LLM Response: {llm_response_content}")

        return llm_response_content 

    except HTTPException:
        raise
    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during processing: {e}"
        )