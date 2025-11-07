// PLCElements.ts
/* Aqui se definiran todos los elementos que pueden existir en el PLC */
export interface PLCElementConfig {
    id: string;
    name: string;
    type: 'button' | 'light' | 'timer' | 'toggle';
    endpoint?: string; // Endpoint del backend para leer (opcional)
    command?: string; // endpoint para enviar comandos (start, stop) (opcional)
    variant?: 'primary' | 'secondary' | 'success' | 'danger'; // Colores para los botones (opcional)
}

export const plcElements: PLCElementConfig[] = [
    {
        id: 'start',
        name: 'INICIO',
        type: 'button', // No necesita estado, solo comando
        // endpoint: undefined, // Omitido porque no se lee
        command: '/start',
        variant: 'success',
    },
    {
        id: 'stop',
        name: 'DETENER',
        type: 'button', // No necesita estado, solo comando
        // endpoint: undefined, // Omitido porque no se lee
        command: '/stop',
        variant: 'danger'
    },
    {
        id: 'status',
        name: 'Estado Actual',
        type: 'light',
        endpoint: '/status', // Este sí tiene un endpoint para leer su estado
        // command: undefined, // Omitido porque no es un botón de comando
    },
    /*
    {
        id: 'timer',
        name: 'Timer',
        type: 'timer',
        endpoint: '/tiempo-restante', // Este también se lee
        // command: undefined, // Omitido
    },
    */
];