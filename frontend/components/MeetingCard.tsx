"use client";

import { useState } from "react";
import clsx from "clsx";
import { SendLinkButton } from "./SendLinkButton";
import type { Booking } from "@/lib/supabase";

interface MeetingCardProps {
  booking: Booking;
  hostTimezone: string;
  onUpdate: (updated: Booking) => void;
  onCancel: (id: string) => void;
}

function formatDateTime(isoString: string, timeZone: string): string {
  return new Date(isoString).toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone,
    timeZoneName: "short",
  });
}

export function MeetingCard({ booking, hostTimezone, onUpdate, onCancel }: MeetingCardProps) {
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await onCancel(booking.id);
    } finally {
      setCancelling(false);
      setConfirming(false);
    }
  };

  return (
    <div className="bg-white border-2 border-gray-900 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] p-5 flex flex-col gap-3 hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:translate-x-[2px] hover:translate-y-[2px] transition-all">
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <h3 className="font-bold text-gray-900 text-base leading-tight">
            {booking.title}
          </h3>
          <p className="text-sm text-gray-500 font-medium">{booking.caller_name}</p>
        </div>
        <span
          className={clsx(
            "text-xs font-bold px-2.5 py-1 shrink-0 uppercase tracking-wide",
            booking.status === "confirmed"
              ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
              : "bg-red-100 text-red-700 border border-red-300"
          )}
        >
          {booking.status}
        </span>
      </div>

      <div className="flex items-center gap-2 text-sm text-gray-600 font-medium">
        <svg
          className="w-4 h-4 text-gray-400 shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        {formatDateTime(booking.start_time, hostTimezone)}
        <span className="text-gray-400 text-xs font-semibold">(1 hr)</span>
      </div>

      {booking.notes && (
        <p className="text-sm text-gray-500 line-clamp-2">
          {booking.notes.length > 100
            ? booking.notes.slice(0, 100) + "..."
            : booking.notes}
        </p>
      )}

      {booking.meeting_link && (
        <p className="text-xs text-emerald-700 font-semibold flex items-center gap-1">
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          Meeting link sent
        </p>
      )}

      {booking.status === "confirmed" && (
        <div className="mt-1 flex items-center gap-2 pt-2 border-t border-gray-200">
          <SendLinkButton booking={booking} onSent={onUpdate} />
          {confirming ? (
            <span className="text-xs text-gray-600 flex items-center gap-2 font-medium">
              Cancel meeting?
              <button
                onClick={handleCancel}
                disabled={cancelling}
                className="font-bold text-red-600 hover:text-red-800 disabled:opacity-60"
              >
                {cancelling ? "..." : "Yes"}
              </button>
              <button
                onClick={() => setConfirming(false)}
                className="font-bold text-gray-500 hover:text-gray-700"
              >
                No
              </button>
            </span>
          ) : (
            <button
              onClick={() => setConfirming(true)}
              className="text-xs font-bold text-red-600 hover:text-white transition-colors border-2 border-red-600 px-2.5 py-1 hover:bg-red-600"
            >
              Cancel
            </button>
          )}
        </div>
      )}
    </div>
  );
}
