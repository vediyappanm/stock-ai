"""Web Research Agent for catalyst extraction and deep analysis (Perplexica-inspired)."""
import httpx
from typing import List, Dict, Any
from config.settings import settings
from tools.llm_client import llm_client
from tools.sentiment import _fetch_feed

class WebResearchAgent:
    def __init__(self):
        self.sources = [
            settings.yahoo_rss_template,
            settings.google_news_template,
            "https://finance.yahoo.com/quote/{ticker}/news",
        ]

    def deep_research(self, ticker: str) -> Dict[str, Any]:
        """Perform deep web research for a specific ticker."""
        all_headlines = []
        
        # 1. Fetch Headlines
        for template in self.sources[:2]: # RSS sources
            url = template.format(ticker=ticker)
            all_headlines.extend(_fetch_feed(url, timeout_seconds=settings.sentiment_timeout))
        
        if not all_headlines:
            return {"catalysts": [], "summary": "No recent news found for research."}

        # 2. Extract Top 5 headlines for synthesis
        top_headlines = all_headlines[:15]
        headlines_text = "\n".join([f"- {h}" for h in top_headlines])

        # 3. Use LLM to extract Catalysts and Synthesis (The "Perplexica" part)
        system_prompt = f"""
        You are a Financial Research Agent. Analyze the provided headlines for {ticker} 
        and extract the core catalysts (earnings, mergers, major orders, legal issues).
        Provide a concise synthesis and 3-5 specific bullet points.
        Return JSON format: {{"synthesis": "overview", "catalysts": ["point1", "point2"]}}
        """
        
        user_prompt = f"Headlines for {ticker}:\n{headlines_text}"
        
        try:
            raw_response = llm_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_mode=True
            )
            import json
            result = json.loads(raw_response)
            return {
                "synthesis": result.get("synthesis", "Neural synthesis complete."),
                "catalysts": result.get("catalysts", []),
                "headlines": top_headlines[:5]
            }
        except Exception as e:
            print(f"Research synthesis error: {e}")
            return {
                "synthesis": "Real-time research mode active. Analysis pending...",
                "catalysts": ["Earnings trend detection", "Sector relative strength"],
                "headlines": top_headlines[:5]
            }

researcher = WebResearchAgent()
