import { AvailabilityGrid } from "@/components/AvailabilityGrid";

export default function AvailabilityPage() {
  return (
    <div className="flex flex-col gap-8 max-w-2xl">
      <div>
        <h1 className="text-3xl font-black text-gray-900 tracking-tight">Availability</h1>
        <p className="text-gray-500 text-sm mt-1 font-medium">
          Set the days and hours when callers can book meetings with you.
        </p>
      </div>

      <AvailabilityGrid />
    </div>
  );
}
