import { cliente } from "@/compartido/api/cliente";
import type { Tokens, Usuario } from "@/compartido/tipos/usuario";

export interface LoginRequest {
  correo: string;
  contrasena: string;
}

export interface LoginResponse {
  usuario: Usuario;
  tokens: Tokens;
}

export interface RefreshResponse {
  tokens: Tokens;
}

/**
 * Login del usuario contra `POST /api/v1/auth/login`.
 *
 * @throws ErrorDominio con código `credenciales_invalidas` si correo o
 *   contraseña son incorrectos (mismo mensaje genérico — defensa contra
 *   enumeración de cuentas).
 */
export async function iniciarSesion(
  payload: LoginRequest
): Promise<LoginResponse> {
  const { data } = await cliente.post<LoginResponse>(
    "/api/v1/auth/login",
    payload
  );
  return data;
}

/**
 * Renueva el par de tokens usando un refresh token válido.
 *
 * Cada llamada rota el refresh: el anterior queda igualmente válido hasta
 * que expire por TTL, pero el cliente debe descartarlo y usar el nuevo.
 */
export async function refrescarTokens(
  refreshToken: string
): Promise<RefreshResponse> {
  const { data } = await cliente.post<RefreshResponse>("/api/v1/auth/refresh", {
    refresh_token: refreshToken,
  });
  return data;
}
