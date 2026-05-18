import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { Tokens, Usuario } from "@/compartido/tipos/usuario";

/**
 * Estado de autenticación global.
 *
 * Persiste en `localStorage` bajo la clave `pokegrading-auth` para que la
 * sesión sobreviva refreshes. El interceptor de axios lee directamente
 * desde ahí — ver `cliente.ts`.
 *
 * Decisión: `localStorage` vs cookie HttpOnly.
 * - `localStorage` es vulnerable a XSS. Mitigamos con CSP estricto y
 *   sanitización de cualquier contenido renderizado desde el backend.
 * - Cookie HttpOnly sería más segura pero requiere setup de same-site,
 *   CSRF tokens y un endpoint de refresh dedicado. Diferido a sprint
 *   posterior cuando el catálogo introduzca operaciones autenticadas críticas.
 */

interface EstadoAuth {
  usuario: Usuario | null;
  tokens: Tokens | null;
  iniciarSesion: (usuario: Usuario, tokens: Tokens) => void;
  cerrarSesion: () => void;
  estaAutenticado: () => boolean;
}

export const useAuthStore = create<EstadoAuth>()(
  persist(
    (set, get) => ({
      usuario: null,
      tokens: null,

      iniciarSesion: (usuario, tokens) => set({ usuario, tokens }),

      cerrarSesion: () => set({ usuario: null, tokens: null }),

      estaAutenticado: () => get().tokens !== null,
    }),
    {
      name: "pokegrading-auth",
      storage: createJSONStorage(() => localStorage),
      // Persistimos solo lo serializable; los métodos se rehidratan vacíos.
      partialize: (state) => ({
        usuario: state.usuario,
        tokens: state.tokens,
      }),
    }
  )
);
