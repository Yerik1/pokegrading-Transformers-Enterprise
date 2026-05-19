import { cliente } from "@/compartido/api/cliente";
import type {
  Acabado,
  Carta,
  Edicion,
  IdiomaCarta,
  Rareza,
  TipoPokemon,
} from "@/catalogo/tipos/carta";

/** Payload del JSON que va en el campo `datos` del multipart. */
export interface DatosCarta {
  // Identity tuple (requerido)
  set_codigo: string;
  numero: string;
  edicion: Edicion;
  idioma: IdiomaCarta;
  acabado: Acabado;
  // Display (opcional)
  nombre: string | null;
  rareza: Rareza | null;
  tipo: TipoPokemon | null;
  hp: number | null;
  ilustrador: string | null;
  anio_impresion: number | null;
}

/**
 * Crea una carta nueva en el catálogo.
 *
 * Hace un POST multipart con tres campos:
 * - `datos`: JSON serializado con los atributos de la carta.
 * - `imagen_frente`: archivo (requerido).
 * - `imagen_reverso`: archivo (opcional).
 *
 * Axios detecta automáticamente que el body es `FormData` y setea el
 * `Content-Type: multipart/form-data` con el boundary correcto. NO se
 * debe setear manualmente o se rompe el boundary.
 */
export async function agregarCarta(
  datos: DatosCarta,
  imagenFrente: File,
  imagenReverso: File | null
): Promise<Carta> {
  const formData = new FormData();
  formData.append("datos", JSON.stringify(datos));
  formData.append("imagen_frente", imagenFrente);
  if (imagenReverso) {
    formData.append("imagen_reverso", imagenReverso);
  }

  const { data } = await cliente.post<Carta>(
    "/api/v1/catalogo/cartas",
    formData
  );
  return data;
}
