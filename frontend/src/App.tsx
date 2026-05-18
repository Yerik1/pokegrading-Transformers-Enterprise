import { RegistroPagina } from "@/usuarios/paginas/RegistroPagina";

/**
 * Componente raíz de la app.
 *
 * Por ahora muestra directamente la página de registro porque es la única
 * pantalla del Sprint 1. Cuando agreguemos más páginas (login, catálogo,
 * etc.) introducimos react-router aquí.
 */
function App() {
  return <RegistroPagina />;
}

export default App;
