"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Booking } from "@/lib/supabase";

interface SendLinkButtonProps {
  booking: Booking;
  onSent: (updated: Booking) => void;
}

export function SendLinkButton({ booking, onSent }: SendLinkButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (booking.meeting_link || booking.status !== "confirmed") {
    return null;
  }

  const handleSend = async () => {
    setLoading(true);
    setError(null);
    try {
      const updated = await api.sendMeetingLink(booking.id);
      onSent(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to send invite.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <button
        onClick={handleSend}
        disabled={loading}
        className="text-xs font-bold text-gray-900 transition-colors border-2 border-gray-900 px-2.5 py-1 hover:bg-gray-900 hover:text-white disabled:opacity-60"
      >
        {loading ? "Sending..." : "Send Invite"}
      </button>
      {error && <p className="text-red-600 text-xs font-medium">{error}</p>}
    </div>
  );
}
