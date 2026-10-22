// Capturas de las pantallas de cuentas y administración (22/10) con Playwright sobre el Edge/Chrome instalado.
// Uso, con la API SIMULADA (python api/tests/servidor_simulado.py: tabla en memoria, sin Supabase) y la web levantadas:
//   node capturas-usuarios.mjs [escritorio|movil] [url de la web, default http://localhost:5173]
// Entra como beto (admin de la tabla simulada). No toca la base real.
import { chromium } from "playwright-core";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [modo = "escritorio", base = "http://localhost:5173"] = process.argv.slice(2);
const aca = path.dirname(fileURLToPath(import.meta.url));
const movil = modo === "movil";
const suf = movil ? "movil" : "escritorio";

const browser = await chromium.launch({ channel: "msedge", headless: true });
const ctx = await browser.newContext(
  movil ? { viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true } : { viewport: { width: 1366, height: 800 }, deviceScaleFactor: 1 },
);
const page = await ctx.newPage();
const foto = async (n, { entera = true } = {}) => {
  await page.evaluate((entera) => {
    if (!document.getElementById("foto-css")) {
      const st = document.createElement("style");
      st.id = "foto-css";
      st.textContent = "body.foto-entera .barra{position:static;height:auto} body.foto-entera .admin-menu{position:static}";
      document.head.appendChild(st);
    }
    document.body.classList.toggle("foto-entera", entera);
  }, entera).catch(() => {});
  await page.waitForTimeout(350);
  await page.screenshot({ path: path.join(aca, `${n}-${suf}.png`), fullPage: entera });
};

// «Primera vez»: paso 1 y paso 2 (email de la lista blanca)
await page.goto(base + "/primera-vez");
await page.waitForSelector("input[type=email]");
await foto("20-primera-vez");
await page.fill("input[type=email]", "amiga@gmail.com");
await page.click("button[type=submit]");
await page.waitForSelector("input[type=password]", { timeout: 10000 });
await page.fill("input[autocomplete=username]", "amiga").catch(() => {});
await page.fill("input[type=password] >> nth=0", "Clave-amiga1");
await page.fill("input[type=password] >> nth=1", "Clave-amiga1");
await foto("21-primera-vez-paso2");

// sesión de beto (admin)
await page.goto(base + "/login");
await page.waitForSelector("input[autocomplete=username]");
await page.fill("input[autocomplete=username]", "beto");
await page.fill("input[type=password]", "Clave-beto1");
await page.click("button[type=submit]");
await page.waitForURL(/\/recortes/, { timeout: 10000 });

// Mi cuenta
await page.goto(base + "/cuenta");
await page.waitForSelector("text=Cambiar mi contraseña");
await foto("22-cuenta");

// Administración → Usuarios, y el modal de reset de clave
await page.goto(base + "/administracion/usuarios");
await page.waitForSelector("table.tabla tbody tr");
await page.waitForTimeout(500);
await foto("23-admin-usuarios");
const fila = page.locator("table.tabla tbody tr", { hasText: "julian" });
await fila.locator("button", { hasText: "Clave" }).click();
await page.waitForSelector(".modal");
await foto("24-admin-reset-clave", { entera: false });
await page.locator(".modal button", { hasText: "Cancelar" }).click();

// Administración → Lista blanca
await page.goto(base + "/administracion/lista-blanca");
await page.waitForSelector("table.tabla");
await page.waitForTimeout(500);
await foto("25-admin-lista-blanca");

// Aprobación (marcador)
await page.goto(base + "/aprobacion");
await page.waitForSelector(".vacio");
await foto("26-aprobacion");

await browser.close();
console.log("listo:", suf);
