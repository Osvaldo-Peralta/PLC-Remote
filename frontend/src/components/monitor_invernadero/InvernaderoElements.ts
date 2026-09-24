// frontend/src/components/monitor_invernadero/InvernaderoElements.ts
/* Elementos del proyecto de invernadero (nodos definidos en config.py del backend). */

export interface SensorConfig {
  id: string;    // clave tal como la regresa GET /status
  name: string;
  unit: string;
}

export interface ActuatorConfig {
  id: string;       // clave tal como la regresa GET /status
  name: string;
  endpoint: string; // ruta base para POST /endpoint/{estado}
}

export const sensors: SensorConfig[] = [
  { id: 'humedad_ext', name: 'Humedad Exterior', unit: '%' },
  { id: 'humedadSHT41', name: 'Humedad Interior (SHT41)', unit: '%' },
  { id: 'temperaturaExt', name: 'Temperatura Exterior', unit: '°C' },
  { id: 'temperaturaSHT41', name: 'Temperatura Interior (SHT41)', unit: '°C' },
];

export const actuators: ActuatorConfig[] = [
  { id: 'extractor', name: 'Extractor', endpoint: '/extractor' },
  { id: 'humificador', name: 'Humidificador', endpoint: '/humificador' },
  { id: 'mister', name: 'Nebulizador (Mister)', endpoint: '/mister' },
];

export const modoAutomatico: ActuatorConfig = {
  id: 'modoAutomatico',
  name: 'Modo Automático',
  endpoint: '/modo_automatico',
};