// (5/11, Franco) Chequeo estático de la ayuda, sin dependencias: node scripts/verificar-ayuda.mjs
// Compara los data-ayuda="<pantalla>.<id>" que hay en el código de web/src con los ids que declaran los definirAyuda("<pantalla>", { … }).
// Falla (código 1) si hay un data-ayuda sin explicar o un paso de la ayuda con id sin elemento. Corre con `npm test` y antes de `npm run build`.
// La prueba src/ayuda/registro.test.tsx hace lo mismo contra el DOM real de cada pantalla; esta es la red rápida para el CI.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src");

function archivos(dir) {
  const salida = [];
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) salida.push(...archivos(p));
    else if (/\.(tsx?|jsx?)$/.test(n) && !/\.test\.(tsx?|jsx?)$/.test(n)) salida.push(p);
  }
  return salida;
}

const declarados = new Map(); // "pantalla.id" → archivo
const usados = new Map(); // "pantalla.id" → archivo
const errores = [];
// el registro y el índice hablan de data-ayuda en sus comentarios: no cuentan
const propios = (p) => relative(SRC, p).replace(/\\/g, "/").startsWith("ayuda/");

for (const archivo of archivos(SRC)) {
  if (propios(archivo)) continue;
  const rel = relative(SRC, archivo).replace(/\\/g, "/");
  // sin comentarios: en ellos se explica el formato (data-ayuda="pantalla.<id>") y no cuenta
  const texto = readFileSync(archivo, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|\s)\/\/.*$/gm, "$1");

  // definirAyuda("pantalla", { … });  el cierre es «});» al principio de una línea
  for (const m of texto.matchAll(/definirAyuda\(\s*"([^"]+)"\s*,\s*\{([\s\S]*?)\r?\n\}\);/g)) {
    const [, pantalla, cuerpo] = m;
    for (const id of cuerpo.matchAll(/\bid:\s*"([^"]+)"/g)) {
      const clave = `${pantalla}.${id[1]}`;
      if (declarados.has(clave)) errores.push(`${rel}: el id ${clave} está declarado dos veces`);
      declarados.set(clave, rel);
    }
  }
  if (/definirAyuda\(/.test(texto) && !/definirAyuda\(\s*"[^"]+"\s*,\s*\{[\s\S]*?\r?\n\}\);/.test(texto) && !/export function definirAyuda/.test(texto)) {
    errores.push(`${rel}: no pude leer el definirAyuda (el cierre tiene que ser «});» al principio de una línea)`);
  }

  for (const m of texto.matchAll(/data-ayuda=("[^"]*"|\{[^}]*\})/g)) {
    const v = m[1];
    if (!v.startsWith('"')) {
      errores.push(`${rel}: data-ayuda tiene que ser un texto fijo (data-ayuda="pantalla.id"), no ${v}`);
      continue;
    }
    const clave = v.slice(1, -1);
    if (!/^[a-z0-9-]+\.[a-z0-9-]+$/.test(clave)) errores.push(`${rel}: data-ayuda="${clave}" no tiene la forma pantalla.id`);
    usados.set(clave, rel);
  }
}

for (const [clave, rel] of usados) if (!declarados.has(clave)) errores.push(`${rel}: data-ayuda="${clave}" no está en ningún definirAyuda (explicalo en la ayuda de su pantalla)`);
for (const [clave, rel] of declarados) if (!usados.has(clave)) errores.push(`${rel}: el paso "${clave}" de la ayuda no tiene ningún elemento con data-ayuda="${clave}"`);

if (errores.length) {
  console.error("La ayuda y el código no coinciden:\n - " + errores.join("\n - "));
  process.exit(1);
}
console.log(`Ayuda ok: ${declarados.size} pasos con elemento, ${usados.size} data-ayuda en el código.`);
