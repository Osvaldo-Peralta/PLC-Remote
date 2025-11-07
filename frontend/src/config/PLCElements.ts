//rc/config/PLCElements.ts
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
/*
   {
        id: 'status',
        name: 'Estado Actual',
        type: 'light',
        endpoint: '/status', // Este sí tiene un endpoint para leer su estado
        // command: undefined, // Omitido porque no es un botón de comando
    },
*/
    {
        id: 'foco_rojo',
        name: 'Foco Rojo',
        type: 'light',
        endpoint: '/foco_rojo',
        variant: 'danger'
    },
    {
        id: 'foco_amarillo',
        name: 'Foco Amarillo',
        type: 'light',
        endpoint: '/foco_amarillo',
        variant: 'danger'
    },
    {
        id: 'foco_verde',
        name: 'Foco Verde',
        type: 'light',
        endpoint: '/foco_verde',
        variant: 'success'
    },
    {
        id: 'current_time',
        name: 'Tiempo Restante',
        type: 'timer',
        endpoint: '/current_time',
    },
];