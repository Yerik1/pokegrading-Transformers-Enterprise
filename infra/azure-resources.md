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