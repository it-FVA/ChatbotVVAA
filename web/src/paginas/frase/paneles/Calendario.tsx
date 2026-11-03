// El calendario por mes con arrastrar y soltar (3/11: antes dentro de FraseDelDia.tsx).

import { MESES } from "../../../util/fechas";
import { Hueso } from "../../../componentes/Comunes";
import { Icono } from "../../../componentes/Iconos";
import { DIAS, ICONO_ESTADO, empezarArrastre, mesVecino, recortar } from "../comun";
import type { EstadoFrase } from "../useFraseDelDia";

export function Calendario({ s }: { s: EstadoFrase }) {
  const { cuando, setCuando, mes, setDiaSel, arrastre, setArrastre, sobre, setSobre, soltar, meses, aprueba } = s;
  return (
    <section className="fd-calendario" aria-label="Calendario">
      <div className="fd-mes-nav">
        <button type="button" className="boton chico icono-solo" aria-label="Mes anterior" onClick={() => cuando && setCuando(mesVecino(cuando, -1))} disabled={!cuando || !meses.length || (cuando.anio === meses[0].anio && cuando.mes === meses[0].mes)}>
          <Icono nombre="chevron" tam={16} style={{ transform: "rotate(180deg)" }} />
        </button>
        <select value={cuando ? `${cuando.anio}-${cuando.mes}` : ""} onChange={(e) => setCuando({ anio: Number(e.target.value.split("-")[0]), mes: Number(e.target.value.split("-")[1]) })} aria-label="Mes">
          {meses.map((x) => (
            <option key={`${x.anio}-${x.mes}`} value={`${x.anio}-${x.mes}`}>
              {MESES[x.mes - 1][0].toUpperCase() + MESES[x.mes - 1].slice(1)} {x.anio}
            </option>
          ))}
        </select>
        <button type="button" className="boton chico icono-solo" aria-label="Mes siguiente" onClick={() => cuando && setCuando(mesVecino(cuando, 1))} disabled={!cuando || !meses.length || (cuando.anio === meses[meses.length - 1].anio && cuando.mes === meses[meses.length - 1].mes)}>
          <Icono nombre="chevron" tam={16} />
        </button>
        <span className="suave chico fd-leyenda">
          <Icono nombre="calendario" tam={13} /> programada · <Icono nombre="megafono" tam={13} /> publicada · <Icono nombre="ojo" tam={13} /> simulada · ⏭ salteada · ↻ ya salió antes
        </span>
      </div>
      {mes === null ? (
        <div className="fd-dias" aria-busy="true">
          {Array.from({ length: 35 }).map((_, i) => (
            <Hueso key={i} alto={74} radio={8} />
          ))}
        </div>
      ) : (
        <div className="fd-dias" role="grid" aria-label={`${MESES[mes.mes - 1]} ${mes.anio}`}>
          {DIAS.map((d) => (
            <div key={d} className="fd-dia-nombre" role="columnheader">
              {d}
            </div>
          ))}
          {Array.from({ length: mes.primer_dia_semana }).map((_, i) => (
            <div key={"v" + i} className="fd-dia vacio" aria-hidden="true" />
          ))}
          {Array.from({ length: mes.dias }).map((_, i) => {
            const f = `${mes.anio}-${String(mes.mes).padStart(2, "0")}-${String(i + 1).padStart(2, "0")}`;
            const fr = mes.frases[f];
            const pasado = f < mes.hoy;
            const hoy = f === mes.hoy;
            const puedeSoltar = aprueba && !!arrastre && !pasado && arrastre.desde !== f && !(fr?.cerrada);
            return (
              <div
                key={f}
                role="gridcell"
                tabIndex={0}
                className={"fd-dia" + (hoy ? " hoy" : "") + (pasado ? " pasado" : "") + (fr ? " con-frase " + fr.estado : " libre") + (sobre === f && puedeSoltar ? " sobre" : "") + (arrastre && !puedeSoltar ? " no-soltar" : "")}
                onClick={() => setDiaSel(f)}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setDiaSel(f))}
                onDragOver={(e) => {
                  if (!puedeSoltar) return;
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "move";
                  if (sobre !== f) setSobre(f);
                }}
                onDragLeave={() => sobre === f && setSobre(null)}
                onDrop={(e) => {
                  e.preventDefault();
                  if (puedeSoltar) soltar(f);
                }}
                aria-label={`${i + 1}: ${fr ? recortar(fr.texto, 60) : "sin frase"}`}
              >
                <div className="fd-dia-num">
                  <span>{i + 1}</span>
                  {hoy && <span className="chip amarillo chico">hoy</span>}
                  {fr && (
                    <span className="fd-estado" title={fr.estado_texto}>
                      {fr.estado === "saltada" ? "⏭" : <Icono nombre={ICONO_ESTADO[fr.estado] ?? "calendario"} tam={13} />}
                      {fr.repetida ? " ↻" : ""}
                    </span>
                  )}
                </div>
                {fr ? (
                  <div
                    className={"fd-frase" + (fr.cerrada || pasado || !aprueba ? " fija" : "")}
                    draggable={aprueba && !fr.cerrada && !pasado}
                    onDragStart={(e) => aprueba && empezarArrastre(e, { id: fr.id, desde: f, texto: fr.texto }, setArrastre)}
                    onDragEnd={() => (setArrastre(null), setSobre(null))}
                    title={!aprueba ? "Abrí el día para ver la frase o pedir un cambio" : fr.cerrada ? "En la cola o ya salió: no se mueve" : "Arrastrá a otro día para mover o intercambiar"}
                  >
                    <span className="fd-texto">{recortar(fr.texto, 70)}</span>
                    {fr.autor && <span className="fd-autor suave chico">{fr.autor}</span>}
                  </div>
                ) : (
                  <div className="fd-sin suave chico">{pasado ? "—" : "sin frase"}</div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
