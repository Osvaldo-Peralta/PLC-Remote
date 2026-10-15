# Sistema HMI: desarrollo con Docker Compose

Esta configuración ejecuta el frontend React/Vite y el backend FastAPI en contenedores separados. Está pensada para desarrollo local; no es una imagen de producción.

## Requisitos

- Docker Desktop con Docker Compose (o Docker Engine + Compose).
- Una ruta de red desde Docker hasta el PLC Siemens configurado en `PLC_ENDPOINT`.

## Arranque

Desde la raíz del proyecto:

```bash
docker compose up --build
```

- HMI: http://localhost:5173
- API: http://localhost:8000/docs (disponible cuando el backend completa su inicio y se conecta al PLC)

Detener:

```bash
docker compose down
```

Logs:

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

## Configurar el PLC

La dirección predeterminada sigue siendo `opc.tcp://192.168.1.99:4840`. Para cambiarla, copia `.env.example` a `.env` y modifica `PLC_ENDPOINT`. No incluyas credenciales ni secretos en el repositorio.

## Datos experimentales

Los CSV se escriben en `backend/experiments/data` y se conservan en el equipo anfitrión gracias al volumen configurado en Compose. No se incluyen los CSV históricos en la imagen del backend.

## Notas

- Git sigue ejecutándose desde tu terminal habitual; no se necesita un contenedor para Git.
- El backend actual espera la conexión al PLC durante su inicio y reintenta hasta conectarse. Si el PLC está apagado o la ruta de red no funciona, el contenedor del backend puede permanecer en fase de inicio y `/docs` no responderá todavía. El frontend puede iniciar por separado.
- El frontend usa el servidor de desarrollo de Vite y su API sigue apuntando a `http://localhost:8000`; no se cambió la lógica de los componentes.
- El archivo `requirements.txt` fija las versiones directas que están presentes en el entorno virtual incluido en el ZIP original. El contenedor instala sus propias dependencias; no copia ni reutiliza el entorno virtual local.
- No se pudo ejecutar `docker compose build` en el entorno de revisión porque Docker no está instalado allí. La configuración debe verificarse en tu equipo antes de usarla con el PLC.
