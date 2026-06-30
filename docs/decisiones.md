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
## D-008 · Calibración real de baselines (ground truth PSA): diferida, no implementada en Sprint 4

**Fecha:** Sprint 4
**Estado:** Aceptada, con tech-debt explícito

**Contexto:** los campos `referencia_centering`, `referencia_corners`,
`referencia_edges` y `referencia_surface` de `GradingBaseline` se cargan en
`CalificarCartaService` pero nunca se usan para calcular ni ajustar ningún
subgrade — solo determinan qué tan ancha es la banda de incertidumbre
(`calcular_banda_incertidumbre`) y qué versión de algoritmo se loguea. La
"selección" del baseline (específico vs. global, según `tamano_muestra`)
funciona correctamente, pero el baseline seleccionado no calibra nada en la
práctica.

El Caso de Negocio v1.6 (pág. 11) es explícito sobre qué debería pasar:

> "El dataset de 800 cartas con grading PSA confirmado se usa para calibrar
> los parámetros de nuestro algoritmo (...) qué métricas geométricas y de
> superficie corresponden a qué grados PSA dentro de cada set y cada tipo
> de acabado."

Y el requisito R10 (★) exige: "el dataset de 800 cartas con grading PSA
confirmado debe auditarse antes de la versión 1.0 del algoritmo". Ese
dataset no existe en el repo ni en el ambiente de desarrollo — el baseline
global sembrado en la migración `0007_pipeline_grading` tiene
`tamano_muestra=0`. Implementar una fórmula de calibración sin datos reales
de PSA contra los cuales validarla no es "calibrar": es inventar un umbral
arbitrario, lo cual contradice el propio R10 y arriesga producir grados
menos confiables que los actuales, no más.

**Decisión:** dejar la calibración real fuera del alcance del Sprint 4. La
selección de baseline (específico/global con fallback) queda implementada
y probada; la calibración contra `referencia_*` queda pendiente hasta que
exista el dataset de 800 cartas PSA (o un subconjunto curado, como anticipa
la definición de "Ground Truth" del Caso de Negocio) para derivar esos
valores de referencia de forma auditable, en línea con S5 (regresión
automática del algoritmo contra el dataset de calibración).

**Alternativas evaluadas:**
- Implementar una fórmula de calibración igual (ej. `score / referencia`,
  acotado a 1.0) usando los valores placeholder actuales (`0.7` en los
  cuatro ejes, sembrados por la migración): se descartó porque, verificado
  empíricamente, homogeniza casi todos los subgrades hacia 10.0 con
  cualquier carta de calidad media-alta — degrada la capacidad de
  diferenciar calidad entre cartas en vez de mejorarla, sin ninguna base
  estadística real detrás del número `0.7`.
- Marcar el campo `tamano_muestra` como bloqueante (rechazar evaluación si
  no hay baseline calibrado): contradice el criterio de aceptación de la
  US 193, que pide explícitamente fallback al global cuando no hay ground
  truth suficiente.

**Consecuencias:** el sistema persiste correctamente qué baseline se usó
(`baseline_id_usado`, `version_algoritmo_grading` — ver fix de Sprint 4) y
la selección específico/global es funcional y testeada, pero el grado
reportado hoy es equivalente a un baseline global no calibrado para todos
los casos. Cuando se incorpore el dataset de 800 cartas PSA (o el
subconjunto inicial mencionado en el Caso de Negocio), la calibración real
debe entrar como una US propia de un sprint futuro, con su propia suite de
regresión contra el dataset (S5) antes de habilitarse en producción.

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
