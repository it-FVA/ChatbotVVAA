# Medición con el set dorado — 2026-10-22 00:16

51 consultas · solo pasajes validados OK por Pato (Set-dorado-validado-2026-10-16.csv) · acierto@6 = al menos un título esperado entre los primeros resultados · filtro de autor: **ninguno**

| Modo | Variante | Aciertos | Posición media del primer acierto | Latencia media | Mediana | p90 |
|---|---|---|---|---|---|---|
| V0 · local (producción) | sin reranker | **39/51** | 2.28 | 0.39 s | 0.22 s | 0.28 s |
| V0 · local (producción) | con reranker | **41/51** | 1.85 | 1.96 s | 1.77 s | 2.58 s |
| V1 · vectores en Supabase | sin reranker | **39/51** | 2.28 | 0.76 s | 0.59 s | 1.05 s |
| V1 · vectores en Supabase | con reranker | **41/51** | 1.63 | 2.69 s | 2.51 s | 3.83 s |
| V2 · vectores + léxico en Supabase | sin reranker | **33/51** | 1.91 | 0.61 s | 0.49 s | 0.89 s |
| V2 · vectores + léxico en Supabase | con reranker | **41/51** | 1.93 | 2.20 s | 2.06 s | 2.64 s |

Latencia = tiempo de `nucleo.buscar` por consulta, con el embedding y la traducción ya en caché (se precalentaron): mide la recuperación (y el reranker, en la variante con reranker), no la llamada de embedding. Medido desde la máquina de Franco (Windows, Internet doméstica); desde Render (Oregon) a Supabase la ida y vuelta puede ser distinta.

## Por consulta (posición del primer acierto; — = no apareció)

| N° | Consulta | V0 sin | V0 con | V1 sin | V1 con | V2 sin | V2 con |
|---|---|---|---|---|---|---|---|
| 1.0 | ¿Qué diferencia hace Br. David entre esperanza y expectativa? | 1 | 1 | 1 | 1 | 1 | 1 |
| 2.0 | ¿Qué dice Br. David sobre la gratitud como camino a la felicidad? | — | — | — | — | — | 4 |
| 3.0 | ¿En qué se distingue la gratitud del pensamiento positivo o la autoayu | 2 | — | 2 | — | 1 | 6 |
| 4.0 | ¿Qué es la gratuidad y por qué todo es un regalo, según Br. David? | 5 | 1 | 5 | 1 | 1 | 1 |
| 5.0 | ¿Qué dice Br. David sobre la sorpresa como puerta de la gratitud? | 1 | 2 | 1 | 2 | 1 | 1 |
| 6.0 | ¿Cómo se puede agradecer en medio del sufrimiento o el dolor? | 1 | 1 | 1 | 1 | 1 | 1 |
| 7.0 | La Transformación de la sociedad y la gratitud | 1 | 1 | 1 | 1 | 1 | 1 |
| 8.0 | ¿Qué es 'parar, mirar y responder' (Stop-Look-Go)? | 2 | 2 | 2 | 2 | 1 | 3 |
| 9.0 | ¿Qué significa 'responder' como gratitud en acción? | — | 2 | — | 1 | — | — |
| 10.0 | ¿Qué dice Br. David sobre vivir el momento presente? | 4 | 2 | 4 | 2 | — | 4 |
| 11.0 | ¿Qué enseña Br. David sobre el perdón? | 3 | 2 | 3 | 1 | 4 | 1 |
| 12.0 | ¿Qué relación hay entre el perdón y la culpa? | 1 | 1 | 1 | 1 | 5 | 3 |
| 13.0 | ¿Qué dice Br. David sobre la confianza plena en la vida? | 1 | 1 | 1 | 1 | 1 | 1 |
| 14.0 | ¿Qué es la fe según Br. David? | — | — | — | — | — | — |
| 15.0 | ¿Qué dice Br. David sobre el miedo y cómo la gratitud lo disuelve? | 3 | 1 | 3 | 1 | 4 | 2 |
| 16.0 | ¿Qué significa que todos somos una sola familia? | 1 | 1 | 1 | 1 | 5 | 1 |
| 17.0 | ¿Qué dice Br. David sobre el prójimo, el extranjero y la hospitalidad? | 3 | 1 | 3 | 1 | 2 | 1 |
| 18.0 | ¿Qué enseña Br. David sobre el silencio y la contemplación? | 1 | 1 | 1 | 1 | 1 | 1 |
| 19.0 | ¿Qué dice Br. David sobre la oración y la plegaria? | 1 | 1 | 1 | 1 | 1 | 1 |
| 20.0 | ¿Qué dice Br. David sobre la muerte? | 1 | 1 | 1 | 1 | 3 | 1 |
| 21.0 | ¿Qué dice Br. David sobre la alegría y el gozo? | 2 | 1 | 2 | 1 | — | 2 |
| 22.0 | ¿Qué es la obediencia entendida como escucha? | 1 | 1 | 1 | 1 | 1 | 1 |
| 23.0 | ¿Qué dice Br. David sobre el ego y el verdadero ser? | 6 | 2 | 6 | 2 | — | 2 |
| 24.0 | ¿Qué dice Br. David sobre la belleza? | 1 | 1 | 1 | 1 | 1 | 1 |
| 25.0 | ¿Qué dice Br. David sobre la vida como don o regalo? | — | 3 | — | 4 | — | 2 |
| 26.0 | ¿Qué dice Br. David sobre la paz interior? | 3 | 1 | 3 | 1 | 3 | 1 |
| 27.0 | Material para un posteo sobre la gratitud en los vínculos familiares | — | — | — | — | — | — |
| 28.0 | Material para un posteo sobre el perdón entre familiares | 2 | 1 | 2 | 1 | 2 | 1 |
| 29.0 | Material para una pieza sobre el Día del Voluntariado (servir, gratitu | 2 | — | 2 | — | 3 | — |
| 30.0 | Material para un carrusel sobre 'parar, mirar y responder' | 1 | 1 | 1 | 1 | 1 | 1 |
| 31.0 | Material para un posteo sobre agradecer en tiempos difíciles | 2 | 3 | 2 | 3 | — | — |
| 32.0 | Material para una pieza sobre la sorpresa y el asombro cotidiano | 5 | 2 | 5 | 2 | 1 | 1 |
| 33.0 | Material para un posteo sobre la esperanza (sin caer en la expectativa | 2 | 1 | 2 | 1 | 1 | 1 |
| 34.0 | Material para una newsletter sobre la confianza en la vida | — | — | — | — | — | — |
| 35.0 | Material para un posteo sobre el momento presente como regalo | 3 | 1 | 3 | 1 | 1 | 1 |
| 36.0 | Material para una pieza sobre gratitud y felicidad | — | 4 | — | 3 | — | 3 |
| 37.0 | Material para un posteo sobre el silencio interior | — | 5 | — | 5 | — | 4 |
| 38.0 | Material para una pieza sobre la muerte y la gratitud por la vida | 1 | 1 | 1 | 1 | 1 | 1 |
| 39.0 | Material para un posteo sobre la alegría que nace del agradecimiento | 6 | 4 | 6 | 4 | 5 | 1 |
| 40.0 | Material para una pieza sobre el miedo y la confianza | 2 | — | 2 | — | — | — |
| 41.0 | Material para un posteo sobre 'todo es regalo' (gratuidad) | 1 | 6 | 1 | 1 | 1 | 6 |
| 42.0 | Material para una pieza sobre la hospitalidad y el extranjero | 1 | 1 | 1 | 1 | — | 2 |
| 43.0 | Material para un posteo sobre la primavera, los ciclos y el renacer | — | — | — | — | — | — |
| 44.0 | Material para una newsletter del Día de la Madre desde la gratitud | 4 | 4 | 4 | 4 | 3 | 4 |
| 45.0 | Material para un posteo sobre la paz interior en tiempos de incertidum | — | — | — | — | — | — |
| 46.0 | Material para una pieza sobre la contemplación y la vida activa | 2 | 1 | 2 | 1 | 1 | 1 |
| 47.0 | Material para un posteo sobre pedir perdón y reconciliarse | 6 | 3 | 6 | 2 | 3 | 2 |
| 48.0 | Material para una pieza sobre la vocación y encontrar sentido | 3 | 1 | 3 | 1 | 1 | 1 |
| 49.0 | Material para un posteo sobre agradecer lo imperfecto de un vínculo | — | 5 | — | 4 | — | 3 |
| 50.0 | Material para una pieza sobre la belleza como camino a la gratitud | 1 | 1 | 1 | 1 | 1 | 3 |
| 51.0 | Cuidado del mundo | — | — | — | — | — | — |

## Qué cambia entre modos

- **V0 · local (producción) (con reranker)** vs V0 · local (producción) (sin reranker): gana 5 consultas ['9.0', '25.0', '36.0', '37.0', '49.0'], pierde 3 ['3.0', '29.0', '40.0']
- **V1 · vectores en Supabase (sin reranker)** vs V0 · local (producción) (sin reranker): gana 0 consultas [], pierde 0 []
- **V1 · vectores en Supabase (con reranker)** vs V0 · local (producción) (sin reranker): gana 5 consultas ['9.0', '25.0', '36.0', '37.0', '49.0'], pierde 3 ['3.0', '29.0', '40.0']
- **V2 · vectores + léxico en Supabase (sin reranker)** vs V0 · local (producción) (sin reranker): gana 0 consultas [], pierde 6 ['10.0', '21.0', '23.0', '31.0', '40.0', '42.0']
- **V2 · vectores + léxico en Supabase (con reranker)** vs V0 · local (producción) (sin reranker): gana 5 consultas ['2.0', '25.0', '36.0', '37.0', '49.0'], pierde 3 ['29.0', '31.0', '40.0']

## Memoria del proceso (medida el 22/10 en la máquina de Franco, Windows, Python 3.14, psutil RSS)

Por partes (corpus cargado, `BUSQUEDA_HIBRIDA=1`):

| Qué | MB | Acumulado |
|---|---|---|
| Python + numpy | 31 | 31 |
| `fragmentos.jsonl` (26.448 dicts) | +72 | 104 |
| `fragmentos_openai.npy` (26.448 × 512 float32) | +52 | 156 |
| índice BM25 (`rank_bm25`: un dict de frecuencias por fragmento) | +245 | 400 |

Por modo, con el índice caliente:

| Modo | RSS | Qué queda en memoria |
|---|---|---|
| V0 · local (producción) | 399 MB | jsonl + npy + BM25 |
| V1 · `VECTORES=supabase` | 347 MB | jsonl + BM25 |
| V2 · `VECTORES=supabase` + `LEXICO=supabase` | 148 MB | solo jsonl |

Del lado de Supabase: `fragmentos_emb` (vectores + texto + tsvector + índices HNSW y GIN) ocupa 190 MB de los 500 MB del plan
Free (la base pasó de ~13 MB a 203 MB, 41 %).

## Lectura

- **V1 (solo los vectores en Supabase) no cambia ningún resultado**: sin reranker, las 51 consultas dan exactamente la misma
  posición que en local (el HNSW devolvió los mismos 50 primeros que la fuerza bruta en la prueba de humo). Con reranker,
  41/51 igual que producción. Cuesta +0,37 s por consulta (media) sin reranker y ahorra 52 MB (400 → 347 MB). Cumple las dos
  condiciones (±2 y < 1,5 s), pero el ahorro es chico: lo que pesa es BM25.
- **V2 (vectores + texto de Postgres en lugar de BM25) empeora la recuperación**: sin reranker 33/51 contra 39/51 (pierde 6
  consultas: 10, 21, 23, 31, 40, 42; `ts_rank_cd` con OR de lexemas no es BM25). Con reranker vuelve a 41/51 porque el
  reranker ve 50 candidatos y rescata, pero la lista que le llega es peor. Regla del proyecto: solo se adopta si la métrica
  no empeora → **no se adopta** tal como está. Ahorra 252 MB (400 → 148 MB).
- Latencias medidas desde Argentina con Internet doméstica; desde Render (Oregon) a Supabase pueden ser otras. El reranker
  (una llamada al modelo) sigue siendo lo que más tarda y tiene ruido de ±1 s entre corridas.
- **Pista para el ahorro grande sin perder calidad** (no hecho, fuera de alcance de esta medición): BM25 ocupa 245 MB por
  cómo lo guarda `rank_bm25` (un dict por fragmento). La misma fórmula sobre una matriz dispersa (scipy) daría los mismos
  puntajes con ~10-20 MB. Habría que implementarlo y medirlo igual que esto antes de prenderlo.
