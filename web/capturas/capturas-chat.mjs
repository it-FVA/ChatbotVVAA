// Capturas de la pantalla de chat (fase 2) con Playwright sobre el Edge/Chrome instalado (sin bajar navegadores).
// Uso (con la API en :8000 y la web en :5173 levantadas):
//   node capturas-chat.mjs <token de sesión> <id de una conversación con fuentes de video y pieza> [escritorio|movil]
// El token es el valor de la cookie fva_sesion que devuelve POST /login. No manda mensajes ni pide recortes: solo mira.
import { chromium } from "playwright-core";
import path from "node:path";
import { fileURLToPath } from "node:url";

const [token, id, modo = "escritorio"] = process.argv.slice(2);
if (!token || !id) {
  console.error("uso: node capturas-chat.mjs <token> <id-conversacion> [escritorio|movil]");
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
await ctx.addCookies([{ name: "fva_sesion", value: token, domain: "localhost", path: "/" }]);
const page = await ctx.newPage();
const foto = (n) => page.screenshot({ path: path.join(aca, `${n}-${suf}.png`) });

// chat vacío
await page.goto(base + "/chat");
await page.waitForSelector(".chat-vacio", { timeout: 20000 });
await page.waitForSelector(".conv-item", { timeout: 20000 }).catch(() => {});
await page.waitForTimeout(600);
await foto("20-chat-vacio");

// una conversación real: respuesta con fuentes
await page.goto(base + "/chat/" + id);
await page.waitForSelector(".fuentes", { timeout: 20000 });
await page.waitForTimeout(1200); // miniaturas de YouTube
await page.evaluate(() => {
  document.querySelector(".fuentes")?.setAttribute("open", "");
  const panel = document.querySelector(".chat-mensajes");
  const primera = document.querySelector(".msj.bot");
  if (panel && primera) panel.scrollTop = primera.offsetTop - panel.offsetTop - 12;
});
await page.waitForTimeout(600);
await foto("21-respuesta-fuentes");

// la tarjeta de video con el recorte (en proceso o listo)
const tarjeta = page.locator(".fuente.video").first();
if (await tarjeta.count()) {
  await tarjeta.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await tarjeta.screenshot({ path: path.join(aca, `22-tarjeta-video-recorte-${suf}.png`) });
}

// la pieza propuesta
const pieza = page.locator(".pieza-caja").last();
if (await pieza.count()) {
  await page.evaluate(() => document.querySelectorAll(".pieza-caja").forEach((p) => p.setAttribute("open", "")));
  await pieza.scrollIntoViewIfNeeded();
  await page.waitForTimeout(1500); // fotos del banco
  await pieza.screenshot({ path: path.join(aca, `23-pieza-propuesta-${suf}.png`) });
}

// celular: el cajón de conversaciones abierto
if (movil) {
  await page.evaluate(() => document.querySelector(".chat-mensajes")?.scrollTo(0, 0));
  await page.click(".chat-abrir-lista");
  await page.waitForTimeout(400);
  await foto("24-cajon-conversaciones");
}

await browser.close();
console.log("listo:", aca);
