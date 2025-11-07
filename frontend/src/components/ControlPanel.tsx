//src/components/ControlPanel.tsx
import { useState, useEffect } from "react";

const PLC_API_BASE = 'http://localhost:8000';

export default function ControlPanel() {
    const [isRunning, setIsRunning] = useState<boolean | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Cargar el estado inicial del PLC
    useEffect(() => {
        const fetchStatus = async () => {
            try {
                setLoading(true);
                const res = await fetch(`${PLC_API_BASE}/status`);
                if (!res.ok) throw new Error('Error al obtener el estado del PLC');
                const data = await res.json();
                setIsRunning(data.value);
            } catch (err) {
                console.error('Error al cargar el estado:', err);
                setError('No se pudo conectar al PLC');
            } finally {
                setLoading(false);
            }
        };

        fetchStatus();

        // Actualizar cada 2 segundos
        const interval = setInterval(fetchStatus, 2000);
        return () => clearInterval(interval);
    }, []);

    const handleStart = async () => {
        setError(null);
        setLoading(true);
        try {
            const res = await fetch(`${PLC_API_BASE}/start`, { method: 'POST' });
            if (!res.ok) throw new Error('Error al iniciar');
            setIsRunning(true);
        } catch (err) {
            console.error('Error al iniciar', err);
            setError('No se pudo iniciar la operación');
        } finally {
            setLoading(false);
        }
    };

    const handleStop = async () => {
        setError(null);
        setLoading(true);
        try {
            const res = await fetch(`${PLC_API_BASE}/stop`, { method: 'POST' });
            if (!res.ok) throw new Error('Error al detener');
            setIsRunning(false);
        } catch (err) {
            console.error('Error al detener', err);
            setError('No se pudo detener la operación');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-md mx-auto p-6 bg-gray-50 rounded-xl shadow-lg">
            <h2 className="text-2xl font-bold text-gray-800 mb-4">Control Panel Semaforo</h2>

            {error && (
                <div className="mb-4 p-2 bg-red-100 text-red-700 rounded">
                    {error}
                </div>
            )}

            <div className="mb-6">
                <div className="flex items-center justify-between">
                    <span className="text-gray-700">Estado Actual:</span>
                    <div className="flex items-center">
                        <div
                            className={`w-6 h-6 rounded-full mr-2 ${
                                isRunning === null ? 'bg-gray-400' : isRunning ? 'bg-red-500' : 'bg-gray-300'
                            }`}
                            title={isRunning === null ? 'Desconocido' : isRunning ? 'ON' : 'OFF'}
                        ></div>
                        <span className="font-bold text-gray-300">
                            {isRunning === null ? 'Desconocido' : isRunning ? 'ON' : 'OFF'}
                        </span>
                    </div>
                </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-4">
                <button
                    onClick={handleStart}
                    disabled={isRunning || loading}
                    className={`px-6 py-3 rounded-lg font-medium ${
                        isRunning || loading
                            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                            : 'bg-green-500 hover:bg-green-600 text-white'
                    }`}
                >
                    {loading ? '...' : 'INICIO'}
                </button>
                <button
                    onClick={handleStop}
                    disabled={!isRunning || loading}
                    className={`px-6 py-3 rounded-lg font-medium ${
                        !isRunning || loading
                            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                            : 'bg-red-500 hover:bg-red-600 text-white'
                    }`}
                >
                    {loading ? '...' : 'STOP'}
                </button>
            </div>
        </div>
    );
}