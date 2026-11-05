import os
from pathlib import Path
import time
import random
import json
import asyncio
import aiohttp
from typing import List, Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.schema import AIMessage

# Load environment variables
load_dotenv()

OUTPUT_FILE = Path(__file__).resolve().parent.parent / "data" / "seed" / "synthetic_conversations.json"

GROQ_API_KEYS = [k for k in [os.getenv("GROQ_API_KEY")] if k]

# Groq models and their rate limits
GROQ_MODELS = [
    {"name": "gemma-7b-it", "rpm": 30, "tpm": 14400, "max_tokens": 15000, "daily_limit": 500000},
    {"name": "gemma2-9b-it", "rpm": 30, "tpm": 14400, "max_tokens": 15000, "daily_limit": 500000},
    {"name": "llama-3.1-70b-versatile", "rpm": 30, "tpm": 14400, "max_tokens": 20000, "daily_limit": 500000},
    {"name": "llama-3.1-8b-instant", "rpm": 30, "tpm": 14400, "max_tokens": 20000, "daily_limit": 500000},
    {"name": "llama3-70b-8192", "rpm": 30, "tpm": 14400, "max_tokens": 6000, "daily_limit": 500000},
    {"name": "llama3-8b-8192", "rpm": 30, "tpm": 14400, "max_tokens": 30000, "daily_limit": 500000},
    {"name": "llama3-groq-70b-8192-tool-use-preview", "rpm": 30, "tpm": 14400, "max_tokens": 15000, "daily_limit": 500000},
    {"name": "llama3-groq-8b-8192-tool-use-preview", "rpm": 30, "tpm": 14400, "max_tokens": 15000, "daily_limit": 500000},
    {"name": "mixtral-8x7b-32768", "rpm": 30, "tpm": 14400, "max_tokens": 5000, "daily_limit": 500000},
    {"name": "llama-3.2-11b-text-preview", "rpm": 30, "tpm": 7000, "max_tokens": 7000, "daily_limit": 500000},
    {"name": "llama-3.2-1b-preview", "rpm": 30, "tpm": 7000, "max_tokens": 7000, "daily_limit": 500000},
    {"name": "llama-3.2-3b-preview", "rpm": 30, "tpm": 7000, "max_tokens": 7000, "daily_limit": 500000},
    {"name": "llama-3.2-90b-text-preview", "rpm": 30, "tpm": 7000, "max_tokens": 7000, "daily_limit": 500000},
]

class ModelManager:
    def __init__(self):
        self.last_request_time = {model['name']: {key: 0 for key in GROQ_API_KEYS} for model in GROQ_MODELS}
        self.requests_this_minute = {model['name']: {key: 0 for key in GROQ_API_KEYS} for model in GROQ_MODELS}

    async def can_make_request(self, model_name: str, api_key: str) -> bool:
        current_time = time.time()
        if current_time - self.last_request_time[model_name][api_key] >= 60:
            self.requests_this_minute[model_name][api_key] = 0
            self.last_request_time[model_name][api_key] = current_time
        model_info = next(model for model in GROQ_MODELS if model['name'] == model_name)
        return self.requests_this_minute[model_name][api_key] < model_info['rpm']

    async def increment_request(self, model_name: str, api_key: str) -> None:
        self.requests_this_minute[model_name][api_key] += 1

def create_prompt(category: str) -> str:
    prompts = f"""
You are a virtual assistant for Zaldi, an Indian online ethnic-fashion store. Write a short conversation on the topic: {category}.
Make it a natural, friendly, unique conversation with at least 3-4 exchanges between Human and AI.
Use English, Hindi (Roman script) or Hinglish, as an Indian customer would. Prices are in Indian Rupees (Rs.).
Do not repeat phrases or ideas used in earlier conversations.

Example for category "chitchat":
Human: Hi! Aaj kal baarish bahut ho rahi hai.
AI: Haan, monsoon poora swing mein hai! Aise mausam mein chai aur pakode best lagte hain. Aap kya plan kar rahe ho aaj?
Human: Bas ghar par movie dekhne ka mann hai.
AI: Mazaa aayega! Waise monsoon mein light cotton kurtas bahut comfortable rehte hain, ghar par bhi aur bahar bhi.

Another example for category "chitchat":
Human: Diwali ki taiyari shuru ho gayi?
AI: Bilkul! Ghar ki safai aur rangoli ke saath. Aapki Diwali plans kya hain?
Human: Family ke saath puja aur dinner.
AI: Sounds lovely! Festive season mein log aksar silk kurtas aur sarees choose karte hain. Kuch dikhaun?

Example for category "product":
Human: Hi, I am looking for a saree for my cousin's wedding.
AI: Congratulations! Are you thinking of a silk saree, such as Banarasi or Kanjivaram, or something lighter?
Human: Banarasi, budget around Rs. 10,000.
AI: Our Banarasi Silk Saree in maroon with a zari border is Rs. 8,999 and comes with a blouse piece. Would you like to see other colours?
Human: Is it available with cash on delivery?
AI: Yes, COD is available for orders up to Rs. 15,000 with a Rs. 49 COD fee, and delivery to metro cities takes 2-4 business days.

Another example for category "product":
Human: Mujhe ek kurta chahiye office ke liye, size L.
AI: Zaroor! Cotton ya linen? Hamare paas Chikankari Cotton Kurta Rs. 1,499 mein aur Jaipuri Block Print Kurti Rs. 899 mein hai.
Human: Men's kurta hai kya?
AI: Ji, Silk Kurta for Men Rs. 2,199 mein L size mein available hai, aur Straight Kurta Pyjama Set Rs. 1,899 mein.

Conversation:
Human: Hello!
AI: """
    return prompts

async def generate_conversation(session: aiohttp.ClientSession, llm: ChatGroq, prompt: PromptTemplate) -> str:
    chain = prompt | llm
    return await chain.ainvoke({})

async def generate_data(session: aiohttp.ClientSession, api_key: str, model_name: str, model_manager: ModelManager, categories: List[str], total_data: int, data_queue: asyncio.Queue) -> None:
    while True:
        if await model_manager.can_make_request(model_name, api_key):
            llm = ChatGroq(temperature=0.9, model=model_name, groq_api_key=api_key, client=session)
            category = random.choice(categories)
            prompt = PromptTemplate(input_variables=[], template=create_prompt(category))
            
            try:
                conversation = await generate_conversation(session, llm, prompt)
                await model_manager.increment_request(model_name, api_key)
                
                ai_response = conversation.content if isinstance(conversation, AIMessage) else str(conversation)
                cleaned_response = ai_response.replace("Human:", "\nHuman:").replace("AI:", "\nAI:").strip()
                
                data = {
                    "conversation": cleaned_response,
                    "category": category
                }
                await data_queue.put(data)
                print(f"Generated ({category}) using {model_name} with API key {api_key[-4:]}:\n{cleaned_response}\n---")
                
                if data_queue.qsize() >= total_data:
                    return
            except Exception as e:
                print(f"Error with model {model_name} and API key {api_key[-4:]}: {str(e)}")
        else:
            await asyncio.sleep(1)

async def append_to_json(data: List[dict], filename: str = str(OUTPUT_FILE)) -> None:
    existing_data = []
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {filename} is empty or contains invalid JSON. Starting with an empty list.")
    
    existing_data.extend(data)
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)
    
    print(f"Added {len(data)} conversations to {filename}. Total: {len(existing_data)}.")

async def main() -> None:
    model_manager = ModelManager()
    categories = ["product", "chitchat"]
    total_data = 1000
    data_queue: asyncio.Queue = asyncio.Queue()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for api_key in GROQ_API_KEYS:
            for model in GROQ_MODELS:
                task = asyncio.create_task(generate_data(session, api_key, model['name'], model_manager, categories, total_data, data_queue))
                tasks.append(task)
        
        all_data = []
        while len(all_data) < total_data:
            data = await data_queue.get()
            all_data.append(data)
            if len(all_data) >= total_data:
                for task in tasks:
                    task.cancel()
                break
        
        await append_to_json(all_data[:total_data])

if __name__ == "__main__":
    asyncio.run(main())
