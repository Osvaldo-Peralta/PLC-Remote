// frontend/src/components/monitor_invernadero/ActuatorSwitch.tsx
interface ActuatorSwitchProps {
  label: string;
  value?: boolean;
  pending?: boolean;
  onToggle: (next: boolean) => void;
}

export default function ActuatorSwitch({ label, value, pending, onToggle }: ActuatorSwitchProps) {
  const isOn = value === true;
  const isUnknown = value === undefined;

  return (
    <div className="flex items-center justify-between rounded-lg border border-stone-200 bg-white px-4 py-3 shadow-sm">
      <div>
        <p className="text-sm font-medium text-stone-800">{label}</p>
        <p className="text-xs text-stone-400">
          {isUnknown ? 'Sin datos' : isOn ? 'Encendido' : 'Apagado'}
        </p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={isOn}
        aria-label={label}
        disabled={pending}
        onClick={() => onToggle(!isOn)}
        className={`relative h-7 w-12 shrink-0 rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 ${
          pending ? 'cursor-not-allowed opacity-50' : ''
        } ${isOn ? 'bg-emerald-600' : 'bg-stone-300'}`}
      >
        <span
          className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-transform ${
            isOn ? 'translate-x-5' : 'translate-x-0.2'
          }`}
        />
      </button>
    </div>
  );
}