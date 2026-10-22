import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// En desarrollo la web habla con la API por el MISMO origen (/api/... → http://127.0.0.1:8000/...): así la cookie de
// sesión es de primera parte y no hace falta CORS. En producción, VITE_API_URL apunta a la API (ver README).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const api = env.VITE_API_PROXY || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": { target: api, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
      },
    },
  };
});
