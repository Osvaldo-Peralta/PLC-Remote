import { plcElements } from "../../config/PLCElements";
import { usePLCState } from "../../hooks/usePLCState";

interface SemaforoState {
    foco_rojo: boolean;
    foco_amarillo: boolean;
    foco_verde: boolean;
    current_time: number; // Si es necesario convertir en backend el tipo Time en segundos 
}

export default function SemaforoPanel() {
    // Se filtraran solo los elementos que se necesiten para el semaforo
    const semaforoElements = plcElements.filter(plc => ['foco_rojo', 'foco_amarillo', 'foco_verde', 'current_time'].includes(plc.id));
    const { state, loading, error } = usePLCState(semaforoElements.map(plc => ({ id: plc.id, endpoint: plc.endpoint! })));

    const semaforoState: SemaforoState = {
        foco_rojo: state['foco_rojo'] || false,
        foco_amarillo: state['foco_amarillo'] || false,
        foco_verde: state['foco_verde'] || false,
        current_time: state['current_time'] || 0, // Se asume que desde el backend el tiempo ya viene convertido en segundos.
    };

// Convertir el tiempo se segundos a milisegundos (MM:SS)
    const formatTime = (seconds: number)  => {
        const mins = Math.floor(seconds / 1000);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}s.${secs.toString().padStart(3, '0')}ms`
    };

    return (
        <div className="p-6 bg-gray-100 rounded-xl shadow-lg">
            <h2 className="text-2xl font-bold text-gray-800 mb-6 text-center">
                    Semaforo
            </h2>
        {error && (
            <div className="mb-4 p-2 bg-red-100 text-red-700 rounded text-center">
                {error}
            </div>
        )}

        <div className="flex flex-col items-center">
            <div className="w-24 h-64 bg-black rounded-3xl p-2 flex flex-col justify-between">
                {/* Luz Roja */}
                <div className={`w-20 h-20 rounded-full mx-auto ${semaforoState.foco_rojo ? 'bg-red-500' : 'bg-gray-700'} shadow-lg`}
                title="Rojo"></div>
                {/* Luz Amarilla */}
                <div className={`w-20 h-20 rounded-full mx-auto ${semaforoState.foco_amarillo ? 'bg-yellow-500' : 'bg-gray-700'} shadow-lg`}
                title="Amarillo"></div>
                {/* Luz Verde */}
                <div className={`w-20 h-20 rounded-full mx-auto ${semaforoState.foco_verde ? 'bg-green-500' : 'bg-gray-700'} shadow-lg`}
                title="Verde"></div>
            </div>
        </div>

        {/* Mostrar el tiempo */}
        <div className="mb-6 text-center">
            <h3 className="text-lg font-semibold text-gray-700 mb-1">Tiempo Transcurrido</h3>
            <div className="text-3xl font-mono bg-gray-800 text-green-400 px-4 py-2 rounded-lg">
                {formatTime(semaforoState.current_time)}
            </div>
        </div>
        </div>
    );

};