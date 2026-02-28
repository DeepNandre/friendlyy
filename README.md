# Friendly

AI agents that make real phone calls for you. Get quotes, book appointments, cancel subscriptions.

## Technologies

- Vite
- TypeScript
- React
- shadcn-ui
- Tailwind CSS

## Getting Started

```sh
# Install dependencies
npm i

# Start the development server
npm run dev
```

## Agent Dashboard Routes

- `/dashboard` - Friendly agent launcher (Blitz + VibeCoder)
- `/chat` - Blitz execution chat (real-time call updates)
- `/vibecoder` - Embedded VibeCoder interface (iframe wrapper with new-tab fallback)

## Environment Variables (Frontend)

```sh
# Blitz backend base URL (FastAPI)
VITE_BLITZ_API_BASE=http://localhost:8000

# Optional, backwards-compatible fallback used by some existing hooks
VITE_API_URL=http://localhost:8000

# Optional: customize SSE path shape.
VITE_BLITZ_STREAM_PATH=/api/blitz/stream

# VibeCoder frontend URL used by /vibecoder wrapper
VITE_VIBECODER_URL=http://localhost:3000
```
