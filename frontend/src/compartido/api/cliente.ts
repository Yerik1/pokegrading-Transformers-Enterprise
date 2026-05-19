import axios, { AxiosError, type AxiosInstance } from "axios";
import { ErrorDominio, ErrorRed, type ErrorDominioPayload } from "./errores";

/**
 * Genera un UUID v4 para el correlation ID.
 *
 * Usa `crypto.randomUUID()` disponible nativamente en navegadores modernos
 * (Chrome 92+, Firefox 95+, Safari 15.4+).
 */
function generarCorrelationId(): string {
  return crypto.randomUUID();
}

/**
 * Cliente HTTP para el backend de PokéGrading.
 *
 * Configurado con:
 * - `baseURL` vacía (usa el proxy de Vite que reenvía `/api/*` al backend)
 * - Header `X-Correlation-Id` único por request (S2, DA-06)
 * - Inyección automática del access token cuando hay sesión
 * - Normalización de errores al shape `ErrorDominio` definido por el backend
 */
export const cliente: AxiosInstance = axios.create({
  baseURL: "",
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
  timeout: 10_000,
});

// === Request interceptor: correlation ID + auth token ===
cliente.interceptors.request.use((config) => {
  config.headers.set("X-Correlation-Id", generarCorrelationId());

  // El token vive en localStorage gracias al middleware persist de Zustand.
  // Lo leemos directo aquí para evitar dependencia circular con el store.
  const raw = localStorage.getItem("pokegrading-auth");
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as {
        state?: { tokens?: { access_token?: string } };
      };
      const token = parsed.state?.tokens?.access_token;
      if (token) {
        config.headers.set("Authorization", `Bearer ${token}`);
      }
    } catch {
      // localStorage corrupto, ignoramos y seguimos sin auth.
    }
  }
  return config;
});

// === Response interceptor: normalización de errores ===
cliente.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ErrorDominioPayload>) => {
    // Sin respuesta = problema de red / timeout / CORS
    if (!error.response) {
      return Promise.reject(new ErrorRed(error.message));
    }

    const { data, status } = error.response;

    // Si el backend devolvió nuestro shape esperado, lo levantamos tipado.
    if (data && typeof data === "object" && "error" in data && "mensaje" in data) {
      return Promise.reject(new ErrorDominio(data, status));
    }

    // Fallback: error HTTP sin shape de dominio (ej. 500 puro)
    return Promise.reject(
      new ErrorDominio(
        {
          error: "error_inesperado",
          mensaje: `Error del servidor (HTTP ${status}).`,
        },
        status
      )
    );
  }
);

// === Interceptor: FormData ===
// Cuando el body es FormData, axios necesita setear `Content-Type:
// multipart/form-data; boundary=...` con un boundary autogenerado.
// Si dejamos el default `application/json` activo, el browser/axios no
// inyecta el boundary y el backend recibe un body inutilizable.
// Solución: eliminamos el Content-Type para que axios lo deduzca solo.
cliente.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    if (config.headers) {
      delete config.headers["Content-Type"];
    }
  }
  return config;
});
