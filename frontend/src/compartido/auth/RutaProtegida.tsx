import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "@/compartido/auth/auth-store";
import type { Rol } from "@/compartido/tipos/usuario";

interface RutaProtegidaProps {
  children: ReactNode;
  /** Si se pasa, solo usuarios con uno de estos roles pueden entrar. */
  roles?: Rol[];
}

/**
 * Wrapper de rutas que requieren autenticación.
 *
 * Comportamiento:
 * - Sin sesión → redirige a `/login` con `state.from` para volver después.
 * - Con sesión pero rol incorrecto → muestra mensaje de acceso denegado.
 * - Con sesión y rol válido (o sin restricción) → renderiza el hijo.
 */
export function RutaProtegida({ children, roles }: RutaProtegidaProps) {
  const usuario = useAuthStore((s) => s.usuario);
  const tokens = useAuthStore((s) => s.tokens);
  const location = useLocation();

  if (!usuario || !tokens) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (roles && !roles.includes(usuario.rol)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper px-6">
        <div className="max-w-md space-y-3 text-center">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-danger">
            Acceso denegado
          </p>
          <h1 className="font-display text-4xl tracking-tight-display text-ink">
            No tienes permiso para ver esta página.
          </h1>
          <p className="text-ink-muted">
            Tu rol actual es{" "}
            <code className="rounded bg-cream-dark/60 px-1.5 py-0.5 font-mono text-sm">
              {usuario.rol}
            </code>
            . Esta sección requiere uno de: {roles.join(", ")}.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
