# NNRG AI Platform — Unified Project

A full-stack AI assistant platform for NNRG Group of Institutions, combining three components into one project.

## 📁 Project Structure

```
nnrg-unified/
├── start.sh                  ← ✅ Run this to start everything
│
├── agent-backend/            ← FastAPI · Port 8000
│   ├── app.py                   RAG chat + PDF upload endpoints
│   ├── rag.py                   LangChain RAG pipeline
│   ├── vector_db.py             ChromaDB vector store
│   ├── embeddings.py            Sentence-Transformers embeddings
│   ├── llm.py                   Groq LLM integration
│   ├── scraper.py               NNRG website scraper
│   ├── pdf_loader.py            PDF text extraction
│   ├── prompts.py               Prompt templates
│   ├── requirements.txt
│   └── .env                  ← ⚠️  Add your GROQ_API_KEY here
│
├── knowledgebot-backend/     ← FastAPI · Port 8001
│   ├── app.py                   Chat endpoint with intent detection
│   ├── services/
│   │   ├── gemini_service.py    Gemini AI responses
│   │   ├── intent_service.py    Route: website vs. general
│   │   ├── website_service.py   Live NNRG website scraper
│   │   └── pdf_service.py
│   ├── requirements.txt
│   └── .env                  ← ⚠️  Add your GEMINI_API_KEY here
│
└── frontend/                 ← React + Vite · Port 5173
    ├── src/
    │   ├── components/          Navbar, Hero, Chat, etc.
    │   └── App.jsx
    └── package.json
```

## 🚀 Quick Start

### Step 1 — Set up API keys

**Agent Backend** — edit `agent-backend/.env`:
```env
GROQ_API_KEY=your_groq_api_key_here     # Free at console.groq.com
```

**KnowledgeBot Backend** — edit `knowledgebot-backend/.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here # Free at aistudio.google.com
```

### Step 2 — Run everything with one command

```bash
chmod +x start.sh
./start.sh
```

That's it! The script will:
1. Create Python virtual environments automatically
2. Install all Python dependencies
3. Install frontend npm packages
4. Start all three services

### Step 3 — Open in browser

| Service       | URL                      |
|---------------|--------------------------|
| 🌐 Frontend   | http://localhost:5173    |
| 🤖 Agent API  | http://localhost:8000    |
| 📚 KnowledgeBot | http://localhost:8001  |

Press **Ctrl+C** to stop everything cleanly.

---

## 🔌 API Reference

### Agent Backend (port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat` | Ask a question (RAG pipeline) |
| `POST` | `/upload` | Upload a PDF to index |
| `GET`  | `/api/sources` | List indexed PDFs |
| `GET`  | `/health` | Health check |
| `DELETE` | `/session` | Clear session |

### KnowledgeBot Backend (port 8001)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/chat?prompt=...` | Ask a question (Gemini AI) |
| `GET`  | `/` | Health check |

---

## 🛠 Requirements

- Python 3.10+
- Node.js 18+
- npm

---

## 🔑 Getting Free API Keys

- **GROQ_API_KEY**: [console.groq.com/keys](https://console.groq.com/keys)
- **GEMINI_API_KEY**: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
