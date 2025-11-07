// Dashboard.tsx
import { plcElements } from "../config/PLCElements";
import { usePLCState } from "../hooks/usePLCState";
import Button from "./common/Button";
import Light from "./common/Light";

export default function Dashboard() {
    // Corregido: endpoints -> endpoint
    const { state, loading, error, sendCommand } = usePLCState(plcElements.filter(el => el.endpoint).map(el => ({id: el.id, endpoint: el.endpoint!})));

    const handleCommand = (command: string) => {
        if (command) {
            sendCommand(command);
        }
    };

    return (
        <div className="max-w-3xl mx-auto p-6 bg-gray-50 rounded-xl shadow-lg">
            <h2 className="text-2xl font-bold text-gray-800 mb-4">Panel de Control</h2>
            {error && (
                <div className="mb-4 p-2 bg-red-100 text-red-700 rounded">
                    {error}
                </div>
            )}
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                {plcElements.map((element => (
                    <div key={element.id} className="p-4 bg-white rounded-lg shadow">
                        <h3 className="text-lg font-semibold text-gray-700 mb-2">{element.name}</h3>
                        {element.type === 'button' && element.command && (
                            <Button
                                name={element.name}
                                variant={element.variant}
                                onClick={() => handleCommand(element.command!)}
                                disabled={loading[element.id]}
                                loading={loading[element.id]}
                            />
                        )}
                        {element.type === 'light' && (
                            <Light
                                name={element.name}
                                value={state[element.id]}
                            />
                        )}
                    {/* Aquí se pueden añadir más tipos de elementos */}
                    {/* {element.type === 'timer' && <TimerDisplay time={state[element.id]} />} */}
                    </div>
                )))}
            </div>
        </div>
    )
}