import { RegistroForm } from "@/usuarios/componentes/RegistroForm";
import { Link } from "react-router-dom";

/**
 * Página de registro.
 *
 * Layout editorial: dos columnas en desktop (brand a la izquierda, formulario
 * a la derecha), una columna apilada en mobile. La columna izquierda establece
 * tono y confianza antes de pedir datos.
 */
export function RegistroPagina() {
  return (
    <div className="min-h-screen bg-paper">
      <div className="mx-auto grid min-h-screen max-w-7xl grid-cols-1 lg:grid-cols-5">
        {/* Columna brand / hero */}
        <aside className="relative flex flex-col justify-between p-8 lg:col-span-2 lg:p-14">
          <header>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-holo">
              PokéGrading
            </p>
          </header>

          <div className="my-12 lg:my-0">
            <h1 className="font-display text-5xl leading-[0.95] tracking-tight-display text-ink lg:text-7xl">
              Una <em className="not-italic text-holo">opinión informada</em>{" "}
              antes de grabar tus cartas.
            </h1>
            <p className="mt-6 max-w-md text-lg leading-relaxed text-ink-muted">
              Sube fotos, recibe una estimación de grado con visión por
              computadora y decide si vale la pena enviar tu carta a PSA, BGS o
              CGC. <span className="text-ink">Sin esperas de 4 a 12 semanas.</span>
            </p>
          </div>

          <footer className="hidden text-xs text-ink-subtle lg:block">
            Construido por PokeVault S.R.L. · Costa Rica
          </footer>
        </aside>

        {/* Columna formulario */}
        <section className="flex items-center justify-center bg-cream p-8 lg:col-span-3 lg:p-14">
          <div className="w-full max-w-md">
            <header className="mb-10">
              <h2 className="font-display text-3xl tracking-tight-display text-ink">
                Crea tu cuenta
              </h2>
              <p className="mt-2 text-sm text-ink-muted">
                Empieza con 3 evaluaciones gratis al mes.
              </p>
            </header>

            <RegistroForm />

            <p className="mt-8 text-sm text-ink-subtle">
              ¿Ya tienes cuenta?{" "}
              <Link to="/login" className="font-medium text-holo underline decoration-holo/30 underline-offset-4 hover:decoration-holo">
                Inicia sesión
              </Link>
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
