import asyncio
import json
import logging
from agents.nlp_pipeline.orchestrator import NLPContextOrchestrator
from agents.historical_db.reader import HistoricalDBReader
from agents.historical_db.clients import AsyncCosmosClientWrapper, AsyncAISearchWrapper
from agents.historical_db.embeddings import EmbeddingService

# Set up basic logging so you can see your orchestrator thinking
logging.basicConfig(level=logging.DEBUG)

async def main():
    print("Loading test payload...")
    with open("test_payload.json", "r") as f:
        payload = json.load(f)

    # Mock infrastructure clients (Dev B's job later)
    cosmos = AsyncCosmosClientWrapper("https://mock-endpoint", "db", "container", "key")
    search = AsyncAISearchWrapper("https://mock-endpoint", "index", "key")
    embed = EmbeddingService("https://mock-endpoint", "key")
    reader = HistoricalDBReader(cosmos, search, embed)

    # Initialize your pipeline brain
    orchestrator = NLPContextOrchestrator(historical_db_reader=reader)

    print("\n🚀 Firing up NLP Context Orchestrator...\n")
    result = await orchestrator.process(payload)

    print("\n" + "="*40)
    print("🎉 FINAL STRUCTURED CONTEXT 🎉")
    print("="*40)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())