import { Link, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/compartido/auth/auth-store";

/**
 * Header de aplicación para páginas autenticadas.
 *
 * Muestra el branding, el alias + rol del usuario y un botón de logout.
 * Es un esqueleto mínimo — cuando agreguemos más rutas admin
 * (catálogo, usuarios, etc.) acá vivirá la navegación principal.
 */
export function HeaderApp() {
  const usuario = useAuthStore((s) => s.usuario);
  const cerrarSesion = useAuthStore((s) => s.cerrarSesion);
  const navegar = useNavigate();

  const onLogout = () => {
    cerrarSesion();
    navegar("/login", { replace: true });
  };

  return (
    <header className="border-b border-ink/10 bg-cream">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-10">
        <Link
          to="/inicio"
          className="text-xs font-medium uppercase tracking-[0.18em] text-holo"
        >
          PokéGrading
        </Link>

        {usuario && (
          <div className="flex items-center gap-4">
            <div className="hidden text-right text-sm sm:block">
              <p className="text-ink">{usuario.alias}</p>
              <p className="text-xs uppercase tracking-wider text-ink-subtle">
                {usuario.rol}
              </p>
            </div>
            <button
              type="button"
              onClick={onLogout}
              className="rounded-card border border-ink/15 px-4 py-2 text-sm text-ink-muted transition-colors hover:border-ink/40 hover:text-ink"
            >
              Cerrar sesión
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
