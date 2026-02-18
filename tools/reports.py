from typing import Dict, Any
import datetime

def generate_text_report(ticker: str, prediction: Dict[str, Any], fundamentals: Dict[str, Any], sentiment: Dict[str, Any]) -> str:
    """Generate a formatted research report in text format."""
    report = f"""
AI STOCK RESEARCH REPORT - {ticker.upper()}
Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
------------------------------------------------------------

[1] PRICE PREDICTION
Point Estimate: {prediction.get('point_estimate', 'N/A')}
Confidence Level: {prediction.get('confidence_level', 'N/A')}
Lower Bound: {prediction.get('lower_bound', 'N/A')}
Upper Bound: {prediction.get('upper_bound', 'N/A')}

[2] FUNDAMENTALS
Company Name: {fundamentals.get('name', 'N/A')}
Sector: {fundamentals.get('sector', 'N/A')}
Industry: {fundamentals.get('industry', 'N/A')}
Market Cap: {fundamentals.get('market_cap', 0) / 1e9:.2f}B
P/E Ratio: {fundamentals.get('pe_ratio', 'N/A')}
Business Summary: {fundamentals.get('summary', 'N/A')[:300]}...

[3] NEWS SENTIMENT
Overall Sentiment: {sentiment.get('label', 'N/A').upper()}
Article Count: {sentiment.get('article_count', 0)}
Latest Headlines:
"""
    for h in sentiment.get('headlines', [])[:5]:
        report += f" - {h}\n"
        
    report += "\n------------------------------------------------------------\n"
    report += "DISCLAIMER: Educational use only. Not financial advice."
    
    return report
