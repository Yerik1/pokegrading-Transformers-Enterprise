# Log de decisiones técnicas

Este documento registra decisiones técnicas tomadas durante el desarrollo que
no quedan capturadas en el código pero que el equipo (presente y futuro) debe
conocer.

Formato: cada entrada tiene contexto, decisión, alternativas evaluadas y
consecuencias. Inspirado en ADRs (Architecture Decision Records) pero más
ligero — los ADRs formales viven en el wiki técnico.

---

## D-001 · Autenticación: JWT con rotación de refresh

**Fecha:** Sprint 1
**Estado:** Aceptada

**Contexto:** la US "Iniciar sesión" requiere sesión persistente entre requests.
Hay que elegir un esquema de tokens.

**Decisión:** JWT con HS256.
- Access token: 15 minutos, contiene `sub` (user id) y `rol`.
- Refresh token: 7 días, mismo sujeto, claim `tipo: refresh`.
- Cada `/auth/refresh` emite un nuevo par y el cliente debe descartar el
  refresh anterior (rotación).

**Alternativas evaluadas:** sesiones server-side con Redis (más complejo,
requiere infra extra); RS256 (curva de aprendizaje + manejo de claves
asimétricas; innecesario para single-app).

**Consecuencias:** simple, sin estado en el servidor. Si el refresh se
filtra, la rotación limita la ventana de exposición.

---

## D-002 · Validación dual del catálogo (R11): diferida a Sprint 2+

**Fecha:** Sprint 1
**Estado:** Aceptada, con tech-debt explícito

**Contexto:** el wiki técnico (R11) exige que "altas y modificaciones del
catálogo requieren validación dual: una persona propone, otra valida antes de
publicar". La US "Agregar carta al catálogo" dice literalmente "al guardar...
deja la carta activa en el catálogo" — un solo paso.

**Decisión:** implementar la US tal como está (un solo paso, queda activa al
crear). Crear una US nueva para Sprint 2+ que cubra R11.

**Alternativas evaluadas:**
- Full workflow propuesta/en_revision/publicada/rechazada: cumple R11 pero
  contradice la US y agrega complejidad significativa.
- Lite con campo `estado`: estado intermedio, ni cumple R11 ni respeta la US.

**Consecuencias:** Sprint 1 cierra la US tal como está escrita. R11 queda
documentado como tech-debt. La US nueva del Sprint 2+ se llamaría algo como
"Validar carta del catálogo con doble verificación".

---

## D-003 · Almacenamiento de imágenes: Azure Blob desde día 1

**Fecha:** Sprint 1
**Estado:** Aceptada

**Contexto:** la wiki especifica Azure Blob (R8). Las opciones eran usar el
servicio real, un emulador (Azurite), o disco local con interfaz abstracta.

**Decisión:** Azure Blob real desde día 1, con interfaz abstracta
(`IAlmacenamientoImagenes`) para permitir swap futuro.

**Alternativas evaluadas:**
- Azurite: más cercano a prod pero suma una pieza al docker-compose con
  posibilidad de fallar en máquinas con setup distinto.
- Disco local: simple pero no representativo de prod.

**Consecuencias:** cada laptop del equipo necesita acceso a la Storage Account
`stpokegradingdev` con la connection string. El setup está documentado en
`docs/azure-setup.md`. Costo estimado: <$5/mes para dev.

---

## D-004 · HEIC: rechazado en el endpoint de catálogo

**Fecha:** Sprint 1
**Estado:** Aceptada

**Contexto:** SP3 lista JPEG, PNG y HEIC como formatos permitidos. HEIC
requiere la librería `pillow-heif` (~10 MB) y agrega complejidad.

**Decisión:** en el endpoint de catálogo (admin-only, Sprint 1), rechazar
HEIC con mensaje claro "convertir a JPEG/PNG primero". Cuando se construya
la US futura de upload de Submitter (donde HEIC viene de iPhones), se
agrega `pillow-heif` en ese flow específico.

**Alternativas evaluadas:**
- Aceptar HEIC y convertir a JPEG: trabajo adicional sin uso real para admins.
- Guardar HEIC tal cual: no todos los navegadores lo renderizan.

**Consecuencias:** menos código, menos dependencias, pero el admin no puede
subir HEIC directamente. Como los admins suben desde su laptop (no iPhone),
no es restrictivo.

---

## D-005 · `set_codigo` y `numero`: strings libres, no validados

**Fecha:** Sprint 1
**Estado:** Aceptada

**Contexto:** Pokémon TCG tiene ~150 sets oficiales y crece. Validar contra
un enum interno de sets significa actualizarlo cada vez que sale uno nuevo.

**Decisión:** ambos campos son `VARCHAR` libres. La integridad referencial
contra duplicados queda garantizada por el `UNIQUE` compuesto sobre el
identity tuple.

**Alternativas evaluadas:**
- Enum de sets en código + migración al agregar sets: deuda recurrente.
- Tabla de sets relacionada vía FK: más sólido pero scope grande para Sprint 1.

**Consecuencias:** admins tienen flexibilidad total. Si en el futuro queremos
validación contra catálogo de sets oficiales, se agrega una tabla `sets`
con FK y se hace una migración de datos.

---

## D-006 · SUPERADMIN como rol separado

**Fecha:** Sprint 1
**Estado:** Aceptada

**Contexto:** el wiki R3 dice "Admin / SuperAdmin" como entidad única. El
equipo decidió tratarlos como dos niveles distintos.

**Decisión:** agregar `superadmin` al enum `rol_enum` (5 roles totales).
Admin gestiona catálogo + usuarios. SuperAdmin todo eso + gestión de admins.
Ambos pueden agregar cartas al catálogo (usando el alias
`requerir_admin_o_superadmin`).

**Alternativas evaluadas:**
- Flag `is_super_admin` booleano: menos granular, mezcla rol con permisos.
- Tratar SuperAdmin = Admin (un solo rol): inconsistente con el wiki.

**Consecuencias:** el enum se mantiene como source of truth de roles.
Future-proof para cuando vengan endpoints "solo SuperAdmin" (configuración
de sistema, gestión de admins, etc.).

---

## D-007 · CI en GitHub Actions, no Azure Pipelines

**Fecha:** Sprint 1
**Estado:** Aceptada

**Contexto:** el wiki V6 originalmente especificaba Azure Pipelines. El repo
está hospedado en GitHub.

**Decisión:** GitHub Actions. Backend job (Postgres service + ruff + black
+ alembic + pytest cov-fail-under=75) + Frontend job (npm ci + type-check
+ build).

**Alternativas evaluadas:**
- Azure Pipelines: requiere conectar el repo a Azure DevOps, agrega fricción.

**Consecuencias:** sub-30s typical run para backend, ~13s para frontend.
Branch protection configurada en `develop` y `main` requiriendo CI verde.

---

## Plantilla para nuevas entradas

```markdown
## D-NNN · Título corto

**Fecha:** Sprint N
**Estado:** Propuesta / Aceptada / Rechazada / Superseded por D-XXX

**Contexto:** [qué problema/decisión surgió]

**Decisión:** [qué elegimos]

**Alternativas evaluadas:** [qué descartamos y por qué]

**Consecuencias:** [trade-offs, implicaciones futuras]
```
