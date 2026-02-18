"""Unified LLM client for Groq and OpenAI."""

import json
from typing import Optional, Dict, Any
from config.settings import settings

try:
    from groq import Groq
    _HAS_GROQ = True
except ImportError:
    Groq = None
    _HAS_GROQ = False

try:
    from openai import OpenAI
    _HAS_OPENAI = True
except ImportError:
    OpenAI = None
    _HAS_OPENAI = False

class LLMClient:
    def __init__(self):
        self.groq_client = None
        self.openai_client = None
        
        if _HAS_GROQ and settings.groq_api_key:
            self.groq_client = Groq(api_key=settings.groq_api_key)
            
        if _HAS_OPENAI and settings.openai_api_key:
            self.openai_client = OpenAI(api_key=settings.openai_api_key)

    def chat_completion(self, system_prompt: str, user_prompt: str, temperature: float = 0.0, max_tokens: int = 500, json_mode: bool = False) -> str:
        """Execute chat completion using the best available client (defaults to Groq)."""
        
        # 1. Try Groq (User Preference)
        if self.groq_client:
            try:
                response_format = {"type": "json_object"} if json_mode else None
                response = self.groq_client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                print(f"Groq API Error: {e}")
                
        # 2. Try OpenAI as Fallback
        if self.openai_client:
            try:
                response_format = {"type": "json_object"} if json_mode else None
                response = self.openai_client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                print(f"OpenAI API Error: {e}")
                
        # 3. No client available
        return ""

llm_client = LLMClient()
