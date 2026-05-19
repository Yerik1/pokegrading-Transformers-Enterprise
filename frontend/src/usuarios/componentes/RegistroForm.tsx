import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorDominio, ErrorRed } from "@/compartido/api/errores";
import { useAuthStore } from "@/compartido/auth/auth-store";
import {
  PAISES,
  type Idioma,
  type Pais,
} from "@/compartido/tipos/usuario";
import { registrar } from "@/usuarios/api/registro-api";

/**
 * Estado controlado del formulario.
 *
 * Mantengo `pais` como `Pais | ""` para soportar el estado inicial "sin
 * seleccionar" sin tener que defaultear a un país arbitrario.
 */
interface EstadoFormulario {
  correo: string;
  alias: string;
  contrasena: string;
  pais: Pais | "";
  idioma_preferido: Idioma;
  disclosure_aceptado: boolean;
}

const ESTADO_INICIAL: EstadoFormulario = {
  correo: "",
  alias: "",
  contrasena: "",
  pais: "",
  idioma_preferido: "es",
  disclosure_aceptado: false,
};

/**
 * Mapea el `campo` que devuelve el backend al `key` del estado del form.
 * El backend usa los mismos nombres que el contrato, así que casi es 1:1.
 */
type CamposError = Partial<Record<keyof EstadoFormulario | "general", string>>;

export function RegistroForm() {
  const [form, setForm] = useState<EstadoFormulario>(ESTADO_INICIAL);
  const [errores, setErrores] = useState<CamposError>({});
  const [enviando, setEnviando] = useState(false);
  const iniciarSesion = useAuthStore((s) => s.iniciarSesion);
  const navegar = useNavigate();

  function actualizar<K extends keyof EstadoFormulario>(
    campo: K,
    valor: EstadoFormulario[K]
  ) {
    setForm((prev) => ({ ...prev, [campo]: valor }));
    // Al editar un campo, limpio su error específico (UX)
    if (errores[campo]) {
      setErrores((prev) => {
        const { [campo]: _omitir, ...resto } = prev;
        return resto;
      });
    }
  }

  async function manejarSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErrores({});

    if (form.pais === "") {
      setErrores({ pais: "Selecciona tu país de residencia." });
      return;
    }

    setEnviando(true);
    try {
      const resp = await registrar({
        correo: form.correo.trim(),
        alias: form.alias.trim(),
        contrasena: form.contrasena,
        pais: form.pais,
        idioma_preferido: form.idioma_preferido,
        disclosure_aceptado: form.disclosure_aceptado,
      });
      iniciarSesion(resp.usuario, resp.tokens);
      navegar("/inicio", { replace: true });
    } catch (err) {
      if (err instanceof ErrorDominio) {
        const campo = (err.campo ?? "general") as keyof CamposError;
        setErrores({ [campo]: err.mensaje });
      } else if (err instanceof ErrorRed) {
        setErrores({ general: err.message });
      } else {
        setErrores({ general: "Ocurrió un error inesperado." });
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={manejarSubmit} noValidate className="space-y-7">
      {errores.general && (
        <div
          role="alert"
          className="rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
        >
          {errores.general}
        </div>
      )}

      <Campo
        id="correo"
        etiqueta="Correo electrónico"
        type="email"
        autoComplete="email"
        required
        value={form.correo}
        onChange={(v) => actualizar("correo", v)}
        error={errores.correo}
      />

      <Campo
        id="alias"
        etiqueta="Alias visible"
        ayuda="Es el nombre que verán otros usuarios en la plataforma."
        type="text"
        autoComplete="nickname"
        minLength={3}
        maxLength={50}
        required
        value={form.alias}
        onChange={(v) => actualizar("alias", v)}
        error={errores.alias}
      />

      <Campo
        id="contrasena"
        etiqueta="Contraseña"
        ayuda="Mínimo 10 caracteres, una mayúscula y un dígito."
        type="password"
        autoComplete="new-password"
        required
        value={form.contrasena}
        onChange={(v) => actualizar("contrasena", v)}
        error={errores.contrasena}
      />

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div>
          <label
            htmlFor="pais"
            className="mb-1.5 block text-sm font-medium text-ink"
          >
            País de residencia
          </label>
          <select
            id="pais"
            value={form.pais}
            onChange={(e) => actualizar("pais", e.target.value as Pais | "")}
            required
            className={[
              "w-full rounded-card border bg-cream px-4 py-2.5 text-ink",
              "transition-colors",
              errores.pais
                ? "border-danger focus:border-danger"
                : "border-ink/15 focus:border-holo",
            ].join(" ")}
          >
            <option value="" disabled>
              Selecciona…
            </option>
            {PAISES.map((p) => (
              <option key={p.codigo} value={p.codigo}>
                {p.nombre}
              </option>
            ))}
          </select>
          {errores.pais && (
            <p className="mt-1.5 text-sm text-danger">{errores.pais}</p>
          )}
        </div>

        <div>
          <label
            htmlFor="idioma"
            className="mb-1.5 block text-sm font-medium text-ink"
          >
            Idioma preferido
          </label>
          <select
            id="idioma"
            value={form.idioma_preferido}
            onChange={(e) =>
              actualizar("idioma_preferido", e.target.value as Idioma)
            }
            className="w-full rounded-card border border-ink/15 bg-cream px-4 py-2.5 text-ink transition-colors focus:border-holo"
          >
            <option value="es">Español</option>
            <option value="en">English</option>
          </select>
        </div>
      </div>

      {/* Disclosure — sección destacada porque es legalmente significativo (CR-03, U9) */}
      <div className="rounded-card border border-ink/10 bg-cream-dark/40 p-5">
        <label className="flex cursor-pointer items-start gap-3">
          <input
            type="checkbox"
            checked={form.disclosure_aceptado}
            onChange={(e) =>
              actualizar("disclosure_aceptado", e.target.checked)
            }
            className="mt-1 h-4 w-4 cursor-pointer accent-holo"
          />
          <span className="text-sm leading-relaxed text-ink-muted">
            Entiendo que PokéGrading es una herramienta{" "}
            <strong className="text-ink">informativa</strong> y{" "}
            <strong className="text-ink">no sustituye</strong> la certificación
            oficial de PSA, BGS ni CGC. Las evaluaciones son orientativas y no
            tienen valor legal ni de garantía.
          </span>
        </label>
        {errores.disclosure_aceptado && (
          <p className="mt-2 text-sm text-danger">
            {errores.disclosure_aceptado}
          </p>
        )}
      </div>

      <button
        type="submit"
        disabled={enviando}
        className={[
          "group relative w-full overflow-hidden rounded-card",
          "bg-ink px-6 py-3.5 text-base font-medium text-cream",
          "transition-all hover:bg-ink/90",
          "disabled:cursor-not-allowed disabled:opacity-60",
          "focus-visible:ring-offset-cream",
        ].join(" ")}
      >
        <span className="relative z-10">
          {enviando ? "Creando cuenta…" : "Crear cuenta"}
        </span>
      </button>
    </form>
  );
}

// ============================================================================
// Subcomponentes
// ============================================================================

interface CampoProps {
  id: string;
  etiqueta: string;
  ayuda?: string;
  type: "text" | "email" | "password";
  value: string;
  onChange: (valor: string) => void;
  error?: string;
  required?: boolean;
  autoComplete?: string;
  minLength?: number;
  maxLength?: number;
}

function Campo({
  id,
  etiqueta,
  ayuda,
  type,
  value,
  onChange,
  error,
  required,
  autoComplete,
  minLength,
  maxLength,
}: CampoProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-sm font-medium text-ink"
      >
        {etiqueta}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        autoComplete={autoComplete}
        minLength={minLength}
        maxLength={maxLength}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : ayuda ? `${id}-ayuda` : undefined}
        className={[
          "w-full rounded-card border bg-cream px-4 py-2.5 text-ink",
          "placeholder:text-ink-subtle/60 transition-colors",
          error
            ? "border-danger focus:border-danger"
            : "border-ink/15 focus:border-holo",
        ].join(" ")}
      />
      {ayuda && !error && (
        <p id={`${id}-ayuda`} className="mt-1.5 text-sm text-ink-subtle">
          {ayuda}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
