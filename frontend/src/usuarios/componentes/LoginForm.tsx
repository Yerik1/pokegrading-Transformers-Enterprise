import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ErrorDominio, ErrorRed } from "@/compartido/api/errores";
import { useAuthStore } from "@/compartido/auth/auth-store";
import { iniciarSesion } from "@/usuarios/api/login-api";

interface EstadoFormulario {
  correo: string;
  contrasena: string;
}

const ESTADO_INICIAL: EstadoFormulario = {
  correo: "",
  contrasena: "",
};

interface LocationState {
  from?: string;
}

export function LoginForm() {
  const [form, setForm] = useState<EstadoFormulario>(ESTADO_INICIAL);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const setSesion = useAuthStore((s) => s.iniciarSesion);
  const navegar = useNavigate();
  const location = useLocation();

  function actualizar<K extends keyof EstadoFormulario>(
    campo: K,
    valor: EstadoFormulario[K]
  ) {
    setForm((prev) => ({ ...prev, [campo]: valor }));
    if (error) setError(null);
  }

  async function manejarSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setEnviando(true);

    try {
      const resp = await iniciarSesion({
        correo: form.correo.trim().toLowerCase(),
        contrasena: form.contrasena,
      });
      setSesion(resp.usuario, resp.tokens);

      // Volver a la ruta original si el usuario fue redirigido aquí desde
      // una ruta protegida; si no, ir al inicio.
      const state = location.state as LocationState | null;
      const destino = state?.from ?? "/inicio";
      navegar(destino, { replace: true });
    } catch (err) {
      if (err instanceof ErrorDominio) {
        setError(err.mensaje);
      } else if (err instanceof ErrorRed) {
        setError(err.message);
      } else {
        setError("Ocurrió un error inesperado.");
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={manejarSubmit} noValidate className="space-y-6">
      {error && (
        <div
          role="alert"
          className="rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
        >
          {error}
        </div>
      )}

      <div>
        <label
          htmlFor="correo"
          className="mb-1.5 block text-sm font-medium text-ink"
        >
          Correo electrónico
        </label>
        <input
          id="correo"
          type="email"
          autoComplete="email"
          required
          value={form.correo}
          onChange={(e) => actualizar("correo", e.target.value)}
          className="w-full rounded-card border border-ink/15 bg-cream px-4 py-2.5 text-ink transition-colors placeholder:text-ink-subtle/60 focus:border-holo"
        />
      </div>

      <div>
        <label
          htmlFor="contrasena"
          className="mb-1.5 block text-sm font-medium text-ink"
        >
          Contraseña
        </label>
        <input
          id="contrasena"
          type="password"
          autoComplete="current-password"
          required
          value={form.contrasena}
          onChange={(e) => actualizar("contrasena", e.target.value)}
          className="w-full rounded-card border border-ink/15 bg-cream px-4 py-2.5 text-ink transition-colors placeholder:text-ink-subtle/60 focus:border-holo"
        />
      </div>

      <button
        type="submit"
        disabled={enviando}
        className="w-full rounded-card bg-ink px-6 py-3.5 text-base font-medium text-cream transition-all hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {enviando ? "Iniciando sesión…" : "Iniciar sesión"}
      </button>
    </form>
  );
}
