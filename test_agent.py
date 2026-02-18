from cli_agent import _build_langchain_agent
import json

agent = _build_langchain_agent()
if agent:
    print("Agent built successfully. Testing prompt...")
    # Using a simple prompt that should trigger a tool
    try:
        result = agent.run("Predict the stock price for RELIANCE on NSE for tomorrow.")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Agent error: {e}")
else:
    print("Failed to build agent. Check OPENAI_API_KEY.")
