// Capturas de pantalla de la web (fase 1) con Playwright sobre el Edge/Chrome instalado (sin bajar navegadores).
// Uso (con la API en :8000 y la web en :5173 levantadas):
//   node capturas.mjs <token de sesión> <id del recorte a editar> [escritorio|movil]
// El token es el valor de la cookie fva_sesion que devuelve POST /login (ver README). Deja los .png en esta carpeta.
import { chromium } from "playwright-core";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [token, id, modo = "escritorio"] = process.argv.slice(2);
if (!token || !id) {
  console.error("uso: node capturas.mjs <token> <id-recorte> [escritorio|movil]");
  process.exit(1);
}
const aca = path.dirname(fileURLToPath(import.meta.url));
const base = "http://localhost:5173";
const movil = modo === "movil";
const suf = movil ? "movil" : "escritorio";

const browser = await chromium.launch({ channel: "msedge", headless: true });
const ctx = await browser.newContext(
  movil ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true } : { viewport: { width: 1366, height: 800 }, deviceScaleFactor: 1 },
);
const page = await ctx.newPage();
// la barra lateral es sticky: en una captura de página entera quedaría flotando en el medio
const foto = async (n) => {
  await page.addStyleTag({ content: ".barra{position:static;height:auto}" }).catch(() => {});
  await page.screenshot({ path: path.join(aca, `${n}-${suf}.png`), fullPage: true });
};

// login (pantalla) y sesión por cookie
await page.goto(base + "/login");
await page.waitForSelector("text=Entrar con Google");
await foto("00-login");
await ctx.addCookies([{ name: "fva_sesion", value: token, domain: "localhost", path: "/" }]);

// lista
await page.goto(base + "/recortes");
await page.waitForSelector(".recorte", { timeout: 20000 });
await page.waitForTimeout(1500);
await foto("01-lista");

// confirmación de borrado (se cancela: no borra nada)
const borrar = page.locator(".recorte", { hasText: "PRUEBA web fase 1" }).locator("button", { hasText: "Borrar" }).first();
if (await borrar.count()) {
  await borrar.click();
  await page.waitForSelector(".modal");
  await page.waitForTimeout(800);
  await foto("04-borrar-confirmacion");
  await page.locator(".modal button", { hasText: "Cancelar" }).click();
}

// editor
await page.goto(`${base}/recortes/${id}`);
await page.waitForSelector(".linea canvas", { timeout: 20000 });
await page.waitForTimeout(3000); // forma de onda
await foto("02-editor-inicial");

// mover la manija de inicio (arrastre), llevar el reproductor a un punto, partir y sacar el segundo pedazo
const manija = page.locator(".manija.ini");
const caja = await manija.boundingBox();
await page.mouse.move(caja.x + caja.width / 2, caja.y + caja.height / 2);
await page.mouse.down();
await page.mouse.move(caja.x + caja.width / 2 + (movil ? 14 : 24), caja.y + caja.height / 2, { steps: 6 });
await page.mouse.up();
const linea = await page.locator(".linea").boundingBox();
await page.mouse.click(linea.x + linea.width * 0.55, linea.y + linea.height * 0.5);
await page.waitForTimeout(600);
await page.locator("button", { hasText: "Partir acá" }).click();
await page.waitForTimeout(300);
const chips = page.locator(".pieza-chip");
if ((await chips.count()) >= 2) await chips.nth(1).click();

// subtítulos: corregir la primera línea; estilo: color, fondo y posición
const primera = page.locator(".sub-linea input").first();
if (await primera.count()) {
  await primera.fill("La gratitud es la LLAVE");
}
const sel = page.locator(".estilo-controles select");
if (await sel.count()) {
  await sel.nth(2).selectOption("amarillo de la marca");
  await sel.nth(3).selectOption("borde negro");
  await sel.nth(4).selectOption("centro");
}
await page.locator(".sub-tiempo").first().click().catch(() => {});
await page.waitForTimeout(800);
await foto("03-editor-editado");

if (!movil) {
  // regenerar (la fila de prueba vuelve a 'pedido'; la cola no encuentra el original y no sube nada)
  await page.locator("button", { hasText: "Regenerar el recorte" }).click();
  await page.waitForSelector("text=Regenerando el recorte", { timeout: 15000 });
  await page.waitForTimeout(500);
  await foto("05-regenerando");
  await page.goto(base + "/recortes");
  await page.waitForSelector(".recorte", { timeout: 20000 });
  await page.waitForTimeout(1200);
  await foto("06-lista-regenerando");
}
await browser.close();
console.log("listo:", suf);
