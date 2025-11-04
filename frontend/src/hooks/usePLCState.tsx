// src/hooks/usePLCState.tsx
import { useState, useEffect, useRef } from 'react';

const PLC_API_BASE = 'http://localhost:8000';

export interface PLCState {
  [key: string]: any;
}

export const usePLCState = (elements: { id: string; endpoint: string }[]) => {
  const [state, setState] = useState<PLCState>({});
  const [loading, setLoading] = useState<{ [key: string]: boolean }>({});
  const [error, setError] = useState<string | null>(null);

  // Usamos un ref para evitar que el intervalo se reinicie si cambia setError
  const elementsRef = useRef(elements);
  elementsRef.current = elements;

  // Cargar estado inicial de cada elemento
  useEffect(() => {
    const fetchAll = async () => {
      const currentElements = elementsRef.current;
      for (const element of currentElements) {
        if (element.endpoint) {
          await fetchValue(element.id, element.endpoint);
        }
      }
    };

    fetchAll();

    // Actualizar cada 1 segundos
    const interval = setInterval(() => {
      // Evitar ejecutar si hay un error general activo (opcional)
      // if (error) return; // Descomenta si quieres pausar refresco en error general
      fetchAll().catch(err => console.error("Error en refresco automático:", err)); // Atrapamos errores del refresco automático
    }, 1000);

    return () => clearInterval(interval);
  }, []); // <-- Ahora depende de [] vacío, no de elements

  const fetchValue = async (id: string, endpoint: string) => {
    setLoading(prev => ({ ...prev, [id]: true }));
    try {
      const res = await fetch(`${PLC_API_BASE}${endpoint}`);
      if (!res.ok) throw new Error(`Error al leer ${id}`);
      const data = await res.json();
      setState(prev => ({ ...prev, [id]: data.value ?? data }));
      setError(null); // Limpiar error si la operación fue exitosa
    } catch (err) {
      console.error(`Error al cargar ${id}:`, err);
      // Opcional: solo actualizar error si no es un error repetido
      // if (!error) {
        setError('No se pudo conectar al PLC');
      // }
    } finally {
      setLoading(prev => ({ ...prev, [id]: false }));
    }
  };

  const sendCommand = async (endpoint: string) => {
    try {
      const res = await fetch(`${PLC_API_BASE}${endpoint}`, { method: 'POST' });
      if (!res.ok) throw new Error(`Error al enviar comando a ${endpoint}`);
      setError(null); // Limpiar error si la operación fue exitosa
    } catch (err) {
      console.error(`Error al enviar comando:`, err);
      setError('No se pudo enviar el comando');
    }
  };

  return { state, loading, error, sendCommand };
};