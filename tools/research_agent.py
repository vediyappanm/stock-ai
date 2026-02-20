"""
Research Agent - Integrates with Dashboard
Provides deep research with citations, catalysts, and streaming
"""
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime, timedelta
from config.settings import settings
from tools.llm_client import llm_client
from tools.researcher import researcher

logger = logging.getLogger(__name__)

class ResearchAgent:
    """
    Main research agent for dashboard integration.
    Handles research requests and returns structured data with citations.
    """
    
    def __init__(self):
        self.researcher = researcher
        self.cache: Dict[str, tuple[Dict[str, Any], datetime]] = {}
        self.cache_ttl = 30  # minutes
    
    async def research_ticker(self, ticker: str, exchange: str = "NSE") -> Dict[str, Any]:
        """
        Main research endpoint - returns comprehensive research data.
        
        Args:
            ticker: Stock ticker (e.g., "NVDA", "RELIANCE")
            exchange: Exchange (NSE, BSE, NYSE, NASDAQ)
        
        Returns:
            {
                "success": true,
                "ticker": "NVDA",
                "exchange": "NASDAQ",
                "research": {
                    "synthesis": "Analysis with citations [1], [2]...",
                    "catalysts": [...],
                    "sources": {...},
                    "sentiment": "bullish|neutral|bearish",
                    "confidence": 0.85
                }
            }
        """
        try:
            logger.info(f"Research request: {ticker} ({exchange})")
            
            # Run async research
            result = await self.researcher.deep_research_async(ticker, exchange)
            
            return {
                "success": True,
                "ticker": ticker,
                "exchange": exchange,
                "research": result,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Research error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "ticker": ticker,
                "exchange": exchange
            }
    
    async def research_ticker_streaming(self, ticker: str, exchange: str = "NSE") -> AsyncGenerator[str, None]:
        """
        Streaming research - returns progress updates as Server-Sent Events.
        
        Yields:
            JSON strings with status updates:
            - {"status": "starting", "message": "..."}
            - {"status": "finnhub", "message": "..."}
            - {"status": "search", "message": "..."}
            - {"status": "fetching", "message": "..."}
            - {"status": "rag", "message": "..."}
            - {"status": "synthesizing", "message": "..."}
            - {"status": "complete", "result": {...}}
        """
        try:
            async for chunk in self.researcher.stream_research(ticker, exchange):
                yield chunk
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            fallback = self.researcher._fallback_research_structured(ticker, exchange)
            yield f'data: {{"status": "error", "result": {json.dumps(fallback)}}}\n\n'
    
    def format_research_for_dashboard(self, research: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format research data for dashboard display.
        
        Returns:
            {
                "synthesis": "...",
                "catalysts": [
                    {
                        "title": "Catalyst name",
                        "description": "...",
                        "confidence": 0.85,
                        "impact": "positive|negative|neutral",
                        "sources": ["[1]", "[2]"]
                    }
                ],
                "sources": [
                    {
                        "id": 1,
                        "title": "Article title",
                        "url": "https://...",
                        "source": "finnhub|duckduckgo",
                        "relevance": 0.92
                    }
                ],
                "sentiment": "bullish",
                "confidence": 0.85,
                "risks": ["Risk 1", "Risk 2"],
                "metrics": {"metric": "value"}
            }
        """
        try:
            # Extract sources
            sources_list = []
            sources_map = research.get("sources", {})
            for source_id, source_data in sources_map.items():
                sources_list.append({
                    "id": int(source_id),
                    "title": source_data.get("title", ""),
                    "url": source_data.get("url", ""),
                    "source": source_data.get("source", "unknown"),
                    "relevance": source_data.get("relevance_score", 0)
                })
            
            # Extract catalysts with source references
            catalysts_list = []
            for catalyst in research.get("catalysts", []):
                source_ids = catalyst.get("source_ids", [])
                source_refs = [f"[{sid}]" for sid in source_ids]
                
                catalysts_list.append({
                    "title": catalyst.get("catalyst", "")[:100],
                    "description": catalyst.get("catalyst", ""),
                    "confidence": catalyst.get("confidence", 0),
                    "impact": catalyst.get("impact", "neutral"),
                    "sources": source_refs
                })
            
            return {
                "synthesis": research.get("synthesis", ""),
                "catalysts": catalysts_list,
                "sources": sources_list,
                "sentiment": research.get("sentiment", "neutral"),
                "confidence": research.get("confidence_overall", 0),
                "risks": research.get("risk_factors", []),
                "metrics": research.get("key_metrics", {}),
                "headlines": research.get("headlines", []),
                "timestamp": research.get("research_timestamp", "")
            }
        except Exception as e:
            logger.error(f"Format error: {e}")
            return {
                "synthesis": "Error formatting research data",
                "catalysts": [],
                "sources": [],
                "sentiment": "neutral",
                "confidence": 0,
                "risks": [],
                "metrics": {}
            }
    
    async def compare_tickers(self, tickers: List[str], exchange: str = "NSE") -> Dict[str, Any]:
        """
        Compare research across multiple tickers.
        
        Args:
            tickers: List of tickers to compare
            exchange: Exchange for all tickers
        
        Returns:
            {
                "comparison": [
                    {
                        "ticker": "NVDA",
                        "sentiment": "bullish",
                        "confidence": 0.85,
                        "catalysts": 3,
                        "top_catalyst": "..."
                    }
                ]
            }
        """
        try:
            comparison = []
            
            # Research all tickers in parallel
            tasks = [self.research_ticker(ticker, exchange) for ticker in tickers]
            results = await asyncio.gather(*tasks)
            
            for result in results:
                if result.get("success"):
                    research = result.get("research", {})
                    catalysts = research.get("catalysts", [])
                    
                    comparison.append({
                        "ticker": result.get("ticker"),
                        "sentiment": research.get("sentiment", "neutral"),
                        "confidence": research.get("confidence_overall", 0),
                        "catalysts_count": len(catalysts),
                        "top_catalyst": catalysts[0].get("catalyst", "") if catalysts else "N/A",
                        "risk_count": len(research.get("risk_factors", []))
                    })
            
            return {
                "success": True,
                "comparison": comparison,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Comparison error: {e}")
            return {
                "success": False,
                "error": str(e),
                "comparison": []
            }
    
    async def get_catalyst_insights(self, ticker: str, exchange: str = "NSE") -> Dict[str, Any]:
        """
        Get detailed catalyst insights for a ticker.
        
        Returns:
            {
                "ticker": "NVDA",
                "catalysts": [
                    {
                        "catalyst": "...",
                        "confidence": 0.85,
                        "impact": "positive",
                        "sources": [1, 2],
                        "details": "..."
                    }
                ],
                "catalyst_summary": {
                    "positive": 2,
                    "negative": 1,
                    "neutral": 0
                }
            }
        """
        try:
            result = await self.research_ticker(ticker, exchange)
            
            if not result.get("success"):
                return {"success": False, "error": result.get("error")}
            
            research = result.get("research", {})
            catalysts = research.get("catalysts", [])
            
            # Summarize catalysts by impact
            summary = {
                "positive": sum(1 for c in catalysts if c.get("impact") == "positive"),
                "negative": sum(1 for c in catalysts if c.get("impact") == "negative"),
                "neutral": sum(1 for c in catalysts if c.get("impact") == "neutral")
            }
            
            return {
                "success": True,
                "ticker": ticker,
                "catalysts": catalysts,
                "catalyst_summary": summary,
                "total_catalysts": len(catalysts),
                "average_confidence": sum(c.get("confidence", 0) for c in catalysts) / len(catalysts) if catalysts else 0
            }
        except Exception as e:
            logger.error(f"Catalyst insights error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_risk_analysis(self, ticker: str, exchange: str = "NSE") -> Dict[str, Any]:
        """
        Get risk analysis for a ticker.
        
        Returns:
            {
                "ticker": "NVDA",
                "risks": ["Risk 1", "Risk 2"],
                "risk_level": "medium",
                "mitigation": ["Mitigation 1", "Mitigation 2"]
            }
        """
        try:
            result = await self.research_ticker(ticker, exchange)
            
            if not result.get("success"):
                return {"success": False, "error": result.get("error")}
            
            research = result.get("research", {})
            risks = research.get("risk_factors", [])
            
            # Determine risk level
            risk_count = len(risks)
            if risk_count == 0:
                risk_level = "low"
            elif risk_count <= 2:
                risk_level = "medium"
            else:
                risk_level = "high"
            
            return {
                "success": True,
                "ticker": ticker,
                "risks": risks,
                "risk_level": risk_level,
                "risk_count": risk_count,
                "confidence": research.get("confidence_overall", 0)
            }
        except Exception as e:
            logger.error(f"Risk analysis error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_sentiment_analysis(self, ticker: str, exchange: str = "NSE") -> Dict[str, Any]:
        """
        Get sentiment analysis for a ticker.
        
        Returns:
            {
                "ticker": "NVDA",
                "sentiment": "bullish",
                "confidence": 0.85,
                "positive_catalysts": 2,
                "negative_catalysts": 1,
                "neutral_catalysts": 0
            }
        """
        try:
            result = await self.research_ticker(ticker, exchange)
            
            if not result.get("success"):
                return {"success": False, "error": result.get("error")}
            
            research = result.get("research", {})
            catalysts = research.get("catalysts", [])
            
            # Count catalysts by impact
            positive = sum(1 for c in catalysts if c.get("impact") == "positive")
            negative = sum(1 for c in catalysts if c.get("impact") == "negative")
            neutral = sum(1 for c in catalysts if c.get("impact") == "neutral")
            
            return {
                "success": True,
                "ticker": ticker,
                "sentiment": research.get("sentiment", "neutral"),
                "confidence": research.get("confidence_overall", 0),
                "positive_catalysts": positive,
                "negative_catalysts": negative,
                "neutral_catalysts": neutral,
                "total_catalysts": len(catalysts)
            }
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Global instance
research_agent = ResearchAgent()
