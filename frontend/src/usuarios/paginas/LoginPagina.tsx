import { Link } from "react-router-dom";
import { LoginForm } from "@/usuarios/componentes/LoginForm";

/**
 * Página de login.
 *
 * Mismo layout editorial que `RegistroPagina` para mantener consistencia
 * de marca, pero con copy distinto.
 */
export function LoginPagina() {
  return (
    <div className="min-h-screen bg-paper">
      <div className="mx-auto grid min-h-screen max-w-7xl grid-cols-1 lg:grid-cols-5">
        <aside className="relative flex flex-col justify-between p-8 lg:col-span-2 lg:p-14">
          <header>
            <Link
              to="/"
              className="text-xs font-medium uppercase tracking-[0.18em] text-holo"
            >
              PokéGrading
            </Link>
          </header>

          <div className="my-12 lg:my-0">
            <h1 className="font-display text-5xl leading-[0.95] tracking-tight-display text-ink lg:text-7xl">
              Bienvenido de vuelta.
            </h1>
            <p className="mt-6 max-w-md text-lg leading-relaxed text-ink-muted">
              Accede a tu cuenta para revisar evaluaciones, agregar cartas
              al catálogo o continuar donde lo dejaste.
            </p>
          </div>

          <footer className="hidden text-xs text-ink-subtle lg:block">
            Construido por PokeVault S.R.L. · Costa Rica
          </footer>
        </aside>

        <section className="flex items-center justify-center bg-cream p-8 lg:col-span-3 lg:p-14">
          <div className="w-full max-w-md">
            <header className="mb-10">
              <h2 className="font-display text-3xl tracking-tight-display text-ink">
                Inicia sesión
              </h2>
              <p className="mt-2 text-sm text-ink-muted">
                Usa el correo y contraseña con los que te registraste.
              </p>
            </header>

            <LoginForm />

            <p className="mt-8 text-sm text-ink-subtle">
              ¿Aún no tienes cuenta?{" "}
              <Link
                to="/registro"
                className="font-medium text-holo underline decoration-holo/30 underline-offset-4 hover:decoration-holo"
              >
                Regístrate
              </Link>
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
