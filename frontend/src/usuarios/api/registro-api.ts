import { cliente } from "@/compartido/api/cliente";
import type { Idioma, Pais, Tokens, Usuario } from "@/compartido/tipos/usuario";

/** Payload exacto que espera `POST /api/v1/usuarios/registro`. */
export interface RegistroRequest {
  correo: string;
  alias: string;
  contrasena: string;
  pais: Pais;
  idioma_preferido: Idioma;
  disclosure_aceptado: boolean;
}

/** Respuesta del endpoint cuando el registro es exitoso. */
export interface RegistroResponse {
  usuario: Usuario;
  tokens: Tokens;
}

/**
 * Llama al endpoint de registro de cuenta.
 *
 * Las validaciones de campo (password rules, país soportado, etc.) las hace
 * el backend y devuelve `ErrorDominio` con `campo` específico, que el
 * formulario muestra junto al input correspondiente.
 *
 * @param payload datos del formulario validados a nivel cliente
 * @returns usuario creado + par de tokens iniciales
 * @throws ErrorDominio si alguna validación del backend falla (422, 409, ...)
 * @throws ErrorRed si no se pudo contactar al backend
 */
export async function registrar(
  payload: RegistroRequest
): Promise<RegistroResponse> {
  const { data } = await cliente.post<RegistroResponse>(
    "/api/v1/usuarios/registro",
    payload
  );
  return data;
}
