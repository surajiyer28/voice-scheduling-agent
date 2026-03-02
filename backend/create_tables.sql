                                                                                                                              -- Run this in the Supabase SQL editor OR against your local Postgres.
                                                                                                                              -- For local dev: docker exec -i voice-scheduling-agent-db-1 psql -U postgres -d voicescheduler < create_tables.sql

                                                                                                                              CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

                                                                                                                              CREATE TABLE IF NOT EXISTS hosts (
                                                                                                                                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                                                                                                                google_id TEXT UNIQUE NOT NULL,
                                                                                                                                email TEXT UNIQUE NOT NULL,
                                                                                                                                name TEXT NOT NULL,
                                                                                                                                picture TEXT,
                                                                                                                                google_access_token TEXT,
                                                                                                                                google_refresh_token TEXT,
                                                                                                                                google_token_expiry TIMESTAMPTZ,
                                                                                                                                calendar_id TEXT DEFAULT 'primary',
                                                                                                                                is_active BOOLEAN DEFAULT TRUE,
                                                                                                                                created_at TIMESTAMPTZ DEFAULT NOW()
                                                                                                                              );

                                                                                                                              CREATE TABLE IF NOT EXISTS availability (
                                                                                                                                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                                                                                                                host_id UUID REFERENCES hosts(id) ON DELETE CASCADE,
                                                                                                                                day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
                                                                                                                                start_time TIME NOT NULL DEFAULT '09:00:00',
                                                                                                                                end_time TIME NOT NULL DEFAULT '17:00:00',
                                                                                                                                is_available BOOLEAN DEFAULT TRUE,
                                                                                                                                UNIQUE(host_id, day_of_week)
                                                                                                                              );

                                                                                                                              CREATE TABLE IF NOT EXISTS bookings (
                                                                                                                                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                                                                                                                host_id UUID REFERENCES hosts(id) ON DELETE SET NULL,
                                                                                                                                caller_name TEXT NOT NULL,
                                                                                                                                caller_phone TEXT NOT NULL,
                                                                                                                                title TEXT DEFAULT 'Meeting',
                                                                                                                                notes TEXT,
                                                                                                                                start_time TIMESTAMPTZ NOT NULL,
                                                                                                                                end_time TIMESTAMPTZ NOT NULL,
                                                                                                                                calendar_event_id TEXT,
                                                                                                                                status TEXT DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled')),
                                                                                                                                meeting_link TEXT,
                                                                                                                                meeting_link_sent BOOLEAN DEFAULT FALSE,
                                                                                                                                sms_sent BOOLEAN DEFAULT FALSE,
                                                                                                                                delete_at TIMESTAMPTZ,
                                                                                                                                created_at TIMESTAMPTZ DEFAULT NOW()
                                                                                                                              );

                                                                                                                              CREATE TABLE IF NOT EXISTS event_logs (
                                                                                                                                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                                                                                                                booking_id UUID REFERENCES bookings(id) ON DELETE SET NULL,
                                                                                                                                event_type TEXT NOT NULL,
                                                                                                                                details JSONB,
                                                                                                                                created_at TIMESTAMPTZ DEFAULT NOW()
                                                                                                                              );

                                                                                                                              ALTER TABLE bookings REPLICA IDENTITY FULL;
