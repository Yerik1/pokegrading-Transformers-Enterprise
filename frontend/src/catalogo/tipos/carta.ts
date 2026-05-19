/**
 * Tipos del dominio de catálogo.
 *
 * Espejo de los enums en `backend/src/pokegrading/catalogo/tipos.py`.
 * Si cambian acá, cambian allá también (y viceversa).
 */

export type Edicion = "1st_edition" | "unlimited" | "shadowless";

export type Acabado = "holo" | "reverse_holo" | "full_art" | "non_holo";

export type Rareza =
  | "common"
  | "uncommon"
  | "rare"
  | "holo_rare"
  | "ultra_rare"
  | "secret_rare";

export type TipoPokemon =
  | "grass"
  | "fire"
  | "water"
  | "lightning"
  | "psychic"
  | "fighting"
  | "darkness"
  | "metal"
  | "fairy"
  | "dragon"
  | "colorless";

export type IdiomaCarta =
  | "EN"
  | "JP"
  | "ES"
  | "DE"
  | "FR"
  | "IT"
  | "KR"
  | "ZH_T";

// === Listas con etiquetas legibles para los selects del form ===

export const EDICIONES: { valor: Edicion; etiqueta: string }[] = [
  { valor: "1st_edition", etiqueta: "1st Edition" },
  { valor: "unlimited", etiqueta: "Unlimited" },
  { valor: "shadowless", etiqueta: "Shadowless" },
];

export const ACABADOS: { valor: Acabado; etiqueta: string }[] = [
  { valor: "holo", etiqueta: "Holo" },
  { valor: "reverse_holo", etiqueta: "Reverse Holo" },
  { valor: "full_art", etiqueta: "Full Art" },
  { valor: "non_holo", etiqueta: "Non-Holo" },
];

export const RAREZAS: { valor: Rareza; etiqueta: string }[] = [
  { valor: "common", etiqueta: "Common" },
  { valor: "uncommon", etiqueta: "Uncommon" },
  { valor: "rare", etiqueta: "Rare" },
  { valor: "holo_rare", etiqueta: "Holo Rare" },
  { valor: "ultra_rare", etiqueta: "Ultra Rare" },
  { valor: "secret_rare", etiqueta: "Secret Rare" },
];

export const TIPOS_POKEMON: { valor: TipoPokemon; etiqueta: string }[] = [
  { valor: "grass", etiqueta: "Grass" },
  { valor: "fire", etiqueta: "Fire" },
  { valor: "water", etiqueta: "Water" },
  { valor: "lightning", etiqueta: "Lightning" },
  { valor: "psychic", etiqueta: "Psychic" },
  { valor: "fighting", etiqueta: "Fighting" },
  { valor: "darkness", etiqueta: "Darkness" },
  { valor: "metal", etiqueta: "Metal" },
  { valor: "fairy", etiqueta: "Fairy" },
  { valor: "dragon", etiqueta: "Dragon" },
  { valor: "colorless", etiqueta: "Colorless" },
];

export const IDIOMAS_CARTA: { valor: IdiomaCarta; etiqueta: string }[] = [
  { valor: "EN", etiqueta: "Inglés" },
  { valor: "JP", etiqueta: "Japonés" },
  { valor: "ES", etiqueta: "Español" },
  { valor: "DE", etiqueta: "Alemán" },
  { valor: "FR", etiqueta: "Francés" },
  { valor: "IT", etiqueta: "Italiano" },
  { valor: "KR", etiqueta: "Coreano" },
  { valor: "ZH_T", etiqueta: "Chino tradicional" },
];

// === Representación de una carta (matchea CartaResponse del backend) ===

export interface Carta {
  id: string;
  set_codigo: string;
  numero: string;
  edicion: Edicion;
  idioma: IdiomaCarta;
  acabado: Acabado;
  nombre: string | null;
  rareza: Rareza | null;
  tipo: TipoPokemon | null;
  hp: number | null;
  ilustrador: string | null;
  anio_impresion: number | null;
  url_imagen_frente: string;
  url_imagen_reverso: string | null;
  creada_por_id: string;
  created_at: string;
}
