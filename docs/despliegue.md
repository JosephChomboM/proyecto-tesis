# Despliegue en Render y GitHub Actions

## Configuración reproducible

- Rama publicada: `main`. Los cambios se validan también en ramas y PR.
- Python 3.12 mediante `.python-version`.
- Dependencias fijadas con hashes en `requirements.lock` (incluye herramientas de verificación).
- Build: `python -m pip install --require-hashes -r requirements.lock && python -m pip install --no-deps .`
- Arranque: `python scripts/start.py`, con dirección `0.0.0.0` y puerto de `$PORT`.
- Health check: `/_stcore/health`.
- Una instancia; disco de 1 GB en `/var/data`; bases en `/var/data/restaurante`.
- `render.yaml` documenta el mismo servicio. No crees un segundo servicio si ya existe el manual.

El plan de servicio y disco son de pago. Confirma los precios del panel antes de activar.
Los archivos SQLite locales no se suben automáticamente al servidor. El primer arranque remoto
crea espacios nuevos; usa únicamente datos de prueba hasta validar el entorno.

## Acceso

Define `RESTAURANTE_ACCESS_PASSWORD` en Render con al menos 16 caracteres, introducidos
directamente por el administrador. No la escribas en Git, el README o el chat.
En Render el acceso queda bloqueado si falta la clave. Al rotarla, se invalidan las sesiones
anteriores en la siguiente ejecución. Hay cierre de sesión y una espera por intentos fallidos
en cada sesión. La clave compartida sirve para la evaluación con un administrador de confianza;
no proporciona cuentas individuales, permisos por participante ni aislamiento entre restaurantes.

Para uso comercial o varios restaurantes, sustituir este control por identidad OIDC y
autorización por usuario/establecimiento. No desactivar CORS ni XSRF para resolver problemas de acceso.

## Pipeline

1. Cada push y PR ejecuta instalación con hashes, Ruff, pytest y arranque real con health check.
2. Solo en `main`, después de pasar la verificación, GitHub Actions envía el commit probado al
   deploy hook de Render. El workflow tiene permisos de lectura y no persiste credenciales Git.
3. Render construye ese commit y verifica su health check antes de considerarlo disponible.
4. El servicio utiliza Auto-Deploy **Off**, pues el pipeline es quien solicita el despliegue.

El enlace secreto se obtiene en Render → servicio → Settings → Deploy Hook. Guardarlo como
secret de Actions llamado `RENDER_DEPLOY_HOOK_URL` en `JosephChomboM/proyecto-tesis`.
Debe ser el enlace del servicio de esta aplicación. No imprimirlo en logs ni guardarlo en archivos.
La petición usa `ref` para desplegar exactamente el commit verificado. El job confirma la solicitud,
no la finalización: el estado final de compilación y salud se consulta en Render.

Si no existe el secret, el job de despliegue falla con un mensaje; las pruebas siguen ejecutándose.
Una invitación de colaborador puede no dar acceso a configurar secretos; de ser necesario,
el propietario debe añadir este secret, sin compartir su token personal.

## Datos y recuperación

El disco persiste entre despliegues; una instancia evita compartir SQLite entre servidores.
El cambio de versión puede provocar una interrupción breve al tener disco adjunto.
Descarga respaldos consistentes desde la aplicación antes de cambios de esquema. Conserva
copias fuera de Render y comprueba su restauración. El disco persistente no sustituye esos respaldos.

Para volver a una versión anterior de código, utiliza un commit conocido mediante Render.
No asumas que eso revierte el esquema ni los datos: verifica compatibilidad y, si corresponde,
restaura una copia revisada con el servicio detenido.

## Actualizar dependencias

```powershell
uv pip compile pyproject.toml --extra dev --python 3.12 --generate-hashes --output-file requirements.lock
```

Verifica la actualización en PR antes de integrarla. La verificación local usa Python 3.12
y GitHub Actions comprueba el mismo lock en Linux.
