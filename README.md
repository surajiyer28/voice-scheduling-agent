# Voice Scheduling Agent

A production-grade voice scheduling system where callers dial a Twilio phone number, speak with a VAPI AI assistant powered by Gemini 2.0 Flash, and book 1-hour meetings automatically — complete with Google Calendar events and SMS confirmations. Company hosts manage their availability and upcoming meetings through a real-time Next.js dashboard.

## Live Demo

- **Frontend (Vercel):** `https://your-vercel-app.vercel.app`
- **Backend (Cloud Run):** `https://your-cloud-run-url.run.app`
- **Call to test:** `+1 (xxx) xxx-xxxx` ← replace with your Twilio number

## How to Test the Voice Agent

1. Call the Twilio number above.
2. The AI assistant will greet you and ask for your name.
3. Provide a name, preferred date/time, optional meeting title, and notes.
4. The agent checks availability, confirms details, then books the meeting.
5. You will receive an SMS confirmation with meeting details.
6. The host dashboard updates in real-time showing your new booking.

## Architecture

```
Caller → Twilio → VAPI → Gemini 2.0 Flash
                              ↓
                       FastAPI (Cloud Run)
                       ├── Supabase PostgreSQL
                       ├── Google Calendar API
                       └── Twilio SMS

Host → Next.js (Vercel) → FastAPI → Supabase
             ↑
       Supabase Realtime (WebSocket)
```

## Calendar Integration

Each host authenticates via Google OAuth during sign-in. The backend stores the host's OAuth access and refresh tokens, refreshing them automatically before every Calendar API call. When a booking is created:

1. `calendar_service.check_free_busy` queries the host's Google Calendar for conflicts in the requested 1-hour window.
2. `calendar_service.create_event` creates the event on the host's primary calendar with the caller's name and notes in the description.
3. When a booking is cancelled, the calendar event is deleted automatically.
4. 48 hours after meeting end, the calendar event and booking record are both deleted by the background cleanup task.

## Local Development

### Prerequisites

- Docker and Docker Compose
- Node.js 20+
- A `.env` file in `backend/` (copy from `backend/.env.example` and fill in values)

### Start backend + local Postgres

```bash
docker compose up --build
```

The backend will be available at `http://localhost:8080`.
Visit `http://localhost:8080/health` to confirm it is running.

### Start frontend

```bash
cd frontend
cp .env.example .env.local
# Fill in values in .env.local
npm install
npm run dev
```

Frontend will be available at `http://localhost:3000`.

### Database migrations (Alembic)

```bash
cd backend
alembic upgrade head
```

> For Supabase, run the SQL in the spec's section 4 directly in the Supabase SQL editor instead of using Alembic migrations.

## Deployment

### Backend — Google Cloud Run

```bash
cd backend
gcloud builds submit --tag gcr.io/<PROJECT_ID>/voice-scheduler-backend
gcloud run deploy voice-scheduler-backend \
  --image gcr.io/<PROJECT_ID>/voice-scheduler-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 10 \
  --port 8080 \
  --set-env-vars DATABASE_URL=...,TWILIO_ACCOUNT_SID=...
```

### Frontend — Vercel

```bash
cd frontend
vercel --prod
```

Set all frontend environment variables in the Vercel dashboard under Project Settings → Environment Variables.

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg format) |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (server-side only) |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | Your Twilio phone number (E.164 format) |
| `VAPI_API_KEY` | VAPI API key |
| `VAPI_WEBHOOK_SECRET` | Secret to validate VAPI webhook calls |
| `GOOGLE_CLIENT_ID` | Google OAuth 2.0 Client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 2.0 Client Secret |
| `GEMINI_API_KEY` | Google AI Studio API key for Gemini |
| `FRONTEND_URL` | Frontend URL for CORS (e.g. https://your-app.vercel.app) |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|---|---|
| `NEXTAUTH_URL` | Base URL of the frontend app |
| `NEXTAUTH_SECRET` | Random secret for NextAuth (run: `openssl rand -base64 32`) |
| `GOOGLE_CLIENT_ID` | Same Google OAuth Client ID as backend |
| `GOOGLE_CLIENT_SECRET` | Same Google OAuth Client Secret as backend |
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon (public) key |
| `NEXT_PUBLIC_BACKEND_URL` | Cloud Run backend URL |

## Supabase Setup

Run the SQL from the project specification's Section 4 in the Supabase SQL Editor to create all tables. Then:

1. Go to **Database → Replication → Supabase Realtime** and enable the `bookings` table.
2. Go to **Database → Extensions** and enable `pg_cron`.
3. Run the cron job SQL to auto-delete expired bookings.

## VAPI Configuration

After deploying the backend, configure your VAPI assistant with:

- **Model:** Custom LLM pointing to Gemini 2.0 Flash via Google AI Studio
- **First Message:** "Hello! Thank you for calling. I'm your scheduling assistant..."
- **System Prompt:** See specification Section 6.2
- **Tools:** Register `check_availability`, `create_booking`, and `log_call_event` with server URL `https://<YOUR_CLOUD_RUN_URL>/webhook/vapi`

## Tech Stack

| Layer | Technology |
|---|---|
| Voice Agent | VAPI (free tier) |
| LLM | Gemini 2.0 Flash |
| Phone/SMS | Twilio |
| Backend | FastAPI (Python 3.11) |
| Database | PostgreSQL via Supabase |
| Frontend | Next.js 14 + React + Tailwind CSS |
| Auth | Google OAuth 2.0 (NextAuth.js) |
| Realtime | Supabase Realtime |
| Calendar | Google Calendar API |
| Backend Deploy | Docker + Google Cloud Run |
| Frontend Deploy | Vercel |
