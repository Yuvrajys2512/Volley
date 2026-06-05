# Volley

A Gmail-connected agentic AI system that monitors your inbox for inbound leads, classifies them, and drafts personalized replies that match your natural writing tone — learned from your past email history via RAG.

Built on LangGraph (agent loop) + Gmail API (inbox access) + ChromaDB (tone RAG).

**Human-in-the-loop by design**: Volley never sends without your explicit approval.

## How It Works

```
Watch inbox → Classify intent → Retrieve your writing style → Draft reply → You approve → Send
```

## Stack

- **LangGraph** — stateful agent loop with human-in-the-loop interrupts
- **Gmail API** — inbox monitoring and sending
- **ChromaDB** — vector store for tone RAG
- **OpenAI / Anthropic** — classification and draft generation

## Status

🚧 In development
