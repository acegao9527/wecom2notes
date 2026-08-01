

# wecom2notes

Servicio de código abierto para sincronizar mensajes de WeCom (WeChat Work) a aplicaciones de notas.

`wecom2notes` extrae mensajes del archivo de contenido de sesiones de WeCom, los consolida en una base de datos SQLite y, según las reglas de enrutamiento, los entrega a Craft, Obsidian/Markdown, Logseq, Notion, WebDAV, repositorios de notas gestionados por Git o interfaces HTTP.

## Matriz de compatibilidad

| Tipo | Estado | Descripción |
| --- | --- | --- |
| Archivo de sesiones de WeCom | Soportado | Extrae y descifra mensajes archivados mediante el SDK oficial |
| Craft | Soportado | Compatible con enlaces heredados y adaptadores de destino |
| Obsidian / Markdown | Soportado | Escribe en directorios o vaults de Markdown locales |
| Logseq | Soportado | Reutiliza la escritura en Markdown y genera el estilo de bloques |
| Notion | Soportado | Compatible con anexar a páginas o páginas de base de datos |
| WebDAV | Soportado | Adjunta archivos de Markdown remotos mediante GET/PUT |
| Repositorios de notas en Git | Soportado | Opción de commit automático tras escribir en Markdown |
| Interfaz HTTP | Soportado | Envía mensajes unificados a webhooks mediante POST/PUT/PATCH/GET |
| Extracción automática de WeChat personal | Fuera del alcance de la versión inicial estable | Los archivos de chat exportados pueden procesarse mediante un importador |

## Arquitectura

```text
Source Connector
  WeCom Archive / Importer

Message Normalizer
  UnifiedMessage / AttachmentInfo

Storage + Queue
  SQLite / source_cursors / deliveries

Router
  legacy Craft binding migration / DB routes / config/routes.json / env targets

Target Adapter
  Craft / Obsidian / Markdown / Logseq / Notion / WebDAV / Git / HTTP
```

## Inicio rápido

```bash
cp .env.example .env
./docker-deploy.sh
curl http://localhost:8001/
curl http://localhost:8001/openapi.json
```

Ver registros:

```bash
docker logs -f wecom2notes
```

Una vez finalizadas las pruebas locales en Mac, detenga los contenedores:

```bash
docker compose down
```

## Configuración

Configuración mínima de WeCom:

```env
WECOM_TOKEN=your_wecom_token
WECOM_CORP_ID=your_corp_id
WECOM_ENCODING_AES_KEY=your_encoding_aes_key
WECOM_APP_SECRET=your_archive_secret
WECOM_PRIVATE_KEY_PATH=private_key.pem
```

Configuración mínima de Obsidian/Markdown:

```env
OBSIDIAN_VAULT_PATH=/notes
OBSIDIAN_BASE_DIR=WeCom
OBSIDIAN_MODE=daily
```

Por defecto, Docker monta `HOST_NOTES_DIR` en `/notes` dentro del contenedor.

## API de administración

- `GET /admin`: Redirige al panel de administración integrado.
- `GET /admin/ui/`: Frontend estático del panel de administración.
- `GET /`: Verificación de estado (health check).
- `GET /openapi.json`: Especificación OpenAPI.
- `GET /metrics`: Métricas de texto para Prometheus.
- `GET /admin/overview`: Datos generales del panel de administración.
- `GET /admin/target-types`: Consulta los tipos de destino soportados.
- `GET /admin/destinations`: Consulta los destinos de entrega.
- `POST /admin/destinations`: Crea o actualiza un destino de entrega.
- `PUT /admin/destinations/{destination_id}`: Actualiza un destino de entrega.
- `PATCH /admin/destinations/{destination_id}/enabled`: Habilita o deshabilita un destino de entrega.
- `DELETE /admin/destinations/{destination_id}`: Elimina un destino de entrega y sus rutas asociadas.
- `POST /admin/destinations/{destination_id}/verify`: Verifica la configuración del destino.
- `GET /admin/routes`: Consulta las reglas de enrutamiento.
- `POST /admin/routes`: Crea una regla de enrutamiento.
- `PUT /admin/routes/{route_id}`: Actualiza una regla de enrutamiento.
- `PATCH /admin/routes/{route_id}/enabled`: Habilita o deshabilita una regla de enrutamiento.
- `DELETE /admin/routes/{route_id}`: Elimina una regla de enrutamiento.
- `POST /admin/routes/test`: Prueba qué destinos se activarían con un mensaje simulado.
- `GET /admin/deliveries`: Consulta el estado de entrega.
- `GET /admin/messages`: Filtra y consulta mensajes unificados.
- `GET /admin/messages/{source}/{msg_id}`: Consulta detalles del mensaje, adjuntos y registros de entrega.
- `POST /admin/replay`: Reenvía manualmente según `source + msg_id`.

Por defecto, la API de administración no requiere autenticación. Se recomienda configurar `ADMIN_TOKEN` en entornos de producción. Una vez configurado, el panel de administración solicitará el token y las llamadas a la API deberán realizarse mediante el encabezado `X-Admin-Token`.

## Compatibilidad con enlaces de Craft

La API de enlaces heredada de Craft sigue disponible:

```bash
curl -X POST http://localhost:8001/bindings \
  -H "Content-Type: application/json" \
  -d '{
    "wecom_openid": "用户OpenID",
    "craft_link_id": "Craft链接ID",
    "craft_document_id": "Craft文档ID",
    "craft_token": "pdk_xxx",
    "display_name": "显示名称"
  }'
```

## Importación masiva

Admite la importación de archivos CSV, Markdown, HTML y de texto:

```bash
python scripts/import_messages.py path/to/export.csv --source import
```

Los mensajes importados seguirán la misma cadena de enrutamiento y entrega.

## Documentación

- [Configuración de WeCom](docs/wecom.md)
- [Destino Craft](docs/craft.md)
- [Destino HTTP](docs/http.md)
- [Destino Obsidian / Markdown](docs/obsidian.md)
- [Despliegue](docs/deployment.md)
- [Solución de problemas](docs/troubleshooting.md)
- [Lista de verificación de lanzamiento](docs/release-checklist.md)

## Consideraciones de seguridad

- No commitee los archivos `.env`, claves privadas, bases de datos ni el contenido real de los vaults de notas al repositorio.
- La imagen de Docker ya no copia `.env` ni `private_key.pem`; las configuraciones sensibles deben inyectarse mediante variables de entorno, volúmenes o secrets.
- Evite mostrar tokens completos, secretos y el contenido original de los mensajes en los registros (logs).

## Licencia

MIT
