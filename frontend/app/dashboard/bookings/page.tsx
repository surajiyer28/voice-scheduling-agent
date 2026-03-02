"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Booking } from "@/lib/supabase";
import clsx from "clsx";

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: "UTC",
  });
}

export default function BookingsPage() {
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [cancelling, setCancelling] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.getBookings(
          statusFilter !== "all" ? { status: statusFilter } : {}
        );
        setBookings(data);
      } catch (err) {
        console.error("Failed to fetch bookings:", err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [statusFilter]);

  const handleCancel = async (id: string) => {
    if (!confirm("Cancel this booking?")) return;
    setCancelling(id);
    try {
      await api.cancelBooking(id);
      setBookings((prev) =>
        prev.map((b) => (b.id === id ? { ...b, status: "cancelled" } : b))
      );
    } catch (err) {
      alert("Failed to cancel booking.");
      console.error(err);
    } finally {
      setCancelling(null);
    }
  };

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-black text-gray-900 tracking-tight">All Bookings</h1>
          <p className="text-gray-500 text-sm mt-1 font-medium">
            Full history of bookings made through your voice agent.
          </p>
        </div>

        <div className="flex gap-1">
          {["all", "confirmed", "cancelled"].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={clsx(
                "px-4 py-1.5 text-sm font-bold uppercase tracking-wide transition-colors border-2",
                statusFilter === s
                  ? "bg-[var(--accent-primary)] text-white border-[var(--accent-primary)]"
                  : "border-gray-300 text-gray-600 hover:bg-[var(--accent-lavender)] hover:border-[var(--accent-primary)]"
              )}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-4 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : bookings.length === 0 ? (
        <div className="bg-[var(--bg-card)] border-2 border-[var(--border-bold)] shadow-[4px_4px_0px_0px_var(--shadow-color)] p-12 text-center">
          <p className="text-gray-500 font-semibold">No bookings found.</p>
        </div>
      ) : (
        <div className="bg-[var(--bg-card)] border-2 border-[var(--border-bold)] shadow-[4px_4px_0px_0px_var(--shadow-color)] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[var(--accent-primary)] text-white">
                  <th className="text-left px-5 py-3 text-xs font-bold uppercase tracking-wider">
                    Caller
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-bold uppercase tracking-wider">
                    Date & Time
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-bold uppercase tracking-wider">
                    Title
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-bold uppercase tracking-wider hidden lg:table-cell">
                    Notes
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-bold uppercase tracking-wider">
                    Status
                  </th>
                  <th className="text-left px-5 py-3 text-xs font-bold uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {bookings.map((b) => (
                  <tr
                    key={b.id}
                    className="border-b border-gray-200 last:border-0 hover:bg-[var(--accent-lavender)]/30 transition-colors"
                  >
                    <td className="px-5 py-3.5 font-bold text-gray-900">
                      {b.caller_name}
                    </td>
                    <td className="px-5 py-3.5 text-gray-600 whitespace-nowrap font-medium">
                      {formatDateTime(b.start_time)}
                    </td>
                    <td className="px-5 py-3.5 text-gray-700 font-medium">{b.title}</td>
                    <td className="px-5 py-3.5 text-gray-500 hidden lg:table-cell max-w-xs truncate">
                      {b.notes ?? "—"}
                    </td>
                    <td className="px-5 py-3.5">
                      <span
                        className={clsx(
                          "text-xs font-bold px-2.5 py-1 uppercase tracking-wide",
                          b.status === "confirmed"
                            ? "bg-[var(--accent-mint)] text-[var(--accent-mint-text)] border border-emerald-300"
                            : "bg-[var(--accent-peach)] text-[var(--accent-peach-text)] border border-orange-300"
                        )}
                      >
                        {b.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      {b.status === "confirmed" && (
                        <button
                          onClick={() => handleCancel(b.id)}
                          disabled={cancelling === b.id}
                          className="text-xs font-bold text-red-600 disabled:opacity-50 transition-colors border-2 border-red-600 px-2.5 py-1 hover:bg-red-600 hover:text-white"
                        >
                          {cancelling === b.id ? "..." : "Cancel"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
