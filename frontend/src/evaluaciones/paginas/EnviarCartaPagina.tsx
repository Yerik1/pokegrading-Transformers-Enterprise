import { useState } from "react";
import { HeaderApp } from "@/compartido/layout/HeaderApp";
import {
  enviarCartaApi,
  busquedaRapidaApi,
  type EnviarCartaResponse,
  type BusquedaRapidaResponse,
} from "@/evaluaciones/api/evaluaciones-api";

type Paso = "captura" | "identificando" | "identificado" | "enviando" | "resultado" | "error";

export function EnviarCartaPagina() {
  const [paso, setPaso] = useState<Paso>("captura");
  const [imagenFrente, setImagenFrente] = useState<File | null>(null);
  const [imagenReverso, setImagenReverso] = useState<File | null>(null);
  const [prevFrente, setPrevFrente] = useState<string | null>(null);
  const [prevReverso, setPrevReverso] = useState<string | null>(null);
  const [busqueda, setBusqueda] = useState<BusquedaRapidaResponse | null>(null);
  const [resultado, setResultado] = useState<EnviarCartaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleImagenFrente(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImagenFrente(file);
    setPrevFrente(URL.createObjectURL(file));
  }

  function handleImagenReverso(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImagenReverso(file);
    setPrevReverso(URL.createObjectURL(file));
  }

  async function handleIdentificar() {
    if (!imagenFrente) return;
    setPaso("identificando");
    setError(null);
    try {
      const res = await busquedaRapidaApi(imagenFrente);
      setBusqueda(res);
      setPaso("identificado");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Error al identificar la carta.";
      setError(msg);
      setPaso("error");
    }
  }

  async function handleEnviar() {
    if (!imagenFrente || !imagenReverso) return;
    setPaso("enviando");
    setError(null);
    try {
      const res = await enviarCartaApi(imagenFrente, imagenReverso);
      setResultado(res);
      setPaso("resultado");
    } catch (e: unknown) {
      const mensajeError = extraerMensajeError(e);
      setError(mensajeError);
      setPaso("error");
    }
  }

  function handleReintentar() {
    setImagenFrente(null);
    setImagenReverso(null);
    setPrevFrente(null);
    setPrevReverso(null);
    setBusqueda(null);
    setResultado(null);
    setError(null);
    setPaso("captura");
  }

  return (
    <div className="min-h-screen bg-paper">
      <HeaderApp />
      <main className="mx-auto max-w-3xl px-6 py-16 lg:px-10">
        <header className="mb-10">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-holo">
            Evaluación
          </p>
          <h1 className="mt-2 font-display text-4xl tracking-tight-display text-ink">
            Enviar carta para evaluación
          </h1>
          <p className="mt-3 text-ink-muted">
            Subí las fotos del frente y reverso de tu carta. El sistema la
            identificará automáticamente y registrará tu solicitud.
          </p>
        </header>

        {paso === "captura" && (
          <PasoCaptura
            prevFrente={prevFrente}
            prevReverso={prevReverso}
            onFrente={handleImagenFrente}
            onReverso={handleImagenReverso}
            onContinuar={handleIdentificar}
            puedeIdentificar={!!imagenFrente}
            puedeEnviar={!!imagenFrente && !!imagenReverso}
            onEnviarDirecto={handleEnviar}
          />
        )}

        {paso === "identificando" && (
          <EstadoCargando mensaje="Identificando tu carta en el catálogo..." />
        )}

        {paso === "identificado" && busqueda && (
          <PasoIdentificado
            busqueda={busqueda}
            puedeEnviar={!!imagenReverso}
            onEnviar={handleEnviar}
            onVolver={() => setPaso("captura")}
          />
        )}

        {paso === "enviando" && (
          <EstadoCargando mensaje="Enviando tu carta para evaluación..." />
        )}

        {paso === "resultado" && resultado && (
          <PasoResultado resultado={resultado} onNuevaEvaluacion={handleReintentar} />
        )}

        {paso === "error" && (
          <PasoError mensaje={error ?? "Error desconocido."} onReintentar={handleReintentar} />
        )}
      </main>
    </div>
  );
}

function PasoCaptura({
  prevFrente,
  prevReverso,
  onFrente,
  onReverso,
  onContinuar,
  puedeIdentificar,
  puedeEnviar,
  onEnviarDirecto,
}: {
  prevFrente: string | null;
  prevReverso: string | null;
  onFrente: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onReverso: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onContinuar: () => void;
  puedeIdentificar: boolean;
  puedeEnviar: boolean;
  onEnviarDirecto: () => void;
}) {
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <SelectorImagen
          label="Frente de la carta *"
          preview={prevFrente}
          onChange={onFrente}
          id="frente"
        />
        <SelectorImagen
          label="Reverso de la carta *"
          preview={prevReverso}
          onChange={onReverso}
          id="reverso"
        />
      </div>

      <div className="rounded-card border border-ink/10 bg-cream p-4 text-sm text-ink-muted">
        <strong className="text-ink">Consejos para una buena foto:</strong> usá
        buena iluminación, fondo oscuro, encuadrá bien la carta y asegurate de
        que esté enfocada.
      </div>

      <div className="flex gap-4">
        <button
          onClick={onContinuar}
          disabled={!puedeIdentificar}
          className="rounded-card bg-holo px-6 py-3 font-medium text-white transition hover:opacity-90 disabled:opacity-40"
        >
          Identificar carta →
        </button>
        {puedeEnviar && (
          <button
            onClick={onEnviarDirecto}
            className="rounded-card border border-ink/20 px-6 py-3 font-medium text-ink transition hover:border-ink/40"
          >
            Enviar sin identificar
          </button>
        )}
      </div>
    </div>
  );
}

function SelectorImagen({
  label,
  preview,
  onChange,
  id,
}: {
  label: string;
  preview: string | null;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  id: string;
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-ink" htmlFor={id}>
        {label}
      </label>
      <label
        htmlFor={id}
        className="flex h-48 cursor-pointer flex-col items-center justify-center rounded-card border-2 border-dashed border-ink/20 bg-cream transition hover:border-holo"
      >
        {preview ? (
          <img
            src={preview}
            alt={label}
            className="h-full w-full rounded-card object-contain p-2"
          />
        ) : (
          <span className="text-sm text-ink-muted">Tocá para seleccionar</span>
        )}
        <input
          id={id}
          type="file"
          accept="image/jpeg,image/png"
          className="hidden"
          onChange={onChange}
        />
      </label>
    </div>
  );
}

function PasoIdentificado({
  busqueda,
  puedeEnviar,
  onEnviar,
  onVolver,
}: {
  busqueda: BusquedaRapidaResponse;
  puedeEnviar: boolean;
  onEnviar: () => void;
  onVolver: () => void;
}) {
  return (
    <div className="space-y-6">
      {busqueda.candidatos.length === 0 ? (
        <div className="rounded-card border border-ink/10 bg-cream p-6 text-center text-ink-muted">
          No se encontraron candidatos en el catálogo. La carta se enviará
          para identificación manual.
        </div>
      ) : (
        <div className="space-y-3">
          <h2 className="font-display text-xl text-ink">
            {(busqueda.candidatos[0]?.aceptado_automaticamente ?? false)
              ? "Carta identificada automáticamente"
              : "Candidatos encontrados"}
          </h2>
          {busqueda.candidatos.map((c, i) => (
            <div
              key={c.carta_id}
              className={`rounded-card border p-4 ${
                c.aceptado_automaticamente
                  ? "border-holo bg-cream"
                  : "border-ink/10 bg-cream-dark/20"
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-ink">
                    {c.nombre ?? "Carta sin nombre"}{" "}
                    {c.aceptado_automaticamente && (
                      <span className="ml-2 rounded-full bg-holo/10 px-2 py-0.5 text-xs text-holo">
                        Aceptada
                      </span>
                    )}
                  </p>
                  <p className="text-sm text-ink-muted">
                    {c.set_codigo} #{c.numero}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-ink">
                    {Math.round(c.confianza * 100)}% confianza
                  </p>
                  <p className="text-xs text-ink-subtle">candidato {i + 1}</p>
                </div>
              </div>
            </div>
          ))}
          {busqueda.escala_a_especializada && (
            <p className="text-sm text-ink-muted">
              Ningún candidato superó el umbral de confianza. Se escala a
              búsqueda especializada.
            </p>
          )}
        </div>
      )}

      <div className="flex gap-4">
        <button
          onClick={onEnviar}
          disabled={!puedeEnviar}
          className="rounded-card bg-holo px-6 py-3 font-medium text-white transition hover:opacity-90 disabled:opacity-40"
        >
          Confirmar y enviar →
        </button>
        <button
          onClick={onVolver}
          className="rounded-card border border-ink/20 px-6 py-3 font-medium text-ink transition hover:border-ink/40"
        >
          Volver
        </button>
      </div>
    </div>
  );
}

function PasoResultado({
  resultado,
  onNuevaEvaluacion,
}: {
  resultado: EnviarCartaResponse;
  onNuevaEvaluacion: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="rounded-card border border-holo/30 bg-cream p-8 text-center">
        <p className="text-xs font-medium uppercase tracking-wider text-holo">
          Evaluación registrada
        </p>
        <h2 className="mt-2 font-display text-3xl text-ink">
          {resultado.identificador_evaluacion}
        </h2>
        <p className="mt-3 text-ink-muted">{resultado.mensaje}</p>
        {resultado.tiempo_estimado_segundos && (
          <p className="mt-2 text-sm text-ink-subtle">
            Tiempo estimado: {resultado.tiempo_estimado_segundos} segundos
          </p>
        )}
        <div className="mt-6 grid grid-cols-2 gap-4 text-sm">
          <div className="rounded-card border border-ink/10 bg-cream-dark/20 p-3">
            <p className="text-ink-muted">Calidad frente</p>
            <p className="font-medium text-ink">
              {Math.round(resultado.iq_score_frente * 100)}%
            </p>
          </div>
          <div className="rounded-card border border-ink/10 bg-cream-dark/20 p-3">
            <p className="text-ink-muted">Calidad reverso</p>
            <p className="font-medium text-ink">
              {Math.round(resultado.iq_score_reverso * 100)}%
            </p>
          </div>
        </div>
      </div>
      <button
        onClick={onNuevaEvaluacion}
        className="rounded-card bg-holo px-6 py-3 font-medium text-white transition hover:opacity-90"
      >
        Evaluar otra carta →
      </button>
    </div>
  );
}

function EstadoCargando({ mensaje }: { mensaje: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="mb-4 h-8 w-8 animate-spin rounded-full border-4 border-holo border-t-transparent" />
      <p className="text-ink-muted">{mensaje}</p>
    </div>
  );
}

function PasoError({
  mensaje,
  onReintentar,
}: {
  mensaje: string;
  onReintentar: () => void;
}) {
  return (
    <div className="rounded-card border border-red-200 bg-red-50 p-8 text-center">
      <p className="font-medium text-red-700">Error</p>
      <p className="mt-2 text-sm text-red-600">{mensaje}</p>
      <button
        onClick={onReintentar}
        className="mt-6 rounded-card border border-red-300 px-6 py-3 text-sm font-medium text-red-700 transition hover:bg-red-100"
      >
        Intentar de nuevo
      </button>
    </div>
  );
}

function extraerMensajeError(e: unknown): string {
  if (e && typeof e === "object" && "response" in e) {
    const resp = (e as { response?: { data?: { mensaje?: string } } }).response;
    if (resp?.data?.mensaje) return resp.data.mensaje;
  }
  if (e instanceof Error) return e.message;
  return "Error desconocido al procesar la solicitud.";
}
