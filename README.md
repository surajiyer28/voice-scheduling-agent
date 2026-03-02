# Voice Scheduling Agent

A production-grade voice scheduling system where callers dial a VAPI phone number, speak with an AI assistant powered by GPT-4o, and book 1-hour meetings automatically — complete with Google Calendar events (in the host's timezone) and email confirmations via Gmail API. Company hosts manage their availability and upcoming meetings through a real-time Next.js dashboard.

## Live Demo

- **Frontend (Vercel):** [voice-scheduling-agent-eight.vercel.app](https://voice-scheduling-agent-eight.vercel.app)

## How to Test the Voice Agent

1. Call the VAPI phone number (configured in the VAPI dashboard).
2. The AI assistant greets you and asks for your name.
3. Provide a preferred date — the agent confirms the day name and date.
4. The agent calls `check_availability` and reads out available times with the timezone label (e.g. "9 AM, 10 AM, and 2 PM Eastern").
5. Pick a time, state the meeting purpose, and provide your email address.
6. The agent calls `create_booking`, confirms the booking details with host name and timezone, and sends an email confirmation.
7. The host dashboard updates in real-time showing the new booking.

## Architecture

```
Caller → VAPI Phone Number → GPT-4o (via VAPI)
                                    ↓
                             FastAPI (Cloud Run)
                             ├── Supabase PostgreSQL
                             ├── Google Calendar API
                             └── Gmail API (email confirmations)

Host → Next.js (Vercel) → FastAPI → Supabase
             ↑
       Supabase Realtime (WebSocket)
```

### Request Flow

1. **Inbound call** → VAPI hits `POST /api/vapi/webhook` with `assistant-request` event
2. Backend returns a full inline assistant config (system prompt with today's date, tool definitions, voice settings)
3. GPT-4o drives the conversation, calling tools via `tool-calls` events:
   - `check_availability` → queries all active hosts' availability, returns deduplicated slots in host-local timezone
   - `create_booking` → creates DB record + Google Calendar event + sends Gmail confirmation
   - `log_call_event` → audit logging
4. VAPI sends tool call payloads to the webhook; backend parses `toolWithToolCallList`, executes, and returns JSON string results

## Calendar Integration

Each host authenticates via Google OAuth during sign-in (scopes: `calendar`, `calendar.events`, `gmail.send`). The backend stores OAuth access and refresh tokens, refreshing them automatically before every API call.

### How Bookings Work

1. **Availability check** — `availability_service.get_available_slots()` interprets the host's availability times (e.g. 9am-5pm) in their configured timezone, converts to UTC for DB queries, then converts slots back to host-local time for the voice agent to read aloud.

2. **Host selection** — `availability_service.find_best_host()` checks all active hosts: converts the requested time to each host's local timezone, compares against their availability window, checks for DB booking overlaps, and calls `calendar_service.check_free_busy()` against their Google Calendar. The host with the fewest bookings that day wins.

3. **Event creation** — `calendar_service.create_event()` creates a Google Calendar event with the `timeZone` field set to the host's timezone so it renders correctly on their calendar. The event includes caller name and meeting purpose in the description.

4. **Email confirmation** — `email_service.send_booking_confirmation()` sends via the host's Gmail using OAuth tokens. Times are formatted in the host's timezone with the abbreviation (e.g. "Monday, March 5, 2026 at 2:00 PM EST").

5. **Meeting link** — Hosts can click "Send Invite" on the dashboard to generate a Google Meet link (`calendar_service.add_meet_link()`) and send it with an .ics calendar attachment.

6. **Cancellation** — Deletes the Google Calendar event and marks the booking as cancelled.

7. **Cleanup** — A background task runs every hour, deleting bookings and calendar events that ended more than 48 hours ago.

### Timezone Handling

- Hosts configure their timezone on the Availability page (US timezones: Eastern, Central, Mountain, Pacific, Alaska, Hawaii)
- Availability times (e.g. 9am-5pm) are interpreted in the host's timezone
- All DB storage is UTC
- Voice agent announces times with timezone label ("2 PM Eastern")
- Dashboard and emails display times in the host's timezone
- Google Calendar events use the host's timezone so they render correctly
- .ics attachments use UTC (calendar apps auto-convert)

## Local Development

### Prerequisites

- Docker and Docker Compose
- Node.js 20+
- A `.env` file in `backend/` (copy from `backend/.env.example`)
- A `.env.local` file in `frontend/` (copy from `frontend/.env.example`)
- ngrok (for VAPI to reach your local backend)

### Start backend

```bash
docker compose up --build -d backend
```

Expose it via ngrok:

```bash
ngrok http 8080
```

Set `BACKEND_URL` in `backend/.env` to the ngrok URL.

The backend will be available at `http://localhost:8080`.
Visit `http://localhost:8080/health` to confirm it is running.

### Start frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at `http://localhost:3000`.

## Deployment

### Backend — Google Cloud Run

```bash
# Build and push Docker image
gcloud builds submit ./backend --tag us-central1-docker.pkg.dev/PROJECT_ID/voice-scheduler/backend:latest

# Deploy
gcloud run deploy voice-scheduler-backend \
  --image us-central1-docker.pkg.dev/PROJECT_ID/voice-scheduler/backend:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --env-vars-file env.yaml
```

### Frontend — Vercel

1. Import the GitHub repo in Vercel
2. Set **Root Directory** to `frontend`
3. Add all environment variables from `frontend/.env.example`
4. Deploy

### Post-deploy Checklist

- [ ] Run SQL migration: `ALTER TABLE hosts ADD COLUMN timezone TEXT NOT NULL DEFAULT 'America/New_York';`
- [ ] Update `BACKEND_URL` on Cloud Run to the actual service URL
- [ ] Update `FRONTEND_URL` on Cloud Run to the Vercel domain
- [ ] Add Vercel domain to Google Console authorized origins and redirect URIs
- [ ] Update VAPI phone number webhook URL to Cloud Run URL
- [ ] Sign in on the Vercel URL to re-authenticate with all OAuth scopes

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg format) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (server-side only) |
| `VAPI_API_KEY` | VAPI API key |
| `VAPI_WEBHOOK_SECRET` | Secret to validate VAPI webhook calls |
| `GOOGLE_CLIENT_ID` | Google OAuth 2.0 Client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 2.0 Client Secret |
| `FRONTEND_URL` | Frontend URL for CORS (e.g. `https://your-app.vercel.app`) |
| `BACKEND_URL` | Public backend URL (Cloud Run URL or ngrok for local dev) |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `NEXTAUTH_URL` | Base URL of the frontend app |
| `NEXTAUTH_SECRET` | Random secret for NextAuth (`openssl rand -base64 32`) |
| `GOOGLE_CLIENT_ID` | Same Google OAuth Client ID as backend |
| `GOOGLE_CLIENT_SECRET` | Same Google OAuth Client Secret as backend |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon (public) key |
| `NEXT_PUBLIC_BACKEND_URL` | Cloud Run backend URL |

## VAPI Configuration

The phone number has **no fixed assistant ID**. Instead, VAPI sends an `assistant-request` event to the webhook, and the backend returns a full inline assistant config with:

- **Model:** GPT-4o (OpenAI, via VAPI)
- **Voice:** ElevenLabs Sarah (eleven_turbo_v2_5)
- **System prompt:** Dynamically generated with today's date
- **Tools:** `check_availability`, `create_booking`, `log_call_event` — each pointing to the backend webhook URL

## Tech Stack

| Layer | Technology |
|---|---|
| Voice Agent | VAPI |
| LLM | GPT-4o (OpenAI) |
| Backend | FastAPI (Python 3.11) |
| Database | PostgreSQL via Supabase |
| Frontend | Next.js 14 + React + Tailwind CSS |
| Auth | Google OAuth 2.0 (NextAuth.js) |
| Realtime | Supabase Realtime (WebSocket) |
| Calendar | Google Calendar API |
| Email | Gmail API |
| Backend Deploy | Docker + Google Cloud Run |
| Frontend Deploy | Vercel |
