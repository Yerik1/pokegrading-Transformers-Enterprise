import { Link } from "react-router-dom";
import { HeaderApp } from "@/compartido/layout/HeaderApp";
import { AgregarCartaForm } from "@/catalogo/componentes/AgregarCartaForm";

/**
 * Página de "Agregar carta al catálogo".
 *
 * Solo accesible para admin/superadmin (la protección la maneja
 * `<RutaProtegida roles={['admin', 'superadmin']}>` en `App.tsx`).
 */
export function AgregarCartaPagina() {
  return (
    <div className="min-h-screen bg-paper">
      <HeaderApp />

      <main className="mx-auto max-w-4xl px-6 py-12 lg:px-10">
        <nav className="mb-8 flex items-center gap-2 text-xs uppercase tracking-wider text-ink-subtle">
          <Link to="/inicio" className="hover:text-ink">
            Inicio
          </Link>
          <span aria-hidden="true">/</span>
          <span className="text-ink">Catálogo · Agregar carta</span>
        </nav>

        <header className="mb-10">
          <h1 className="font-display text-5xl tracking-tight-display text-ink">
            Agregar carta al catálogo
          </h1>
          <p className="mt-3 max-w-2xl text-ink-muted">
            Da de alta una nueva entrada en el catálogo de referencia. Los
            cinco campos de identidad (set, número, edición, idioma, acabado)
            son requeridos; el resto es opcional pero recomendado.
          </p>
        </header>

        <AgregarCartaForm />
      </main>
    </div>
  );
}
