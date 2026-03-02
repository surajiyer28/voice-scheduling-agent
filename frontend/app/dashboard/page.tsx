"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { MeetingCard } from "@/components/MeetingCard";
import type { Booking } from "@/lib/supabase";

export default function DashboardPage() {
  const { data: session } = useSession();
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [hostId, setHostId] = useState<string | null>(null);
  const [hostTimezone, setHostTimezone] = useState<string>("America/New_York");

  const fetchBookings = useCallback(async () => {
    try {
      const now = new Date().toISOString();
      const data = await api.getBookings({ status: "confirmed", from: now });
      setBookings(data);
    } catch (err) {
      console.error("Failed to fetch bookings:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const loadHost = async () => {
      try {
        const host = await api.getMe();
        setHostId(host.id);
        setHostTimezone(host.timezone);
      } catch {
        // silently fail
      }
    };
    loadHost();
    fetchBookings();
  }, [fetchBookings]);

  useEffect(() => {
    if (!hostId) return;

    const channel = supabase
      .channel("bookings-realtime")
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "bookings",
          filter: `host_id=eq.${hostId}`,
        },
        (payload) => {
          const changed = payload.new as Booking | null;
          const old = payload.old as Booking | null;

          if (payload.eventType === "INSERT" && changed) {
            setBookings((prev) => {
              const exists = prev.some((b) => b.id === changed.id);
              if (exists) return prev;
              return [...prev, changed].sort(
                (a, b) =>
                  new Date(a.start_time).getTime() -
                  new Date(b.start_time).getTime()
              );
            });
          } else if (payload.eventType === "UPDATE" && changed) {
            setBookings((prev) =>
              prev.map((b) => (b.id === changed.id ? changed : b))
            );
          } else if (payload.eventType === "DELETE" && old) {
            setBookings((prev) => prev.filter((b) => b.id !== old.id));
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [hostId]);

  const handleBookingUpdate = (updated: Booking) => {
    setBookings((prev) =>
      prev.map((b) => (b.id === updated.id ? updated : b))
    );
  };

  const handleCancel = async (bookingId: string) => {
    await api.cancelBooking(bookingId);
    setBookings((prev) => prev.filter((b) => b.id !== bookingId));
  };

  const upcomingBookings = bookings.filter(
    (b) =>
      b.status === "confirmed" && new Date(b.start_time) >= new Date()
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-4 border-gray-900 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-black text-gray-900 tracking-tight">
          Upcoming Meetings
        </h1>
        <p className="text-gray-500 text-sm mt-1 font-medium">
          {upcomingBookings.length === 0
            ? "No upcoming meetings"
            : `${upcomingBookings.length} confirmed meeting${upcomingBookings.length === 1 ? "" : "s"}`}
        </p>
      </div>

      {upcomingBookings.length === 0 ? (
        <div className="bg-white border-2 border-gray-900 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] p-14 text-center">
          <div className="w-16 h-16 bg-gray-100 flex items-center justify-center mx-auto mb-5">
            <svg
              className="w-8 h-8 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>
          <p className="text-gray-900 font-bold text-lg">No upcoming meetings</p>
          <p className="text-gray-500 text-sm mt-1">
            New bookings will appear here in real-time when callers book through the voice agent.
          </p>
        </div>
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {upcomingBookings.map((booking) => (
            <MeetingCard
              key={booking.id}
              booking={booking}
              hostTimezone={hostTimezone}
              onUpdate={handleBookingUpdate}
              onCancel={handleCancel}
            />
          ))}
        </div>
      )}
    </div>
  );
}
