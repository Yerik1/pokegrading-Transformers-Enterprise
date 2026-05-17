# Recursos Azure — PokéGrading

Este documento define la organización inicial de recursos Azure prevista para PokéGrading. Su propósito es documentar qué recursos se necesitan, para qué se usan, cómo se nombran y qué consideraciones aplican para el Sprint 1 y la evolución posterior del sistema.

PokéGrading utilizará Azure como infraestructura cloud principal para almacenamiento, base de datos, monitoreo, control de costos y gestión segura de secretos. Durante Sprint 1, el desarrollo puede ejecutarse localmente, pero la arquitectura debe quedar preparada para usar recursos cloud gestionados.

---

## 1. Objetivo de la infraestructura

La infraestructura de PokéGrading debe permitir:

- Ejecutar el sistema en ambientes controlados.
- Almacenar imágenes de referencia del catálogo.
- Persistir usuarios, cartas, auditoría y versiones futuras del algoritmo.
- Mantener configuración sensible fuera del repositorio.
- Controlar costos mediante presupuestos y alertas.
- Preparar observabilidad básica para logs, métricas y trazabilidad.
- Separar recursos por ambiente cuando el proyecto evolucione.

---

## 2. Ambiente inicial

Para Sprint 1 se considera como ambiente base:

```text
dev
```

Este ambiente corresponde al entorno de desarrollo y pruebas iniciales del equipo.

En Sprint 1 no es obligatorio tener una infraestructura productiva completa, pero sí debe estar definida la organización de recursos y, cuando aplique, los recursos mínimos para probar las funcionalidades iniciales.

---

## 3. Recursos mínimos previstos

| Recurso Azure | Nombre sugerido | Propósito |
|---|---|---|
| Resource Group | `rg-te-pgd-dev` | Agrupar todos los recursos del ambiente de desarrollo. |
| Storage Account | `sttepgddev01` | Almacenar imágenes de referencia del catálogo. |
| Blob Container | `catalog-reference-images` | Contenedor privado para imágenes de referencia de cartas. |
| Azure Database for PostgreSQL | Pendiente | Base de datos relacional del sistema. |
| Key Vault | Pendiente | Gestión segura de secretos y connection strings. |
| Application Insights | Pendiente | Observabilidad, métricas y monitoreo. |
| Budget | Pendiente | Control de gasto mensual y alertas. |

---

## 4. Recursos relevantes para Sprint 1

En Sprint 1 las funcionalidades principales son:

- Registrar cuenta.
- Agregar carta al catálogo.

Por lo tanto, los recursos cloud más relevantes son:

| Recurso | Uso en Sprint 1 |
|---|---|
| Azure Blob Storage | Guardar imágenes de referencia del catálogo. |
| Azure Database for PostgreSQL | Persistir usuarios, cartas y auditoría si se trabaja contra ambiente cloud. |
| Key Vault | Guardar secretos si se configura conexión cloud. |
| Budget / Cost Alerts | Controlar costos del ambiente de desarrollo. |

Para evitar costos innecesarios durante el desarrollo inicial, se puede trabajar localmente con:

| Recurso local | Reemplaza temporalmente |
|---|---|
| PostgreSQL local o Docker | Azure Database for PostgreSQL |
| Azurite | Azure Blob Storage |
| `.env` local no versionado | Key Vault |
| Logs locales | Application Insights |

---

## 5. Convención de nomenclatura

Los recursos deben nombrarse usando minúsculas, sin espacios, sin tildes y con identificadores consistentes.

Formato general:

```text
<prefijo>-<proyecto>-<ambiente>-<componente>
```

Ejemplos:

```text
rg-te-pgd-dev
sttepgddev01
psql-pokegrading-dev
kv-pokegrading-dev
appi-pokegrading-dev
```

Para Storage Account, Azure exige nombres globalmente únicos, solo con letras minúsculas y números, sin guiones.

---

## 6. Storage Account

### Nombre creado

```text
sttepgddev01
```

### Resource Group

```text
rg-te-pgd-dev
```

### Región

```text
East US
```

### Redundancia

```text
Locally-redundant storage (LRS)
```

### Uso

Este Storage Account se usará para almacenar imágenes de referencia del catálogo.

Cuando un Admin agregue una carta al catálogo, el sistema deberá:

1. Validar la imagen.
2. Subir la imagen a Azure Blob Storage.
3. Recibir una referencia como `blobUri` o `storageKey`.
4. Guardar esa referencia en la base de datos junto con la carta.

---

## 7. Blob Container

### Nombre creado

```text
catalog-reference-images
```

### Nivel de acceso

```text
Private / No anonymous access
```

### Uso en Sprint 1

Este contenedor almacena las imágenes de referencia de las cartas agregadas al catálogo por un Admin.

No debe permitir acceso anónimo público.

---

## 8. Recursos futuros posibles

Estos recursos no son obligatorios para Sprint 1, pero quedan previstos para la evolución del sistema:

| Recurso futuro | Posible uso |
|---|---|
| Azure Database for PostgreSQL | Persistencia cloud de usuarios, cartas, auditoría y evaluaciones. |
| Key Vault | Gestión centralizada de secretos. |
| Application Insights | Logs, métricas, trazas y monitoreo. |
| Log Analytics Workspace | Centralización de logs operativos. |
| Azure Service Bus | Cola de evaluaciones en una evolución futura. |
| Azure Container Apps | Despliegue del backend. |
| Azure API Management | Exposición futura de API B2B. |

---

## 9. Recursos que NO son necesarios en Sprint 1

Para evitar sobrecostos y complejidad, no se recomienda crear todavía:

- Kubernetes.
- API Management.
- Front Door.
- CDN.
- Service Bus.
- Azure Functions para procesamiento.
- Infraestructura B2B.
- Integración real con PokéMarket.
- Integración con Discovery API.
- Proveedor real de correo.

---

## 10. Variables de entorno relacionadas

El archivo `.env.example` debe documentar variables como:

```env
ENVIRONMENT=local

DATABASE_URL=postgresql://pokegrading:pokegrading@localhost:5432/pokegrading

JWT_SECRET=change-me-local-only
JWT_ALGORITHM=HS256

DISCLOSURE_VERSION=2026-04-v1

AZURE_STORAGE_CONNECTION_STRING=UseDevelopmentStorage=true
AZURE_BLOB_CONTAINER_CATALOG=catalog-reference-images

FRONTEND_URL=http://localhost:5173
ALLOWED_ORIGINS=http://localhost:5173
```

Los valores reales no deben subirse al repositorio.

---

## 11. Reglas de seguridad

La configuración de infraestructura debe seguir estas reglas:

- No almacenar secretos en el repositorio.
- No subir archivos `.env`.
- No subir connection strings reales.
- No subir tokens ni credenciales de Azure.
- No subir imágenes reales de usuarios.
- No exponer públicamente los contenedores de Blob Storage.
- Usar acceso privado por defecto.
- Guardar imágenes en Blob Storage, no directamente en la base de datos.
- Guardar en base de datos solo la referencia al archivo.

---

## 12. Relación con la arquitectura lógica

| Componente lógico | Recurso Azure |
|---|---|
| Blob Client | Azure Blob Storage |
| Catalog Module | Blob Container `catalog-reference-images` |
| Data Access / Repositories | PostgreSQL local o Azure Database for PostgreSQL |
| Audit Module | PostgreSQL / logs futuros |
| Security / Secrets | `.env` local o Key Vault futuro |
| Observability | Application Insights futuro |

---

## 13. Estado actual

| Elemento | Estado |
|---|---|
| Resource Group dev | `rg-te-pgd-dev` existente |
| Storage Account dev | `sttepgddev01` creado |
| Blob Container catálogo | `catalog-reference-images` creado |
| Región | `East US` configurado |
| Redundancia | `Locally-redundant storage (LRS)` configurado |
| Acceso anónimo | `Private / No anonymous access` configurado |
| PostgreSQL | Local por ahora; pendiente en Azure |
| Key Vault | Pendiente |
| Application Insights | Pendiente |
| Budget | Pendiente de configurar |
| Azurite local | Recomendado para desarrollo local |
| `.env.example` | Versionado en el repositorio |

---

## 14. Checklist de Sprint 1

Para Sprint 1, la configuración de Azure queda documentada si se cumple:

- [x] Resource Group de desarrollo identificado.
- [x] Storage Account de desarrollo creado.
- [x] Blob Container para catálogo creado.
- [x] Acceso anónimo deshabilitado.
- [x] Región y redundancia documentadas.
- [x] Uso de `.env.example` documentado.
- [x] Secretos excluidos del repositorio.
- [ ] Budget o alertas de costo configuradas.
- [ ] PostgreSQL local documentado o configurado.
- [ ] Azurite local documentado o configurado.

---

## 15. Notas finales

La infraestructura inicial debe mantenerse simple. La prioridad del Sprint 1 es demostrar una base técnica ordenada, segura y alineada con la arquitectura lógica, sin incurrir en sobreingeniería.

El sistema queda preparado para crecer hacia procesamiento de evaluaciones, versionado de algoritmo, revisión humana, integración con PokéMarket y reporting, pero no es necesario desplegar toda esa infraestructura desde el inicio.
