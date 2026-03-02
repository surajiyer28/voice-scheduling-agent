"use client";

import { useState, useEffect } from "react";
import { api } from "@/lib/api";
import type { AvailabilitySlot } from "@/lib/supabase";

const DAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

const DEFAULT_SLOTS: Omit<AvailabilitySlot, "id" | "host_id">[] = DAY_NAMES.map(
  (_, i) => ({
    day_of_week: i,
    start_time: "09:00:00",
    end_time: "17:00:00",
    is_available: i < 5,
  })
);

function toTimeInput(t: string): string {
  return t.slice(0, 5);
}

function toTimeBackend(t: string): string {
  return t.length === 5 ? `${t}:00` : t;
}

const US_TIMEZONES = [
  { value: "America/New_York", label: "Eastern (ET)" },
  { value: "America/Chicago", label: "Central (CT)" },
  { value: "America/Denver", label: "Mountain (MT)" },
  { value: "America/Los_Angeles", label: "Pacific (PT)" },
  { value: "America/Anchorage", label: "Alaska (AKT)" },
  { value: "America/Honolulu", label: "Hawaii (HT)" },
];

interface AvailabilityGridProps {
  initial: AvailabilitySlot[];
}

export function AvailabilityGrid({ initial }: AvailabilityGridProps) {
  const [slots, setSlots] = useState<Omit<AvailabilitySlot, "id" | "host_id">[]>(
    () => {
      if (initial.length === 7) {
        return initial
          .slice()
          .sort((a, b) => a.day_of_week - b.day_of_week)
          .map((s) => ({
            day_of_week: s.day_of_week,
            start_time: s.start_time,
            end_time: s.end_time,
            is_available: s.is_available,
          }));
      }
      return DEFAULT_SLOTS;
    }
  );

  const [timezone, setTimezone] = useState("America/New_York");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getMe().then((host) => setTimezone(host.timezone)).catch(() => {});
  }, []);

  const update = (
    index: number,
    field: keyof Omit<AvailabilitySlot, "id" | "host_id">,
    value: string | boolean | number
  ) => {
    setSlots((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = slots.map((s) => ({
        ...s,
        start_time: toTimeBackend(s.start_time),
        end_time: toTimeBackend(s.end_time),
      }));
      await api.updateAvailability(payload);
      try {
        await api.updateMe({ timezone });
      } catch {
        // timezone save failed silently
      }
      setSaved(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center gap-3">
        <label htmlFor="tz-select" className="text-sm font-bold text-gray-900 uppercase tracking-wide">
          Timezone
        </label>
        <select
          id="tz-select"
          value={timezone}
          onChange={(e) => {
            setTimezone(e.target.value);
            setSaved(false);
          }}
          className="border-2 border-[var(--border-bold)] px-3 py-1.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] focus:ring-offset-1 bg-[var(--bg-card)]"
        >
          {US_TIMEZONES.map((tz) => (
            <option key={tz.value} value={tz.value}>
              {tz.label}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-[var(--bg-card)] border-2 border-[var(--border-bold)] shadow-[4px_4px_0px_0px_var(--shadow-color)] overflow-hidden">
        <div className="grid grid-cols-4 gap-0 bg-[var(--accent-primary)] px-5 py-3 text-xs font-bold text-white uppercase tracking-wider">
          <span>Day</span>
          <span>Available</span>
          <span>Start</span>
          <span>End</span>
        </div>

        {slots.map((slot, i) => (
          <div
            key={slot.day_of_week}
            className="grid grid-cols-4 gap-0 items-center px-5 py-3.5 border-b border-gray-200 last:border-0"
          >
            <span className="text-sm font-bold text-gray-900">
              {DAY_NAMES[slot.day_of_week]}
            </span>

            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={slot.is_available}
                onChange={(e) => update(i, "is_available", e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-10 h-6 bg-gray-300 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-[var(--accent-primary)] peer-focus:ring-offset-1 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--accent-primary)]" />
            </label>

            <input
              type="time"
              value={toTimeInput(slot.start_time)}
              disabled={!slot.is_available}
              onChange={(e) => update(i, "start_time", e.target.value)}
              className="border-2 border-gray-300 px-2 py-1.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] focus:border-[var(--accent-primary)] w-36 disabled:opacity-30 disabled:bg-gray-50"
            />

            <input
              type="time"
              value={toTimeInput(slot.end_time)}
              disabled={!slot.is_available}
              onChange={(e) => update(i, "end_time", e.target.value)}
              className="border-2 border-gray-300 px-2 py-1.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] focus:border-[var(--accent-primary)] w-36 disabled:opacity-30 disabled:bg-gray-50"
            />
          </div>
        ))}
      </div>

      {error && (
        <p className="text-red-600 text-sm font-semibold">{error}</p>
      )}

      <div className="flex items-center gap-4">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2.5 bg-[var(--accent-primary)] text-white text-sm font-bold uppercase tracking-wide hover:bg-[var(--accent-primary-hover)] disabled:opacity-60 transition-colors shadow-[3px_3px_0px_0px_var(--shadow-color)] active:shadow-none active:translate-x-[3px] active:translate-y-[3px]"
        >
          {saving ? "Saving..." : "Save Availability"}
        </button>
        {saved && (
          <span className="text-emerald-700 text-sm font-bold">Saved</span>
        )}
      </div>
    </div>
  );
}
