import { useRef, useState, type DragEvent, type ChangeEvent } from "react";

interface SubirImagenProps {
  id: string;
  etiqueta: string;
  required?: boolean;
  archivo: File | null;
  onChange: (archivo: File | null) => void;
  error?: string;
}

// === Constantes alineadas con el backend (SP3) ===
const TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024;
const TIPOS_PERMITIDOS = ["image/jpeg", "image/png"];
const ANCHO_MINIMO = 600;
const ALTO_MINIMO = 840;

async function leerDimensiones(
  archivo: File
): Promise<{ ancho: number; alto: number }> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(archivo);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve({ ancho: img.naturalWidth, alto: img.naturalHeight });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("No se pudo leer la imagen"));
    };
    img.src = url;
  });
}

function validarClienteSide(archivo: File): string | null {
  if (!TIPOS_PERMITIDOS.includes(archivo.type)) {
    if (archivo.type === "image/heic" || archivo.name.toLowerCase().endsWith(".heic")) {
      return "HEIC no es soportado. Convertí la imagen a JPEG o PNG primero.";
    }
    return "Formato no soportado. Solo JPEG y PNG.";
  }
  if (archivo.size > TAMANO_MAXIMO_BYTES) {
    return `Tamaño máximo: 10 MB. Tu archivo: ${(archivo.size / (1024 * 1024)).toFixed(1)} MB.`;
  }
  return null;
}

function formatearTamano(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Subcomponente para subir una imagen con drag-and-drop, preview y
 * validación client-side (mirror de las reglas del backend para UX rápida).
 *
 * El backend siempre revalida — esto es solo para evitar viajes de red
 * innecesarios con archivos obviamente inválidos.
 */
export function SubirImagen({
  id,
  etiqueta,
  required,
  archivo,
  onChange,
  error,
}: SubirImagenProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [errorCliente, setErrorCliente] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [dimensiones, setDimensiones] = useState<{ w: number; h: number } | null>(null);

  async function procesarArchivo(file: File) {
    setErrorCliente(null);

    const errorFormato = validarClienteSide(file);
    if (errorFormato) {
      setErrorCliente(errorFormato);
      onChange(null);
      setPreviewUrl(null);
      setDimensiones(null);
      return;
    }

    try {
      const { ancho, alto } = await leerDimensiones(file);
      setDimensiones({ w: ancho, h: alto });

      if (ancho < ANCHO_MINIMO || alto < ALTO_MINIMO) {
        setErrorCliente(
          `Resolución mínima: ${ANCHO_MINIMO}×${ALTO_MINIMO} px. Tu imagen: ${ancho}×${alto} px.`
        );
        onChange(null);
        setPreviewUrl(null);
        return;
      }
    } catch {
      setErrorCliente("No se pudo decodificar la imagen.");
      onChange(null);
      setPreviewUrl(null);
      return;
    }

    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(file));
    onChange(file);
  }

  function onInputChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) procesarArchivo(file);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) procesarArchivo(file);
  }

  function quitar() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setDimensiones(null);
    setErrorCliente(null);
    onChange(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  const errorMostrar = errorCliente || error;

  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1.5 block text-sm font-medium text-ink"
      >
        {etiqueta}
        {required && <span className="ml-1 text-danger">*</span>}
      </label>

      {archivo && previewUrl ? (
        <div className="rounded-card border border-ink/15 bg-cream p-4">
          <div className="flex gap-4">
            <img
              src={previewUrl}
              alt="Preview"
              className="h-40 w-28 rounded object-cover"
            />
            <div className="flex-1 space-y-1 text-sm">
              <p className="font-medium text-ink">{archivo.name}</p>
              <p className="text-ink-subtle">
                {formatearTamano(archivo.size)}
                {dimensiones && (
                  <>
                    {" · "}
                    {dimensiones.w}×{dimensiones.h} px
                  </>
                )}
              </p>
              <button
                type="button"
                onClick={quitar}
                className="text-sm text-danger underline decoration-danger/30 underline-offset-4 hover:decoration-danger"
              >
                Quitar
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={[
            "flex cursor-pointer flex-col items-center justify-center rounded-card border-2 border-dashed p-8 text-center transition-colors",
            dragging
              ? "border-holo bg-holo/5"
              : errorMostrar
                ? "border-danger/50 bg-danger/5"
                : "border-ink/20 bg-cream hover:border-ink/40",
          ].join(" ")}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="mb-3 h-8 w-8 text-ink-subtle"
            aria-hidden="true"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <p className="text-sm text-ink-muted">
            Arrastra una imagen aquí o{" "}
            <span className="text-holo underline decoration-holo/30 underline-offset-4">
              hace click para elegir
            </span>
          </p>
          <p className="mt-1 text-xs text-ink-subtle">
            JPEG o PNG · mín {ANCHO_MINIMO}×{ALTO_MINIMO} px · máx 10 MB
          </p>
        </div>
      )}

      <input
        ref={inputRef}
        id={id}
        type="file"
        accept="image/jpeg,image/png"
        onChange={onInputChange}
        className="hidden"
      />

      {errorMostrar && (
        <p className="mt-1.5 text-sm text-danger">{errorMostrar}</p>
      )}
    </div>
  );
}
