// Capturas de pantalla de la web con Playwright sobre el Edge/Chrome instalado (sin bajar navegadores).
// Uso (con la API en :8000 y la web en :5173 levantadas):
//   node capturas.mjs <token de sesión> <id del recorte a editar> [escritorio|movil]
// El token es el valor de la cookie fva_sesion que devuelve POST /login (ver README). Deja los .png en esta carpeta.
// El recorte tiene que ser una FILA DE PRUEBA (el modo escritorio manda a regenerar al final).
// (22/10) Capturas nuevas: 12 (tres pedazos en la secuencia), 13 (arrastrando un bloque, con la marca de inserción), 14 (viendo la secuencia).
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
  movil ? { viewport: { width: 375, height: 812 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true } : { viewport: { width: 1366, height: 800 }, deviceScaleFactor: 1 },
);
const page = await ctx.newPage();
// la barra lateral y la barra inferior son fijas: en una captura de página entera quedarían flotando en el medio
const foto = async (n, { entera = true } = {}) => {
  // (solo en las capturas de página entera; en las de pantalla se ven fijas, como en el navegador)
  await page.evaluate((entera) => {
    if (!document.getElementById("foto-css")) {
      const st = document.createElement("style");
      st.id = "foto-css";
      st.textContent = "body.foto-entera .barra{position:static;height:auto} body.foto-entera .editor .editor-regenerar{position:static;border-radius:12px} body.foto-entera .editor-video{position:static}";
      document.head.appendChild(st);
    }
    document.body.classList.toggle("foto-entera", entera);
  }, entera).catch(() => {});
  await page.screenshot({ path: path.join(aca, `${n}-${suf}.png`), fullPage: entera });
};

// login (pantalla) y sesión por cookie
await page.goto(base + "/login");
await page.waitForSelector("text=Entrar con Google");
await foto("00-login");
await ctx.addCookies([{ name: "fva_sesion", value: token, domain: "localhost", path: "/" }]);

// lista: primero con la carga demorada (skeletons), después normal
const esLista = (u) => /\/api\/recortes(\?.*)?$/.test(u.pathname + u.search);
let demorar = true;
await page.route(esLista, async (ruta) => {
  if (demorar) await new Promise((r) => setTimeout(r, 2500));
  await ruta.continue().catch(() => {});
});
await page.goto(base + "/recortes");
await page.waitForSelector(".esqueleto", { timeout: 20000 });
await page.waitForTimeout(300);
await foto("10-lista-cargando", { entera: false });
demorar = false;
await page.waitForSelector(".recorte", { timeout: 20000 });
await page.waitForTimeout(1500);
await foto("01-lista");

// estado vacío (una búsqueda sin resultados)
await page.fill("input[type=search]", "zzzz-no-existe");
await page.waitForSelector(".vacio", { timeout: 20000 });
await page.waitForTimeout(400);
await foto("09-lista-vacia");
await page.fill("input[type=search]", "");
await page.waitForSelector(".recorte", { timeout: 20000 });
await page.waitForTimeout(800);

// confirmación de borrado (se cancela: no borra nada)
const borrar = page.locator(".recorte", { hasText: "PRUEBA UX" }).locator("button", { hasText: "Borrar" }).first();
if (await borrar.count()) {
  await borrar.click();
  await page.waitForSelector(".modal");
  await page.waitForTimeout(800);
  await foto("04-borrar-confirmacion", { entera: false });
  await page.locator(".modal button", { hasText: "Cancelar" }).click();
}

// editor
await page.goto(`${base}/recortes/${id}`);
await page.waitForSelector(".linea canvas", { timeout: 20000 });
await page.waitForTimeout(6000); // forma de onda y miniaturas
await foto("02-editor-inicial");

// atajos de teclado (modal)
await page.keyboard.press("?");
await page.waitForSelector(".modal");
await page.waitForTimeout(500);
await foto("08-atajos", { entera: false });
await page.keyboard.press("Escape");
await page.waitForTimeout(300);

// zoom (teclas +) con el cabezal movido: la vista sigue al cabezal
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("+");
await page.keyboard.press("+");
await page.waitForTimeout(600);
await page.locator(".manija.ini").hover();
await page.waitForTimeout(300);
await foto("07-editor-zoom", { entera: false });
await page.keyboard.press("0");
await page.waitForTimeout(400);

// mover la manija de inicio (arrastre), partir en el cabezal (S), seleccionar el segundo pedazo y sacarlo (Supr)
const manija = page.locator(".manija.ini");
const caja = await manija.boundingBox();
await page.mouse.move(caja.x + caja.width / 2, caja.y + caja.height / 2);
await page.mouse.down();
await page.mouse.move(caja.x + caja.width / 2 + (movil ? 14 : 24), caja.y + caja.height / 2, { steps: 6 });
await page.mouse.up();
await page.evaluate(() => document.activeElement?.blur()); // si no, las flechas mueven la manija (que quedó con el foco)
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("ArrowRight");
await page.keyboard.press("s");
await page.waitForTimeout(300);
const linea = await page.locator(".linea").boundingBox();
await page.mouse.click(linea.x + linea.width * 0.7, linea.y + linea.height * 0.6);
await page.waitForTimeout(300);
await page.keyboard.press("Delete");
await page.waitForTimeout(300);

// (22/10) cada pedazo es una pieza: restaurar el sacado, partir en tres, arrastrar el tercer bloque al principio de la secuencia
// (con la marca de inserción a la vista), recortar el primero por su manija y ver la secuencia
await page.evaluate(() => document.activeElement?.blur());
const restaurar = page.locator(".pieza-chip.restaurar").first();
if (await restaurar.count()) await restaurar.click();
await page.evaluate(() => {
  const v = document.querySelector("video");
  v.currentTime = Math.max(1, v.duration * 0.72);
});
await page.waitForTimeout(500);
await page.keyboard.press("s");
await page.waitForTimeout(400);
await page.locator(".linea-marco").scrollIntoViewIfNeeded();
await page.waitForTimeout(300);
await foto("12-editor-pedazos", { entera: false });
const bloques = page.locator(".bloque");
if ((await bloques.count()) >= 3) {
  const b3 = await bloques.nth(2).boundingBox();
  const b1 = await bloques.nth(0).boundingBox();
  await page.mouse.move(b3.x + b3.width / 2, b3.y + b3.height / 2);
  await page.mouse.down();
  await page.mouse.move(b1.x + 6, b3.y + b3.height / 2, { steps: 10 });
  await page.waitForTimeout(250);
  await foto("13-editor-arrastre", { entera: false });
  await page.mouse.up();
  await page.waitForTimeout(400);
  // manija de inicio del primer bloque: lo achica un poco (lo que saca queda rayado en el original)
  const manijaBloque = await bloques.nth(0).locator(".bloque-manija.ini").boundingBox();
  await page.mouse.move(manijaBloque.x + manijaBloque.width / 2, manijaBloque.y + manijaBloque.height / 2);
  await page.mouse.down();
  await page.mouse.move(manijaBloque.x + manijaBloque.width / 2 + (movil ? 12 : 22), manijaBloque.y + manijaBloque.height / 2, { steps: 6 });
  await page.mouse.up();
  await page.evaluate(() => document.activeElement?.blur());
  await page.waitForTimeout(400);
}
await page.locator("button", { hasText: "Ver secuencia" }).click();
await page.waitForTimeout(1500);
await foto("14-editor-secuencia", { entera: false });
await page.locator("button", { hasText: "Parar la secuencia" }).click().catch(() => {});
await page.waitForTimeout(300);

// subtítulos: corregir la primera línea; estilo: preset «Negrita amarilla» y posición centro
const primera = page.locator(".sub-linea input").first();
if (await primera.count()) {
  await primera.fill("La gratitud es la LLAVE");
}
const preset = page.locator(".preset", { hasText: "Negrita amarilla" });
if (await preset.count()) await preset.click();
const sel = page.locator(".estilo-controles select");
if (await sel.count()) await sel.nth(4).selectOption("centro");
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
} else {
  // en celular: la barra inferior fija con «Regenerar» tal como se ve en pantalla
  await page.evaluate(() => window.scrollTo(0, 400));
  await page.waitForTimeout(300);
  await foto("11-editor-barra-inferior", { entera: false });
}
await browser.close();
console.log("listo:", suf);
