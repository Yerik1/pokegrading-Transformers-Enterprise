/**
 * Tipos del dominio compartidos con el backend.
 *
 * Estos tipos deben mantenerse sincronizados con los enums de
 * `backend/src/pokegrading/usuarios/tipos.py`. Si cambia uno, cambia el otro.
 */

export type Pais = "CR" | "PA" | "MX" | "CO" | "CL" | "AR";

export type Idioma = "es" | "en";

export type Rol =
  | "submitter"
  | "reviewer"
  | "admin"
  | "superadmin"
  | "b2b_service_account";

/** Listado de países atendidos con su nombre legible para el selector. */
export const PAISES: { codigo: Pais; nombre: string }[] = [
  { codigo: "CR", nombre: "Costa Rica" },
  { codigo: "PA", nombre: "Panamá" },
  { codigo: "MX", nombre: "México" },
  { codigo: "CO", nombre: "Colombia" },
  { codigo: "CL", nombre: "Chile" },
  { codigo: "AR", nombre: "Argentina" },
];

/** Representación pública de un usuario (matchea `UsuarioResponse` del backend). */
export interface Usuario {
  id: string;
  correo: string;
  alias: string;
  pais: Pais;
  idioma_preferido: Idioma;
  rol: Rol;
  created_at: string;
}

/** Par de tokens entregados tras registro/login. */
export interface Tokens {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}
