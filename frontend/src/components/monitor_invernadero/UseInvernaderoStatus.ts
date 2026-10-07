import { useState, useEffect, useCallback, useRef } from 'react';

const PLC_API_BASE = 'http://localhost:8000';
const RESPONSE_TIMEOUT_MS = 10000;

export interface InvernaderoValues {
  [key: string]: any;
}

export interface ResponseMeasurement {
  commandId: string | null;
  timestamp: string;
  actuator: string;
  action: 'ON' | 'OFF';
  previousState: boolean;
  expectedState: boolean;
  backendCommandTimestamp: string | null;
  backendDetectionTimestamp: string | null;
  backendResponseTimeMs: number | null;
  hmiConfirmationTimestamp: string | null;
  hmiResponseTimeMs: number | null;
  status: 'confirmed' | 'timeout' | 'error';
}

interface PendingMeasurement {
  startedAt: number;
  timestamp: string;
  previousState: boolean;
  expectedState: boolean;
  actuator: string;
  action: 'ON' | 'OFF';
  commandId: string | null;
  backendCommandTimestamp: string | null;
  timeoutId: ReturnType<typeof setTimeout>;
}

interface CommandResponse {
  status: string;
  value?: boolean;
  response_experiment?: {
    command_id: string;
    command_timestamp: string;
  };
}

/**
 * HMI normal: conserva la actualización optimista.
 * Prueba 2: cuando está activa, registra tres etapas:
 * 1) orden en el navegador,
 * 2) detección del cambio en el monitor backend/PLC,
 * 3) confirmación del cambio mediante /status en el HMI.
 */
export const useInvernaderoStatus = (pollMs: number = 1000) => {
  const [values, setValues] = useState<InvernaderoValues>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<{ [key: string]: boolean }>({});
  const [measurementActive, setMeasurementActive] = useState(false);
  const [measurements, setMeasurements] = useState<ResponseMeasurement[]>([]);
  const pendingMeasurements = useRef<{ [key: string]: PendingMeasurement }>({});

  const finishMeasurement = useCallback(async (
    id: string,
    measurement: PendingMeasurement,
    status: ResponseMeasurement['status'],
    responseTimeMs: number | null,
  ) => {
    let backendDetectionTimestamp: string | null = null;
    let backendResponseTimeMs: number | null = null;

    if (status === 'confirmed' && measurement.commandId) {
      // El monitor backend debe haber detectado el cambio antes de que /status
      // lo exponga al HMI. Se da un pequeño margen por asincronía de respuestas.
      for (let attempt = 0; attempt < 5; attempt += 1) {
        try {
          const res = await fetch(
            `${PLC_API_BASE}/experiments/response/event/${measurement.commandId}`,
          );
          if (res.ok) {
            const data = await res.json();
            if (data.status === 'ok' && data.event) {
              backendDetectionTimestamp = data.event.detected_timestamp ?? null;
              backendResponseTimeMs = data.event.backend_response_time_ms ?? null;
              break;
            }
          }
        } catch (err) {
          console.error('Error al obtener la etapa backend de la prueba:', err);
        }

        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }

    setMeasurements(prev => [
      ...prev,
      {
        commandId: measurement.commandId,
        timestamp: measurement.timestamp,
        actuator: measurement.actuator,
        action: measurement.action,
        previousState: measurement.previousState,
        expectedState: measurement.expectedState,
        backendCommandTimestamp: measurement.backendCommandTimestamp,
        backendDetectionTimestamp,
        backendResponseTimeMs,
        hmiConfirmationTimestamp:
          status === 'confirmed' ? new Date().toISOString() : null,
        hmiResponseTimeMs: responseTimeMs,
        status,
      },
    ]);

    setPending(prev => ({ ...prev, [id]: false }));
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${PLC_API_BASE}/status`);
      if (!res.ok) throw new Error('Error al obtener el estado del invernadero');

      const data = await res.json();
      const nextValues = data.values ?? {};

      setValues(nextValues);
      setError(null);

      Object.entries(pendingMeasurements.current).forEach(([id, measurement]) => {
        if (nextValues[id] !== measurement.expectedState) return;

        const responseTimeMs = performance.now() - measurement.startedAt;
        clearTimeout(measurement.timeoutId);
        delete pendingMeasurements.current[id];

        void finishMeasurement(id, measurement, 'confirmed', responseTimeMs);
      });
    } catch (err) {
      console.error('Error al leer /status:', err);
      setError('No se pudo conectar al backend del invernadero');
    }
  }, [finishMeasurement]);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      if (!cancelled) await fetchStatus();
    };

    poll();
    const interval = setInterval(poll, pollMs);

    return () => {
      cancelled = true;
      clearInterval(interval);

      Object.values(pendingMeasurements.current).forEach(m => {
        clearTimeout(m.timeoutId);
      });
      pendingMeasurements.current = {};
    };
  }, [pollMs, fetchStatus]);

  const startMeasurement = useCallback(async () => {
    try {
      const res = await fetch(`${PLC_API_BASE}/experiments/response/start`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('No se pudo iniciar la instrumentación backend');
      setMeasurements([]);
      setMeasurementActive(true);
      setError(null);
    } catch (err) {
      console.error('Error al iniciar Prueba 2:', err);
      setError('No se pudo iniciar la instrumentación de la Prueba 2');
    }
  }, []);

  const stopMeasurement = useCallback(async () => {
    try {
      const res = await fetch(`${PLC_API_BASE}/experiments/response/stop`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('No se pudo detener la instrumentación backend');
      setMeasurementActive(false);
      setError(null);
    } catch (err) {
      console.error('Error al detener Prueba 2:', err);
      setError('No se pudo detener la instrumentación de la Prueba 2');
    }
  }, []);

  const setActuator = useCallback(async (
    endpoint: string,
    id: string,
    estado: boolean,
    actuatorName?: string,
  ) => {
    setPending(prev => ({ ...prev, [id]: true }));

    const previousState = values[id] === true;

    if (measurementActive && id !== 'modoAutomatico') {
      const startedAt = performance.now();
      const timestamp = new Date().toISOString();

      const timeoutId = setTimeout(() => {
        const measurement = pendingMeasurements.current[id];
        if (!measurement) return;

        delete pendingMeasurements.current[id];
        void finishMeasurement(id, measurement, 'timeout', null);
      }, RESPONSE_TIMEOUT_MS);

      pendingMeasurements.current[id] = {
        startedAt,
        timestamp,
        previousState,
        expectedState: estado,
        actuator: actuatorName ?? id,
        action: estado ? 'ON' : 'OFF',
        commandId: null,
        backendCommandTimestamp: null,
        timeoutId,
      };
    }

    try {
      const res = await fetch(`${PLC_API_BASE}${endpoint}/${estado}`, {
        method: 'POST',
      });

      if (!res.ok) throw new Error(`Error al enviar comando a ${endpoint}`);

      const data: CommandResponse = await res.json();
      const measurement = pendingMeasurements.current[id];

      if (measurement && data.response_experiment) {
        measurement.commandId = data.response_experiment.command_id;
        measurement.backendCommandTimestamp = data.response_experiment.command_timestamp;
      }

      // Se conserva el comportamiento optimista original del HMI.
      setValues(prev => ({ ...prev, [id]: estado }));
      setError(null);

      if (!measurementActive || id === 'modoAutomatico') {
        setPending(prev => ({ ...prev, [id]: false }));
      }
    } catch (err) {
      console.error('Error al enviar el comando:', err);
      setError('No se pudo enviar el comando');

      const measurement = pendingMeasurements.current[id];
      if (measurement) {
        clearTimeout(measurement.timeoutId);
        delete pendingMeasurements.current[id];
        void finishMeasurement(id, measurement, 'error', null);
      } else {
        setPending(prev => ({ ...prev, [id]: false }));
      }
    }
  }, [values, measurementActive, finishMeasurement]);

  const clearMeasurements = useCallback(() => {
    setMeasurements([]);
  }, []);

  return {
    values,
    error,
    pending,
    setActuator,
    measurementActive,
    startMeasurement,
    stopMeasurement,
    measurements,
    clearMeasurements,
  };
};
