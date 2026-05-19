import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { RutaProtegida } from "@/compartido/auth/RutaProtegida";
import { RegistroPagina } from "@/usuarios/paginas/RegistroPagina";
import { LoginPagina } from "@/usuarios/paginas/LoginPagina";
import { InicioPagina } from "@/usuarios/paginas/InicioPagina";
import { AgregarCartaPagina } from "@/catalogo/paginas/AgregarCartaPagina";

/**
 * Rutas de la aplicación.
 *
 * Públicas:
 *   /             → redirect a /inicio (si hay sesión) o /login (si no)
 *   /registro     → registro público (Submitter por default)
 *   /login        → login
 *
 * Protegidas (cualquier rol autenticado):
 *   /inicio       → landing post-login
 *
 * Protegidas (admin o superadmin):
 *   /admin/cartas/nueva → agregar carta al catálogo
 *
 * Cualquier otra ruta cae al catch-all que redirige a /.
 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/inicio" replace />} />
        <Route path="/registro" element={<RegistroPagina />} />
        <Route path="/login" element={<LoginPagina />} />

        <Route
          path="/inicio"
          element={
            <RutaProtegida>
              <InicioPagina />
            </RutaProtegida>
          }
        />

        <Route
          path="/admin/cartas/nueva"
          element={
            <RutaProtegida roles={["admin", "superadmin"]}>
              <AgregarCartaPagina />
            </RutaProtegida>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
