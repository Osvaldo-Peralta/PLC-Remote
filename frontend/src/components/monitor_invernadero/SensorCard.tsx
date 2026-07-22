// frontend/src/components/invernadero/SensorCard.tsx
interface SensorCardProps {
  label: string;
  value?: number;
  unit: string;
  precision?: number;
}

export default function SensorCard({ label, value, unit, precision = 1 }: SensorCardProps) {
  const hasValue = typeof value === 'number' && !Number.isNaN(value);

  return (
    <div className="relative overflow-hidden rounded-lg border border-stone-200 bg-white py-4 pl-4 pr-5 shadow-sm">
      <span className="absolute left-0 top-0 h-full w-1.5 bg-emerald-600" />
      <p className="text-xs font-medium uppercase tracking-wide text-stone-500">{label}</p>
      <p className="mt-1 font-mono text-3xl tabular-nums text-stone-900">
        {hasValue ? value!.toFixed(precision) : '—'}
        <span className="ml-1 text-base text-stone-400">{unit}</span>
      </p>
    </div>
  );
}