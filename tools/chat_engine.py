import re
from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import json
import logging

class ChatResponse(BaseModel):
    message: str
    intent: str
    status: str = "success"
    data: Optional[Dict[str, Any]] = None
    action: Optional[str] = None

from tools.llm_client import llm_client

logger = logging.getLogger(__name__)

class ChatEngine:
    def __init__(self, pipeline, portfolio_manager, watchlist_manager):
        self.pipeline = pipeline
        self.portfolio_manager = portfolio_manager
        self.watchlist_manager = watchlist_manager
        self.history = [] # Memory management for the chat session

    def _get_history_context(self) -> str:
        """Format last few messages for the LLM."""
        if not self.history: return "No recent history."
        return "\n".join([f"{m['role'].upper()}: {m['content']}" for m in self.history[-10:]])

    def _get_context_summary(self) -> str:
        """Gather current state for LLM context."""
        try:
            portfolio = self.portfolio_manager.get_all()
            watchlist = self.watchlist_manager.get_all()
            
            p_summary = ", ".join([f"{p.ticker} ({p.quantity} @ {p.avg_price})" for p in portfolio]) or "Empty"
            w_summary = ", ".join([w.ticker for w in watchlist]) or "Empty"
            
            return f"Current Portfolio: {p_summary}\nCurrent Watchlist: {w_summary}"
        except Exception as e:
            logger.error(f"Context gathering error: {e}")
            return "Context unavailable."

    def process(self, message: str) -> ChatResponse:
        raw_message = message
        message_lower = message.lower().strip()
        context = self._get_context_summary()
        history_context = self._get_history_context()
        
        # 0. High-Intelligence LLM Loop
        system_prompt = f"""You are the STK-ENGINE Omni-Access Assistant. You are an elite quantitative analyst with full control over this trading workstation.
        
STATE_CONTEXT:
{context}

CONVERSATION_HISTORY:
{history_context}

YOUR_MISSION:
- You interpret user commands for PREDICTIONS, MARKET SCANS, PORTFOLIO MODS, and BACKTESTS.
- If the command matches a platform action, output JSON for the frontend to execute.
- If the user asks for financial research, advice, or general conversation, provide an expert response.
- DO NOT hallucinate portfolio data; only use what is provided in STATE_CONTEXT.
- If the user asks about their specific stocks, analyze the context.

JSON_PROTOCOL (MUST output strict JSON if an action is needed):
{{
  "intent": "PREDICT" | "SCAN" | "PORTFOLIO_ADD" | "WATCHLIST_ADD" | "ANALYZE" | "BACKTEST" | "ANALYZE_ROTATION" | "ANALYZE_CORRELATION" | "CHAT",
  "data": {{ "ticker": "SYMBOL", "exchange": "NSE"|"BSE"|"NYSE"|"NASDAQ", "target_date": "YYYY-MM-DD", "history_days": int, "quantity": float, "price": float, "days": int, "preset": "NIFTY50"|"BLUECHIP_US" }},
  "action": "RUN_PREDICTION" | "RUN_SCAN" | "REFRESH_PORTFOLIO" | "REFRESH_WATCHLIST" | "RUN_ANALYSIS" | "RUN_BACKTEST" | "RUN_ROTATION" | "RUN_CORRELATION" | "NONE",
  "response": "A clean, professional expert response."
}}

CRITICAL RULES:
- Use STATE_CONTEXT for portfolio queries.
- If it's just a conversation, use intent="CHAT" and action="NONE".
- ALL JSON VALUES MUST BE LITERALS. DO NOT use expressions like "5 * 365" or "100/2".
"""
        try:
            # Use Groq/OpenAI via unified client with increased max_tokens for complex reasoning
            llm_json = llm_client.chat_completion(system_prompt, f"User: {raw_message}", json_mode=True, max_tokens=800)
            if llm_json:
                # Store in history
                self.history.append({"role": "user", "content": raw_message})

                # Handle possible markdown wrapping
                clean_json = llm_json.strip()
                if clean_json.startswith("```json"):
                    clean_json = clean_json.split("```json", 1)[1].split("```", 1)[0].strip()
                elif clean_json.startswith("```"):
                    clean_json = clean_json.split("```", 1)[1].split("```", 1)[0].strip()
                
                res = json.loads(clean_json)
                self.history.append({"role": "assistant", "content": res.get("response", "")})
                intent = res.get("intent", "UNKNOWN")
                
                if intent != "UNKNOWN" and intent != "CHAT":
                    data = res.get("data", {})
                    # Direct data mutation if needed
                    if intent == "PORTFOLIO_ADD":
                         self.portfolio_manager.add_position(
                             data.get("ticker", "").upper(), 
                             data.get("exchange", "NSE").upper(), 
                             float(data.get("quantity", 0)), 
                             float(data.get("price", 0))
                         )
                    elif intent == "WATCHLIST_ADD":
                         self.watchlist_manager.add(data.get("ticker", "").upper(), data.get("exchange", "NSE").upper())
                    
                    return ChatResponse(
                        message=res.get("response", "Executing command..."),
                        intent=intent,
                        action=res.get("action", "NONE"),
                        data=data
                    )
                elif intent == "CHAT":
                    return ChatResponse(
                        message=res.get("response", "I'm here to help."),
                        intent="CHAT",
                        action="NONE"
                    )
        except Exception as e:
            logger.error(f"Chat Omni-Access Error: {e}")

        # 1. Regex Fallback
        predict_match = re.search(r"(?:predict|forecast|prediction for)\s+([a-z0-9\-.]+)", message_lower)
        if predict_match:
            ticker = predict_match.group(1).upper()
            return ChatResponse(
                message=f"I've identified a prediction request for {ticker}. Initializing...",
                intent="PREDICT",
                action="RUN_PREDICTION",
                data={"ticker": ticker}
            )

        if "help" in message_lower or "protocols" in message_lower:
            return ChatResponse(
                message="""STK-ENGINE NEURAL PROTOCOLS:
1. [PREDICT]: 'Predict AAPL' or 'Forecast RELIANCE for 2026'
2. [SCAN]: 'Run market scan' or 'Scan NIFTY50'
3. [PORTFOLIO]: 'Add 10 shares of MSFT at 400'
4. [ANALYTIC]: 'Show sector rotation' or 'Correlation map'
5. [SYSTEM]: 'Clear memory' to reset context.""",
                intent="HELP",
                status="info"
            )

        if "clear memory" in message_lower or "reset context" in message_lower:
            self.history = []
            return ChatResponse(
                message="Neural memory cleared. Conversation context has been reset to zero-state.",
                intent="RESET_MEMORY",
                action="NONE"
            )

        return ChatResponse(
            message="I'm the STK-ENGINE Omni-Assistant. How can I help you manage your trading workstation today?",
            intent="HELP",
            status="info"
        )
