// frontend/src/components/monitor_invernadero/UseInvernaderoStatus.ts
import { useState, useEffect, useCallback } from 'react';

const PLC_API_BASE = 'http://localhost:8000';

export interface InvernaderoValues {
  [key: string]: any;
}

/**
 * A diferencia de usePLCState (que hace un fetch por cada elemento), este
 * hook aprovecha el endpoint /status del nuevo backend: una sola llamada
 * trae el snapshot completo (todos los sensores y actuadores), cacheado
 * por el loop de monitoreo del backend. Los comandos se envían aparte,
 * como POST /endpoint/{estado}.
 */
export const useInvernaderoStatus = (pollMs: number = 1000) => {
  const [values, setValues] = useState<InvernaderoValues>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<{ [key: string]: boolean }>({});

  useEffect(() => {
    let cancelled = false;

    const fetchStatus = async () => {
      try {
        const res = await fetch(`${PLC_API_BASE}/status`);
        if (!res.ok) throw new Error('Error al obtener el estado del invernadero');
        const data = await res.json();
        if (!cancelled) {
          setValues(data.values ?? {});
          setError(null);
        }
      } catch (err) {
        console.error('Error al leer /status:', err);
        if (!cancelled) setError('No se pudo conectar al backend del invernadero');
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, pollMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [pollMs]);

  const setActuator = useCallback(async (endpoint: string, id: string, estado: boolean) => {
    setPending(prev => ({ ...prev, [id]: true }));
    try {
      const res = await fetch(`${PLC_API_BASE}${endpoint}/${estado}`, { method: 'POST' });
      if (!res.ok) throw new Error(`Error al enviar comando a ${endpoint}`);
      setValues(prev => ({ ...prev, [id]: estado })); // actualización optimista
      setError(null);
    } catch (err) {
      console.error('Error al enviar comando:', err);
      setError('No se pudo enviar el comando');
    } finally {
      setPending(prev => ({ ...prev, [id]: false }));
    }
  }, []);

  return { values, error, pending, setActuator };
};