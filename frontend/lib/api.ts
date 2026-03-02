import type { Booking, AvailabilitySlot } from "./supabase";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

async function getAuthHeaders(): Promise<HeadersInit> {
  // Fetch the raw NextAuth JWT (signed with NEXTAUTH_SECRET) via a same-origin
  // API route. This is a proper JWT the backend can decode, unlike the Google
  // access token exposed on session.accessToken which is an opaque string.
  try {
    const res = await fetch("/api/auth/session-token");
    if (res.ok) {
      const { token } = await res.json();
      if (token) {
        return {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        };
      }
    }
  } catch {
    // fall through to unauthenticated
  }
  return { "Content-Type": "application/json" };
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BACKEND_URL}${path}`, {
    ...options,
    headers: { ...headers, ...(options.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join("; ")
          : `Request failed: ${res.status}`;
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // Host
  getMe: () => apiFetch<{ id: string; name: string; email: string; picture: string; timezone: string }>("/api/hosts/me"),
  updateMe: (data: { name?: string; picture?: string; timezone?: string }) =>
    apiFetch("/api/hosts/me", { method: "PUT", body: JSON.stringify(data) }),

  // Availability
  getAvailability: () => apiFetch<AvailabilitySlot[]>("/api/availability"),
  updateAvailability: (slots: Omit<AvailabilitySlot, "id" | "host_id">[]) =>
    apiFetch<AvailabilitySlot[]>("/api/availability", {
      method: "PUT",
      body: JSON.stringify({ slots }),
    }),

  // Bookings
  getBookings: (params?: {
    status?: string;
    from?: string;
    to?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.from) qs.set("from", params.from);
    if (params?.to) qs.set("to", params.to);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return apiFetch<Booking[]>(`/api/bookings${query}`);
  },
  getBooking: (id: string) => apiFetch<Booking>(`/api/bookings/${id}`),
  cancelBooking: (id: string) =>
    apiFetch<void>(`/api/bookings/${id}`, { method: "DELETE" }),
  sendMeetingLink: (id: string) =>
    apiFetch<Booking>(`/api/bookings/${id}/send-link`, {
      method: "POST",
      body: "{}",
    }),
};
