

**Reachable** verifica si una URL existe y es accesible.

# Características
- Usa solicitudes `HEAD` en lugar de `GET` para ahorrar ancho de banda
- Sigue redirecciones
- Maneja redirecciones locales (sin URL completa en el encabezado `location`)
- Registra todas las URLs de la cadena de redirección
- Verifica si la URL redirigida coincide con el TLD de la URL de origen
- Detecta protección de Cloudflare
- Evita detectores básicos de bots
    - Usa un agente de usuario aleatorio de Chrome
    - Espera entre solicitudes consecutivas al mismo host
    - Incluye el encabezado `Host`
    - Puede usar Playwright para realizar la solicitud
- Uso de HTTP/2
- Detecta dominios de estacionamiento

# Instalación
Puedes instalarlo con pip:
```bash
pip install reachable
```
Si deseas usar playwright:
```bash
pip install reachable[playwright]
```
O clona este repositorio y simplemente ejecuta:
```bash
cd reachable/
pip install -e .
```

# Uso

## URL Simple
```python
from reachable import is_reachable
result = is_reachable("https://google.com")
```

La salida se verá así:
```json
{
    "original_url": "https://google.com",
    "final_url": "https://www.google.com/",
    "response": null, 
    "status_code": 200,
    "success": true,
    "error_name": null,
    "cloudflare_protection": false,
    "redirect": {
        "chain": ["https://www.google.com/"],
        "final_url": "https://www.google.com/",
        "tld_match": true
    }
}
```

## Múltiples URLs
```python
from reachable import is_reachable
result = is_reachable(["https://google.com", "http://bing.com"])
```

La salida se verá así:
```json
[
    {
        "original_url": "https://google.com",
        "final_url": "https://www.google.com/",
        "response": null, 
        "status_code": 200,
        "success": true,
        "error_name": null,
        "cloudflare_protection": false,
        "redirect": {
            "chain": ["https://www.google.com/"],
            "final_url": "https://www.google.com/",
            "tld_match": true
        }
    },
    {
        "original_url": "http://bing.com",
        "final_url": "https://www.bing.com/?toWww=1&redig=16A78C94",
        "response": null,
        "status_code": 200,
        "success": true,
        "error_name": null,
        "cloudflare_protection": false,
        "redirect": {
            "chain": ["https://www.bing.com:443/?toWww=1&redig=16A78C94"],
            "final_url": "https://www.bing.com/?toWww=1&redig=16A78C94",
            "tld_match": true
        }
    }
]
```

## Asíncrono
```python
import asyncio
from reachable import is_reachable_async

result = asyncio.run(is_reachable_async("https://google.com"))
```
o
```python
import asyncio
from reachable import is_reachable_async

urls = ["https://google.com", "https://bing.com"]

try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    # No loop already exists so we crete one
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
try:
    result = loop.run_until_complete(asyncio.gather(*[is_reachable_async(url) for url in urls]))
finally:
    loop.close()
```

### Manejo de grandes volúmenes con Taskpool

Si deseas procesar una gran cantidad de URLs (> 500), rápidamente alcanzarás los límites de tu hardware y/o sistema operativo, ya que solo puedes abrir un número definido de conexiones activas.

Para sortear este problema, puedes usar la clase `TaskPool`. Utiliza semáforos de Asyncio para limitar la cantidad de hilos (threads) de asyncio en ejecución. Funciona adquiriendo un bloqueo al iniciar el trabajador y liberándolo cuando termina. Esto permite mantener siempre un número determinado de trabajadores de asyncio sin saturar el sistema operativo.

```python
import asyncio

from reachable import is_reachable_async
from reachable.client import AsyncClient
from reachable.pool import TaskPool


urls = ["https://google.com", "https://bing.com"]


async def worker(url, client):
    result = await is_reachable_async(url, client=client)
    return result


async def workers_builder(urls, pool_size: int = 100):
    async with AsyncClient() as client:
        tasks = TaskPool(workers=pool_size)

        for url in urls:
            await tasks.put(worker(url, client=client))

        await tasks.join()

    return tasks._results


try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    # No loop already exists so we crete one
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

try:
    result = loop.run_until_complete(workers_builder(urls))
    print(result)
finally:
    loop.close()

```
