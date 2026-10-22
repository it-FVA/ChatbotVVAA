// Capturas de Administración (22/10: Dashboard, Salud, Servicios y costos, Configuración, y la pasada responsive de Usuarios y
// Lista blanca) con Playwright sobre el Edge/Chrome instalado. Con la API y la web levantadas:
//   node capturas-admin.mjs <usuario> <clave> [ancho|todos] [url de la web, default http://localhost:5173]
// Anchos: 1366 (escritorio), 1200, 1000 (menú solo iconos), 768 (chips + tarjetas) y 375 (celular). Solo mira; las pruebas de
// editar/borrar se hacen a mano. Las capturas quedan en esta carpeta como 30-…-<ancho>.png.
import { chromium } from "playwright-core";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [usuario, clave, cual = "todos", base = "http://localhost:5173"] = process.argv.slice(2);
if (!usuario || !clave) {
  console.error("uso: node capturas-admin.mjs <usuario> <clave> [1366|1200|1000|768|375|todos] [url]");
  process.exit(1);
}
const aca = path.dirname(fileURLToPath(import.meta.url));
const ANCHOS = cual === "todos" ? [1366, 1200, 1000, 768, 375] : [Number(cual)];
const PANTALLAS = [
  ["30-admin-dashboard", "/administracion/dashboard", ".graficos"],
  ["31-admin-salud", "/administracion/salud", ".chequeo"],
  ["32-admin-servicios", "/administracion/servicios", ".capacidad-item"],
  ["33-admin-configuracion", "/administracion/configuracion", ".bloque-config"],
  ["34-admin-usuarios", "/administracion/usuarios", "table.tabla tbody tr"],
  ["35-admin-lista-blanca", "/administracion/lista-blanca", "table.tabla"],
];

const browser = await chromium.launch({ channel: "msedge", headless: true });
for (const ancho of ANCHOS) {
  const movil = ancho < 768;
  const ctx = await browser.newContext({ viewport: { width: ancho, height: movil ? 812 : 900 }, deviceScaleFactor: movil ? 2 : 1, isMobile: movil, hasTouch: movil });
  const page = await ctx.newPage();
  await page.goto(base + "/login");
  await page.waitForSelector("input[autocomplete=username]");
  await page.fill("input[autocomplete=username]", usuario);
  await page.fill("input[type=password]", clave);
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 15000 });
  for (const [nombre, ruta, espera] of PANTALLAS) {
    await page.goto(base + ruta);
    await page.waitForSelector(espera, { timeout: 40000 });
    await page.waitForTimeout(900);
    await page.evaluate(() => {
      if (!document.getElementById("foto-css")) {
        const st = document.createElement("style");
        st.id = "foto-css";
        st.textContent = ".barra{position:static!important;height:auto!important} .admin-menu{position:static!important}";
        document.head.appendChild(st);
      }
    });
    await page.screenshot({ path: path.join(aca, `${nombre}-${ancho}.png`), fullPage: true });
    console.log(nombre, ancho);
  }
  await ctx.close();
}
await browser.close();
