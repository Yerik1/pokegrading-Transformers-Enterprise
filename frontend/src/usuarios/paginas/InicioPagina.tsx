import { Link } from "react-router-dom";
import { useAuthStore } from "@/compartido/auth/auth-store";
import { HeaderApp } from "@/compartido/layout/HeaderApp";

/**
 * Landing post-login.
 *
 * Sirve como hub mientras se construye el resto del producto. El contenido
 * depende del rol del usuario:
 * - Submitter: mensaje placeholder de "evaluaciones próximamente".
 * - Admin/SuperAdmin: accesos directos a las funciones administrativas
 *   disponibles (por ahora solo "Agregar carta").
 */
export function InicioPagina() {
  const usuario = useAuthStore((s) => s.usuario);
  if (!usuario) return null;

  const esAdmin = usuario.rol === "admin" || usuario.rol === "superadmin";

  return (
    <div className="min-h-screen bg-paper">
      <HeaderApp />

      <main className="mx-auto max-w-5xl px-6 py-16 lg:px-10">
        <header className="mb-12">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-holo">
            Inicio
          </p>
          <h1 className="mt-2 font-display text-5xl tracking-tight-display text-ink">
            Hola, <em className="not-italic text-holo">{usuario.alias}</em>.
          </h1>
        </header>

        {esAdmin ? <PanelAdmin /> : <PanelSubmitter />}
      </main>
    </div>
  );
}

function PanelAdmin() {
  return (
    <section>
      <h2 className="mb-6 font-display text-2xl tracking-tight-display text-ink">
        Funciones administrativas
      </h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Link
          to="/admin/cartas/nueva"
          className="group rounded-card border border-ink/10 bg-cream p-6 transition-all hover:border-holo hover:shadow-sm"
        >
          <p className="mb-1 text-xs uppercase tracking-wider text-ink-subtle">
            Catálogo
          </p>
          <h3 className="font-display text-xl text-ink group-hover:text-holo">
            Agregar carta nueva →
          </h3>
          <p className="mt-2 text-sm text-ink-muted">
            Da de alta una nueva entrada en el catálogo de referencia con
            su identity tuple e imagen.
          </p>
        </Link>

        <div className="rounded-card border border-dashed border-ink/15 bg-cream-dark/30 p-6">
          <p className="mb-1 text-xs uppercase tracking-wider text-ink-subtle">
            Próximamente
          </p>
          <h3 className="font-display text-xl text-ink-muted">
            Más funciones admin
          </h3>
          <p className="mt-2 text-sm text-ink-subtle">
            Listado y gestión del catálogo, importación masiva, auditoría
            y revisión humana llegan en próximos sprints.
          </p>
        </div>
      </div>
    </section>
  );
}

function PanelSubmitter() {
  return (
    <section className="rounded-card border border-ink/10 bg-cream p-8 text-center">
      <h2 className="font-display text-3xl tracking-tight-display text-ink">
        Tu cuenta está lista.
      </h2>
      <p className="mx-auto mt-3 max-w-md text-ink-muted">
        La funcionalidad para subir y evaluar tus cartas se habilita en
        próximos sprints. Te avisaremos en cuanto esté disponible.
      </p>
    </section>
  );
}
