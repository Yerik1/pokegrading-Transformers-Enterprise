import { useState, type ChangeEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ErrorDominio, ErrorRed } from "@/compartido/api/errores";
import { agregarCarta, type DatosCarta } from "@/catalogo/api/cartas-api";
import { SubirImagen } from "@/catalogo/componentes/SubirImagen";
import {
  ACABADOS,
  EDICIONES,
  IDIOMAS_CARTA,
  RAREZAS,
  TIPOS_POKEMON,
  type Acabado,
  type Carta,
  type Edicion,
  type IdiomaCarta,
  type Rareza,
  type TipoPokemon,
} from "@/catalogo/tipos/carta";

interface EstadoFormulario {
  // Identity tuple
  set_codigo: string;
  numero: string;
  edicion: Edicion | "";
  idioma: IdiomaCarta | "";
  acabado: Acabado | "";
  // Display
  nombre: string;
  rareza: Rareza | "";
  tipo: TipoPokemon | "";
  hp: string;
  ilustrador: string;
  anio_impresion: string;
}

const ESTADO_INICIAL: EstadoFormulario = {
  set_codigo: "",
  numero: "",
  edicion: "",
  idioma: "",
  acabado: "",
  nombre: "",
  rareza: "",
  tipo: "",
  hp: "",
  ilustrador: "",
  anio_impresion: "",
};

function aDatosCarta(form: EstadoFormulario): DatosCarta {
  return {
    set_codigo: form.set_codigo.trim(),
    numero: form.numero.trim(),
    edicion: form.edicion as Edicion,
    idioma: form.idioma as IdiomaCarta,
    acabado: form.acabado as Acabado,
    nombre: form.nombre.trim() || null,
    rareza: (form.rareza || null) as Rareza | null,
    tipo: (form.tipo || null) as TipoPokemon | null,
    hp: form.hp ? Number.parseInt(form.hp, 10) : null,
    ilustrador: form.ilustrador.trim() || null,
    anio_impresion: form.anio_impresion
      ? Number.parseInt(form.anio_impresion, 10)
      : null,
  };
}

export function AgregarCartaForm() {
  const [form, setForm] = useState<EstadoFormulario>(ESTADO_INICIAL);
  const [imagenFrente, setImagenFrente] = useState<File | null>(null);
  const [imagenReverso, setImagenReverso] = useState<File | null>(null);

  const [erroresCampo, setErroresCampo] = useState<Record<string, string>>({});
  const [errorGlobal, setErrorGlobal] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [creada, setCreada] = useState<Carta | null>(null);

  function actualizar<K extends keyof EstadoFormulario>(
    campo: K,
    valor: EstadoFormulario[K]
  ) {
    setForm((p) => ({ ...p, [campo]: valor }));
    if (erroresCampo[campo]) {
      setErroresCampo((p) => {
        const next = { ...p };
        delete next[campo];
        return next;
      });
    }
    if (errorGlobal) setErrorGlobal(null);
  }

  function onChangeTexto(e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) {
    const { name, value } = e.target;
    actualizar(name as keyof EstadoFormulario, value as never);
  }

  function resetear() {
    setForm(ESTADO_INICIAL);
    setImagenFrente(null);
    setImagenReverso(null);
    setErroresCampo({});
    setErrorGlobal(null);
    setCreada(null);
  }

  async function manejarSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setErrorGlobal(null);
    setErroresCampo({});

    // Validación mínima previa al envío (los campos requeridos)
    const errores: Record<string, string> = {};
    if (!form.set_codigo.trim()) errores.set_codigo = "Requerido.";
    if (!form.numero.trim()) errores.numero = "Requerido.";
    if (!form.edicion) errores.edicion = "Requerido.";
    if (!form.idioma) errores.idioma = "Requerido.";
    if (!form.acabado) errores.acabado = "Requerido.";
    if (!imagenFrente) errores.imagen_frente = "Imagen frontal requerida.";

    if (Object.keys(errores).length > 0) {
      setErroresCampo(errores);
      return;
    }

    setEnviando(true);
    try {
      const carta = await agregarCarta(
        aDatosCarta(form),
        imagenFrente!,
        imagenReverso
      );
      setCreada(carta);
    } catch (err) {
      if (err instanceof ErrorDominio) {
        if (err.campo) {
          setErroresCampo({ [err.campo]: err.mensaje });
        } else {
          setErrorGlobal(err.mensaje);
        }
      } else if (err instanceof ErrorRed) {
        setErrorGlobal(err.message);
      } else {
        setErrorGlobal("Ocurrió un error inesperado.");
      }
    } finally {
      setEnviando(false);
    }
  }

  // === Estado: carta creada con éxito ===
  if (creada) {
    return (
      <div className="rounded-card border border-success/30 bg-success/5 p-8">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-success">
          Carta creada
        </p>
        <h2 className="mt-2 font-display text-3xl tracking-tight-display text-ink">
          {creada.nombre ?? `${creada.set_codigo} ${creada.numero}`}
        </h2>
        <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs uppercase tracking-wider text-ink-subtle">ID</dt>
            <dd className="mt-0.5 font-mono text-xs text-ink">{creada.id}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-ink-subtle">Set</dt>
            <dd className="mt-0.5 text-ink">
              {creada.set_codigo} #{creada.numero}
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wider text-ink-subtle">
              Identity
            </dt>
            <dd className="mt-0.5 text-ink">
              {creada.edicion} · {creada.idioma} · {creada.acabado}
            </dd>
          </div>
        </dl>

        <div className="mt-8 flex gap-3">
          <button
            type="button"
            onClick={resetear}
            className="rounded-card bg-ink px-5 py-2.5 text-sm text-cream transition-colors hover:bg-ink/90"
          >
            Crear otra
          </button>
          <Link
            to="/inicio"
            className="rounded-card border border-ink/15 px-5 py-2.5 text-sm text-ink-muted transition-colors hover:border-ink/40 hover:text-ink"
          >
            Volver al inicio
          </Link>
        </div>
      </div>
    );
  }

  // === Estado: formulario ===
  return (
    <form onSubmit={manejarSubmit} noValidate className="space-y-10">
      {errorGlobal && (
        <div
          role="alert"
          className="rounded-card border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
        >
          {errorGlobal}
        </div>
      )}

      {/* === Sección: Identidad === */}
      <section>
        <header className="mb-4">
          <h2 className="font-display text-xl tracking-tight-display text-ink">
            Identidad
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            Los cinco campos que identifican unívocamente la carta. Cero
            duplicados permitidos.
          </p>
        </header>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <CampoTexto
            id="set_codigo"
            etiqueta="Código del set"
            placeholder="Ej: BASE, JUNGLE, XY1"
            valor={form.set_codigo}
            onChange={onChangeTexto}
            error={erroresCampo.set_codigo}
            required
          />
          <CampoTexto
            id="numero"
            etiqueta="Número en el set"
            placeholder="Ej: 4/102, H1"
            valor={form.numero}
            onChange={onChangeTexto}
            error={erroresCampo.numero}
            required
          />
          <CampoSelect
            id="edicion"
            etiqueta="Edición"
            valor={form.edicion}
            opciones={EDICIONES}
            onChange={onChangeTexto}
            error={erroresCampo.edicion}
            required
          />
          <CampoSelect
            id="idioma"
            etiqueta="Idioma"
            valor={form.idioma}
            opciones={IDIOMAS_CARTA}
            onChange={onChangeTexto}
            error={erroresCampo.idioma}
            required
          />
          <CampoSelect
            id="acabado"
            etiqueta="Acabado"
            valor={form.acabado}
            opciones={ACABADOS}
            onChange={onChangeTexto}
            error={erroresCampo.acabado}
            required
          />
        </div>
      </section>

      {/* === Sección: Display === */}
      <section>
        <header className="mb-4">
          <h2 className="font-display text-xl tracking-tight-display text-ink">
            Información de presentación
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            Datos opcionales que ayudan al usuario a reconocer la carta.
          </p>
        </header>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <CampoTexto
            id="nombre"
            etiqueta="Nombre"
            placeholder="Ej: Charizard"
            valor={form.nombre}
            onChange={onChangeTexto}
            error={erroresCampo.nombre}
          />
          <CampoSelect
            id="rareza"
            etiqueta="Rareza"
            valor={form.rareza}
            opciones={RAREZAS}
            onChange={onChangeTexto}
            error={erroresCampo.rareza}
            placeholderOption="— sin especificar —"
          />
          <CampoSelect
            id="tipo"
            etiqueta="Tipo Pokémon"
            valor={form.tipo}
            opciones={TIPOS_POKEMON}
            onChange={onChangeTexto}
            error={erroresCampo.tipo}
            placeholderOption="— sin especificar —"
          />
          <CampoTexto
            id="hp"
            etiqueta="HP"
            type="number"
            placeholder="30–340"
            valor={form.hp}
            onChange={onChangeTexto}
            error={erroresCampo.hp}
          />
          <CampoTexto
            id="ilustrador"
            etiqueta="Ilustrador"
            placeholder="Ej: Mitsuhiro Arita"
            valor={form.ilustrador}
            onChange={onChangeTexto}
            error={erroresCampo.ilustrador}
          />
          <CampoTexto
            id="anio_impresion"
            etiqueta="Año de impresión"
            type="number"
            placeholder="1996–2030"
            valor={form.anio_impresion}
            onChange={onChangeTexto}
            error={erroresCampo.anio_impresion}
          />
        </div>
      </section>

      {/* === Sección: Imágenes === */}
      <section>
        <header className="mb-4">
          <h2 className="font-display text-xl tracking-tight-display text-ink">
            Imágenes de referencia
          </h2>
          <p className="mt-1 text-sm text-ink-muted">
            La imagen frontal es obligatoria. El reverso es opcional.
          </p>
        </header>

        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
          <SubirImagen
            id="imagen_frente"
            etiqueta="Frente"
            required
            archivo={imagenFrente}
            onChange={setImagenFrente}
            error={erroresCampo.imagen_frente}
          />
          <SubirImagen
            id="imagen_reverso"
            etiqueta="Reverso"
            archivo={imagenReverso}
            onChange={setImagenReverso}
            error={erroresCampo.imagen_reverso}
          />
        </div>
      </section>

      <div className="flex items-center gap-3 border-t border-ink/10 pt-6">
        <button
          type="submit"
          disabled={enviando}
          className="rounded-card bg-ink px-6 py-3 text-base font-medium text-cream transition-all hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {enviando ? "Creando carta…" : "Crear carta"}
        </button>
        <Link
          to="/inicio"
          className="text-sm text-ink-subtle underline decoration-ink-subtle/30 underline-offset-4 hover:text-ink"
        >
          Cancelar
        </Link>
      </div>
    </form>
  );
}

// === Campos auxiliares ===

interface CampoTextoProps {
  id: string;
  etiqueta: string;
  type?: string;
  placeholder?: string;
  valor: string;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
  error?: string;
  required?: boolean;
}

function CampoTexto({
  id,
  etiqueta,
  type = "text",
  placeholder,
  valor,
  onChange,
  error,
  required,
}: CampoTextoProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-sm font-medium text-ink"
      >
        {etiqueta}
        {required && <span className="ml-1 text-danger">*</span>}
      </label>
      <input
        id={id}
        name={id}
        type={type}
        placeholder={placeholder}
        value={valor}
        onChange={onChange}
        className={[
          "w-full rounded-card border bg-cream px-4 py-2.5 text-ink transition-colors placeholder:text-ink-subtle/60 focus:border-holo",
          error ? "border-danger" : "border-ink/15",
        ].join(" ")}
      />
      {error && <p className="mt-1 text-sm text-danger">{error}</p>}
    </div>
  );
}

interface Opcion {
  valor: string;
  etiqueta: string;
}

interface CampoSelectProps {
  id: string;
  etiqueta: string;
  valor: string;
  opciones: Opcion[];
  onChange: (e: ChangeEvent<HTMLSelectElement>) => void;
  error?: string;
  required?: boolean;
  placeholderOption?: string;
}

function CampoSelect({
  id,
  etiqueta,
  valor,
  opciones,
  onChange,
  error,
  required,
  placeholderOption = "— seleccionar —",
}: CampoSelectProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-sm font-medium text-ink"
      >
        {etiqueta}
        {required && <span className="ml-1 text-danger">*</span>}
      </label>
      <select
        id={id}
        name={id}
        value={valor}
        onChange={onChange}
        className={[
          "w-full rounded-card border bg-cream px-4 py-2.5 text-ink transition-colors focus:border-holo",
          error ? "border-danger" : "border-ink/15",
          !valor ? "text-ink-subtle/60" : "",
        ].join(" ")}
      >
        <option value="">{placeholderOption}</option>
        {opciones.map((op) => (
          <option key={op.valor} value={op.valor}>
            {op.etiqueta}
          </option>
        ))}
      </select>
      {error && <p className="mt-1 text-sm text-danger">{error}</p>}
    </div>
  );
}
