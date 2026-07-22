// frontend/src/components/invernadero/InvernaderoDashboard.tsx
import { sensors, actuators, modoAutomatico } from './InvernaderoElements';
import { useInvernaderoStatus } from './UseInvernaderoStatus';
import SensorCard from './SensorCard';
import ActuatorSwitch from './ActuatorSwitch';

export default function InvernaderoDashboard() {
  const { values, error, pending, setActuator } = useInvernaderoStatus();

  const isAuto = values[modoAutomatico.id] === true;

  return (
    <div className="mx-auto max-w-4xl p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-emerald-600">Invernadero</p>
          <h1 className="text-2xl font-semibold text-stone-900">Panel de Monitoreo y Control</h1>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            isAuto ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
          }`}
        >
          {isAuto ? 'Modo automático' : 'Modo manual'}
        </span>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="mb-8">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-stone-500">Sensores</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {sensors.map((sensor) => (
            <SensorCard
              key={sensor.id}
              label={sensor.name}
              value={values[sensor.id]}
              unit={sensor.unit}
            />
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-stone-500">Controles</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <ActuatorSwitch
            label={modoAutomatico.name}
            value={values[modoAutomatico.id]}
            pending={pending[modoAutomatico.id]}
            onToggle={(next) => setActuator(modoAutomatico.endpoint, modoAutomatico.id, next)}
          />
          {actuators.map((actuator) => (
            <ActuatorSwitch
              key={actuator.id}
              label={actuator.name}
              value={values[actuator.id]}
              pending={pending[actuator.id]}
              onToggle={(next) => setActuator(actuator.endpoint, actuator.id, next)}
            />
          ))}
        </div>
      </section>
    </div>
  );
}