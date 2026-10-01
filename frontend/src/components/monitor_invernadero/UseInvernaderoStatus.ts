import { useState, useEffect, useCallback, useRef } from 'react';

const PLC_API_BASE = 'http://localhost:8000';
const RESPONSE_TIMEOUT_MS = 10000;

export interface InvernaderoValues {
  [key: string]: any;
}

export interface ResponseMeasurement {
  timestamp: string;
  actuator: string;
  action: 'ON' | 'OFF';
  previousState: boolean;
  expectedState: boolean;
  responseTimeMs: number | null;
  status: 'confirmed' | 'timeout' | 'error';
}

interface PendingMeasurement {
  startedAt: number;
  timestamp: string;
  previousState: boolean;
  expectedState: boolean;
  actuator: string;
  action: 'ON' | 'OFF';
  timeoutId: ReturnType<typeof setTimeout>;
}

/**
 * El HMI conserva la actualización optimista para su funcionamiento normal.
 * La medición experimental solo considera confirmación cuando /status devuelve
 * el estado esperado desde el backend/PLC.
 */
export const useInvernaderoStatus = (pollMs: number = 1000) => {
  const [values, setValues] = useState<InvernaderoValues>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<{ [key: string]: boolean }>({});
  const [measurementActive, setMeasurementActive] = useState(false);
  const [measurements, setMeasurements] = useState<ResponseMeasurement[]>([]);
  const pendingMeasurements = useRef<{ [key: string]: PendingMeasurement }>({});

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

        setMeasurements(prev => [
          ...prev,
          {
            timestamp: measurement.timestamp,
            actuator: measurement.actuator,
            action: measurement.action,
            previousState: measurement.previousState,
            expectedState: measurement.expectedState,
            responseTimeMs,
            status: 'confirmed',
          },
        ]);

        setPending(prev => ({ ...prev, [id]: false }));
      });
    } catch (err) {
      console.error('Error al leer /status:', err);
      setError('No se pudo conectar al backend del invernadero');
    }
  }, []);

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

        setMeasurements(prev => [
          ...prev,
          {
            timestamp: measurement.timestamp,
            actuator: measurement.actuator,
            action: measurement.action,
            previousState: measurement.previousState,
            expectedState: measurement.expectedState,
            responseTimeMs: null,
            status: 'timeout',
          },
        ]);

        setPending(prev => ({ ...prev, [id]: false }));
      }, RESPONSE_TIMEOUT_MS);

      pendingMeasurements.current[id] = {
        startedAt,
        timestamp,
        previousState,
        expectedState: estado,
        actuator: actuatorName ?? id,
        action: estado ? 'ON' : 'OFF',
        timeoutId,
      };
    }

    try {
      const res = await fetch(`${PLC_API_BASE}${endpoint}/${estado}`, {
        method: 'POST',
      });

      if (!res.ok) throw new Error(`Error al enviar comando a ${endpoint}`);

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

        setMeasurements(prev => [
          ...prev,
          {
            timestamp: measurement.timestamp,
            actuator: measurement.actuator,
            action: measurement.action,
            previousState: measurement.previousState,
            expectedState: measurement.expectedState,
            responseTimeMs: null,
            status: 'error',
          },
        ]);
      }

      setPending(prev => ({ ...prev, [id]: false }));
    }
  }, [values, measurementActive]);

  const clearMeasurements = useCallback(() => {
    setMeasurements([]);
  }, []);

  return {
    values,
    error,
    pending,
    setActuator,
    measurementActive,
    setMeasurementActive,
    measurements,
    clearMeasurements,
  };
};
