import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
export default defineConfig(function (_a) {
    var mode = _a.mode;
    // Solo se exponen al cliente las variables que empiezan con VITE_
    var env = loadEnv(mode, process.cwd(), "");
    return {
        plugins: [react()],
        resolve: {
            alias: {
                "@": fileURLToPath(new URL("./src", import.meta.url)),
            },
        },
        server: {
            port: 5173,
            strictPort: true,
            // Proxy hacia el backend para evitar problemas de CORS en dev.
            // El frontend hace fetch a /api/... y vite lo reenvía al backend.
            proxy: {
                "/api": {
                    target: env.VITE_API_URL || "http://localhost:8000",
                    changeOrigin: true,
                },
            },
        },
    };
});
