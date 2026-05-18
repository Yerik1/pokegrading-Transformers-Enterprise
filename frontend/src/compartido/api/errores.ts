/**
 * Tipos y clase de error de dominio.
 *
 * El backend siempre devuelve errores con el shape:
 * ```
 * { error: "codigo_snake_case", mensaje: "Texto legible", campo?: "campo_afectado", correlation_id?: "..." }
 * ```
 *
 * Aquí los modelamos como una clase JS para que se puedan `throw` desde el
 * cliente y capturarse con `instanceof` en los componentes.
 */

export interface ErrorDominioPayload {
  error: string;
  mensaje: string;
  campo?: string;
  correlation_id?: string;
}

export class ErrorDominio extends Error {
  readonly codigo: string;
  readonly campo: string | undefined;
  readonly correlationId: string | undefined;
  readonly statusHttp: number;

  constructor(payload: ErrorDominioPayload, statusHttp: number) {
    super(payload.mensaje);
    this.name = "ErrorDominio";
    this.codigo = payload.error;
    this.campo = payload.campo;
    this.correlationId = payload.correlation_id;
    this.statusHttp = statusHttp;
  }
}

/** Error que indica que el backend no respondió o respondió algo no parseable. */
export class ErrorRed extends Error {
  constructor(mensaje: string = "No fue posible contactar al servidor.") {
    super(mensaje);
    this.name = "ErrorRed";
  }
}
