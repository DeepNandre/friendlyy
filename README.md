# Friendly

**AI agents that make real phone calls for you.**

Get quotes from plumbers, book appointments with dentists, cancel subscriptions, wait on hold at HMRC — all through a simple chat interface. Friendly calls businesses in parallel, negotiates on your behalf, and reports back with results.

Built for the **Mistral Worldwide Hackathon 2026**.

---

## What It Does

Friendly is a chat-first app where AI agents do real-world tasks through phone calls:

| Agent | What It Does |
|-------|-------------|
| **Blitz** | Find services, get quotes, check availability. Calls multiple businesses in parallel. |
| **VibeCoder** | Build websites from natural language. "Make me a landing page for my dog walking business." |
| **Bounce** | Cancel subscriptions (Netflix, gym, etc.) by calling customer service. |
| **Queue** | Wait on hold for you (HMRC, banks) and alert you when a human picks up. |
| **Bid** | Negotiate bills lower (Sky, broadband) by calling retention departments. |

## How It Works

```
User Message → Mistral Router → Agent Selection → Real Phone Calls → Results via SSE
```

1. **Intent Classification**: User messages are classified by **Mistral Large** (via NVIDIA NIM) into the appropriate agent
2. **Parallel Calling**: Blitz agent uses **Twilio** to call multiple businesses simultaneously
3. **AI Voice**: **ElevenLabs** provides natural-sounding voice for phone conversations
4. **Real-time Updates**: Server-Sent Events (SSE) stream call status and results back to the UI
5. **Business Discovery**: **Google Places API** finds local businesses with phone numbers

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React/Vite)                    │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│  │  AI Chat    │  │  VibeCoder   │  │  Real-time Call       │   │
│  │  Interface  │  │  Preview     │  │  Status Widget        │   │
│  └─────────────┘  └──────────────┘  └───────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP + SSE
┌────────────────────────────▼────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│  │   Router    │  │    Blitz     │  │      Webhooks         │   │
│  │  (Mistral)  │  │  Orchestrator│  │     (Twilio)          │   │
│  └─────────────┘  └──────────────┘  └───────────────────────┘   │
└─────┬───────────────────┬───────────────────┬───────────────────┘
      │                   │                   │
┌─────▼─────┐  ┌──────────▼──────────┐  ┌─────▼─────┐
│  NVIDIA   │  │      Twilio +       │  │   Redis   │
│   NIM     │  │    ElevenLabs       │  │ (Sessions)│
│ (Mistral) │  │     (Voice)         │  │           │
└───────────┘  └─────────────────────┘  └───────────┘
```

## Tech Stack

### Frontend
- **React 18** + **TypeScript** + **Vite**
- **Tailwind CSS** + **shadcn/ui** for styling
- **Server-Sent Events** for real-time call updates

### Backend
- **FastAPI** with async/await throughout
- **Redis** for session storage and SSE event queues
- **W&B Weave** for observability and tracing

### AI & Voice
- **Mistral Large** via NVIDIA NIM (intent classification)
- **ElevenLabs** (AI voice for phone calls)
- **Twilio** (telephony / making actual calls)

### APIs
- **Google Places API** (business discovery)
- **NVIDIA NIM** (free Mistral inference)

---

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- Redis (local or Railway addon)
- API keys (see Environment Variables below)

### Frontend

```bash
# Install dependencies
npm install

# Set up environment
cp .env.example .env
# Edit .env with your VITE_BLITZ_API_BASE

# Start development server
npm run dev
```

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Start server
uvicorn main:app --reload --port 8000
```

### For Twilio Webhooks (Local Development)

```bash
# Install ngrok
brew install ngrok

# Start tunnel
ngrok http 8000

# Update BACKEND_URL in .env with ngrok URL
```

---

## Environment Variables

### Frontend (.env)
```bash
VITE_BLITZ_API_BASE=http://localhost:8000
VITE_VIBECODER_URL=http://localhost:3000
```

### Backend (.env)
```bash
# Twilio (for phone calls)
TWILIO_ACCOUNT_SID=ACxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxx
TWILIO_PHONE_NUMBER=+1234567890

# ElevenLabs (AI voice)
ELEVENLABS_API_KEY=xxxxxxx

# Google Places (business discovery)
GOOGLE_PLACES_API_KEY=xxxxxxx

# NVIDIA NIM - FREE! Get from build.nvidia.com
NVIDIA_API_KEY=nvapi-xxxxxxx

# W&B Weave - FREE! For observability
WANDB_API_KEY=xxxxxxx
WEAVE_PROJECT=friendly-blitz

# Redis
REDIS_URL=redis://localhost:6379

# App config
BACKEND_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:5173
DEMO_MODE=false  # Set to true for demo without real calls
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message, get routed to agent |
| GET | `/api/blitz/stream/{session_id}` | SSE stream for call updates |
| POST | `/api/webhooks/twilio/status` | Twilio call status webhook |
| POST | `/api/webhooks/twilio/gather` | Twilio speech gather webhook |
| GET | `/api/build/preview/{id}` | Get generated website preview |

---

## Demo Mode

For reliable hackathon demos, set `DEMO_MODE=true` in your backend `.env`. This:
- Skips real API calls (Twilio, Google Places)
- Uses hardcoded UK businesses (Pimlico Plumbers, etc.)
- Simulates realistic call timing and results
- Works without any API keys except NVIDIA

---

## Project Structure

```
/
├── src/                    # React frontend
│   ├── pages/
│   │   ├── AIChat.tsx     # Main chat interface
│   │   └── VibeCoder.tsx  # Website builder
│   ├── components/chat/
│   │   ├── BlitzCallWidget.tsx
│   │   ├── VibeCoderWidget.tsx
│   │   └── ComingSoonCard.tsx
│   └── hooks/
│       └── useBlitzStream.ts  # SSE hook
│
├── backend/
│   ├── api/
│   │   ├── chat.py        # Main chat endpoint
│   │   ├── blitz.py       # Blitz session endpoints
│   │   └── webhooks.py    # Twilio webhooks
│   ├── services/
│   │   ├── router.py      # Mistral intent classification
│   │   ├── blitz.py       # Call orchestration
│   │   ├── places.py      # Google Places integration
│   │   ├── twilio_caller.py
│   │   ├── elevenlabs_voice.py
│   │   └── demo_mode.py   # Demo simulation
│   └── core/
│       ├── config.py      # Settings
│       └── redis_client.py
│
└── README.md
```

---

## Key Features

### Parallel Calling
Blitz calls multiple businesses simultaneously, reducing wait time from 15+ minutes to under 60 seconds.

### Real-time Updates
Watch each call progress in real-time: ringing → connected → speaking → result.

### Smart Routing
Mistral Large classifies intents with high accuracy, routing to the right agent automatically.

### Natural Voice
ElevenLabs provides human-like voice for AI phone conversations.

### Observability
W&B Weave traces every request, call, and decision for debugging and analytics.

---

## Team

Built with AI assistance from Claude (Anthropic).

---

## License

MIT
