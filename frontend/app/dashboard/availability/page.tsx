import { api } from "@/lib/api";
import { AvailabilityGrid } from "@/components/AvailabilityGrid";
import type { AvailabilitySlot } from "@/lib/supabase";

async function getAvailability(): Promise<AvailabilitySlot[]> {
  try {
    return await api.getAvailability();
  } catch {
    return [];
  }
}

export default async function AvailabilityPage() {
  const slots = await getAvailability();

  return (
    <div className="flex flex-col gap-8 max-w-2xl">
      <div>
        <h1 className="text-3xl font-black text-gray-900 tracking-tight">Availability</h1>
        <p className="text-gray-500 text-sm mt-1 font-medium">
          Set the days and hours when callers can book meetings with you.
        </p>
      </div>

      <AvailabilityGrid initial={slots} />
    </div>
  );
}
