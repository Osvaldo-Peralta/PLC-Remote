import { useMemo } from 'react';
import type { ResponseMeasurement } from './UseInvernaderoStatus';

interface ResponseExperimentPanelProps {
  active: boolean;
  measurements: ResponseMeasurement[];
  onStart: () => void;
  onStop: () => void;
  onClear: () => void;
}

function csv(value: string | number | boolean | null) {
  const text = value === null ? '' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function seconds(ms: number | null) {
  return ms === null ? '—' : `${(ms / 1000).toFixed(3)} s`;
}

export default function ResponseExperimentPanel({
  active,
  measurements,
  onStart,
  onStop,
  onClear,
}: ResponseExperimentPanelProps) {
  const confirmed = measurements.filter(
    m => m.status === 'confirmed' && m.hmiResponseTimeMs !== null,
  );

  const summary = useMemo(() => {
    if (!confirmed.length) {
      return { count: 0, average: null, min: null, max: null };
    }

    const times = confirmed.map(m => m.hmiResponseTimeMs as number);
    return {
      count: times.length,
      average: times.reduce((sum, value) => sum + value, 0) / times.length,
      min: Math.min(...times),
      max: Math.max(...times),
    };
  }, [confirmed]);

  const exportCsv = () => {
    if (!measurements.length) return;

    const header = [
      'command_id',
      'command_timestamp_hmi',
      'actuator',
      'action',
      'previous_state',
      'expected_state',
      'backend_command_timestamp',
      'backend_detection_timestamp',
      'backend_response_time_ms',
      'backend_response_time_s',
      'hmi_confirmation_timestamp',
      'hmi_response_time_ms',
      'hmi_response_time_s',
      'status',
    ];

    const rows = measurements.map(m => [
      m.commandId ?? '',
      m.timestamp,
      m.actuator,
      m.action,
      m.previousState,
      m.expectedState,
      m.backendCommandTimestamp ?? '',
      m.backendDetectionTimestamp ?? '',
      m.backendResponseTimeMs ?? '',
      m.backendResponseTimeMs === null ? '' : (m.backendResponseTimeMs / 1000).toFixed(3),
      m.hmiConfirmationTimestamp ?? '',
      m.hmiResponseTimeMs ?? '',
      m.hmiResponseTimeMs === null ? '' : (m.hmiResponseTimeMs / 1000).toFixed(3),
      m.status,
    ]);

    const content = [
      header.map(csv).join(','),
      ...rows.map(row => row.map(csv).join(',')),
    ].join('\n');

    const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);

    link.href = url;
    link.download = `prueba_respuesta_3_etapas_${stamp}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="mt-8 rounded-lg border border-stone-200 bg-white p-5 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">
            Experimento 2
          </p>
          <h2 className="mt-1 text-lg font-semibold text-stone-900">
            Tiempo de respuesta HMI
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-stone-500">
            Registra la orden del usuario, la detección del cambio en el backend/PLC y la confirmación posterior del HMI.
          </p>
        </div>

        <button
          type="button"
          onClick={active ? onStop : onStart}
          className={`rounded-md px-4 py-2 text-sm font-medium ${
            active
              ? 'bg-amber-100 text-amber-800 hover:bg-amber-200'
              : 'bg-emerald-100 text-emerald-800 hover:bg-emerald-200'
          }`}
        >
          {active ? 'Detener medición' : 'Iniciar medición'}
        </button>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Metric label="Mediciones" value={String(summary.count)} />
        <Metric label="HMI promedio" value={seconds(summary.average)} />
        <Metric label="HMI mínimo" value={seconds(summary.min)} />
        <Metric label="HMI máximo" value={seconds(summary.max)} />
      </div>

      {active && (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Medición activa. Realiza las conmutaciones ON/OFF desde los actuadores del HMI.
        </div>
      )}

      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[1100px] text-left text-sm">
          <thead className="border-b border-stone-200 text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th className="px-3 py-2">Fecha/hora</th>
              <th className="px-3 py-2">Actuador</th>
              <th className="px-3 py-2">Acción</th>
              <th className="px-3 py-2">Backend</th>
              <th className="px-3 py-2">HMI</th>
              <th className="px-3 py-2">Estado</th>
            </tr>
          </thead>
          <tbody>
            {!measurements.length ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-stone-400">
                  No hay mediciones registradas.
                </td>
              </tr>
            ) : (
              measurements.map((m, index) => (
                <tr key={`${m.timestamp}-${index}`} className="border-b border-stone-100">
                  <td className="px-3 py-2 font-mono text-xs">
                    {new Date(m.timestamp).toLocaleTimeString()}
                  </td>
                  <td className="px-3 py-2">{m.actuator}</td>
                  <td className="px-3 py-2">{m.action}</td>
                  <td className="px-3 py-2 font-mono">{seconds(m.backendResponseTimeMs)}</td>
                  <td className="px-3 py-2 font-mono">{seconds(m.hmiResponseTimeMs)}</td>
                  <td className="px-3 py-2">{statusLabel(m.status)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={exportCsv}
          disabled={!measurements.length}
          className="rounded-md border border-stone-300 px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-40"
        >
          Descargar CSV
        </button>

        <button
          type="button"
          onClick={onClear}
          disabled={!measurements.length || active}
          className="rounded-md border border-stone-300 px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-40"
        >
          Limpiar mediciones
        </button>
      </div>

      <p className="mt-3 text-xs text-stone-400">
        El tiempo HMI se mide desde la orden en el navegador hasta la confirmación mediante /status. El tiempo backend se mide desde el inicio del comando hasta su detección en el snapshot leído del PLC.
      </p>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-stone-50 px-3 py-3">
      <p className="text-xs text-stone-500">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold text-stone-900">{value}</p>
    </div>
  );
}

function statusLabel(status: ResponseMeasurement['status']) {
  return {
    confirmed: 'Confirmado',
    timeout: 'Timeout',
    error: 'Error',
  }[status];
}
