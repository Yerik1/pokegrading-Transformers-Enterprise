import { cliente } from "@/compartido/api/cliente";

export interface EnviarCartaResponse {
  identificador_evaluacion: string;
  estado: string;
  iq_score_frente: number;
  iq_score_reverso: number;
  mensaje: string;
  tiempo_estimado_segundos: number | null;
  created_at: string;
}

export interface CandidatoResponse {
  carta_id: string;
  set_codigo: string;
  numero: string;
  nombre: string | null;
  confianza: number;
  aceptado_automaticamente: boolean;
}

export interface BusquedaRapidaResponse {
  candidatos: CandidatoResponse[];
  escala_a_especializada: boolean;
  deriva_a_manual: boolean;
  umbral_usado: number;
}

export async function enviarCartaApi(
  imagenFrente: File,
  imagenReverso: File
): Promise<EnviarCartaResponse> {
  const form = new FormData();
  form.append("imagen_frente", imagenFrente);
  form.append("imagen_reverso", imagenReverso);
  const res = await cliente.post<EnviarCartaResponse>(
    "/api/v1/evaluaciones/enviar",
    form,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return res.data;
}

export async function busquedaRapidaApi(
  imagenFrente: File
): Promise<BusquedaRapidaResponse> {
  const form = new FormData();
  form.append("imagen_frente", imagenFrente);
  const res = await cliente.post<BusquedaRapidaResponse>(
    "/api/v1/identificacion/busqueda-rapida",
    form,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return res.data;
}
