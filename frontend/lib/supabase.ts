import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

export type BookingStatus = "confirmed" | "cancelled";

export interface Booking {
  id: string;
  host_id: string;
  caller_name: string;
  caller_email: string;
  title: string;
  notes: string | null;
  start_time: string;
  end_time: string;
  calendar_event_id: string | null;
  status: BookingStatus;
  meeting_link: string | null;
  email_sent: boolean;
  delete_at: string | null;
  created_at: string;
}

export interface AvailabilitySlot {
  id: string;
  host_id: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
  is_available: boolean;
}
