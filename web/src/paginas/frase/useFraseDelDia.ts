// (3/11) El estado compartido de la Frase del día: lo que antes vivía en el componente raíz de FraseDelDia.tsx (16 useState, los
// cargadores, `correr`, deshacer, arrastrar y soltar). La página y los paneles lo reciben de acá.
import { diaMes } from "../../util/fechas";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSesion } from "../../App";
import { type Mes, type Proxima, type Resumen, apiFrases } from "../../apiFrases";
import { useToast } from "../../componentes/Toasts";
import { type Arrastre, type Deshacer, mensajeDe } from "./comun";
import type { Solapa } from "./solapas";

export function useFraseDelDia() {
  const { yo } = useSesion();
  const { avisar } = useToast();
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [proximas, setProximas] = useState<Proxima[] | null>(null);
  const [cuando, setCuando] = useState<{ anio: number; mes: number } | null>(null);
  const [mes, setMes] = useState<Mes | null>(null);
  const [diaSel, setDiaSel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [arrastre, setArrastre] = useState<Arrastre | null>(null);
  const [sobre, setSobre] = useState<string | null>(null);
  const [deshacer, setDeshacer] = useState<Deshacer | null>(null);
  const [modal, setModal] = useState<"repartir" | "vaciar" | "nueva" | null>(null);
  const [verMail, setVerMail] = useState<string | null>(null); // (2/11) la fecha del mail que se está mirando
  const [verWa, setVerWa] = useState<string | null>(null); // (2/11 tarde) prototipo WhatsApp: la fecha del mensaje que se está mirando
  const [verMailDetalles, setVerMailDetalles] = useState(false); // (2/11 noche) los detalles de Perfit, en una ventana desde la fila Mail
  const [solapaPedida, setSolapaPedida] = useState<{ s: Solapa; n: number } | null>(null); // (2/11 tarde) desde el mail: abrir el día en «Foto de fondo»
  const [ocupado, setOcupado] = useState(false);
  const [version, setVersion] = useState(0); // para refrescar backlog y próximas tras un cambio
  const timerDeshacer = useRef<number | null>(null);

  const cargarResumen = useCallback(async () => {
    try {
      const r = await apiFrases.resumen();
      setResumen(r);
      setError(null);
      if (r.hoy && !cuando) {
        const [y, m] = r.hoy.split("-").map(Number);
        setCuando({ anio: y, mes: m });
      }
    } catch (e) {
      setError(mensajeDe(e));
      setResumen((r) => r ?? { disponible: false, admin: false, conteos: {}, activa: false, avisos: [] });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cargarMes = useCallback(async () => {
    if (!cuando) return;
    try {
      setMes(await apiFrases.mes(cuando.anio, cuando.mes));
    } catch (e) {
      avisar(mensajeDe(e), "error");
    }
  }, [cuando, avisar]);

  const recargar = useCallback(() => {
    cargarResumen();
    cargarMes();
    apiFrases.proximas(14).then(setProximas).catch(() => {});
    setVersion((v) => v + 1);
  }, [cargarResumen, cargarMes]);

  useEffect(() => {
    cargarResumen();
    apiFrases.proximas(14).then(setProximas).catch(() => {});
  }, [cargarResumen]);
  useEffect(() => {
    setMes(null);
    cargarMes();
  }, [cargarMes]);

  function ofrecerDeshacer(texto: string, hacer: () => Promise<void>) {
    if (timerDeshacer.current) window.clearTimeout(timerDeshacer.current);
    setDeshacer({ texto, hacer });
    timerDeshacer.current = window.setTimeout(() => setDeshacer(null), 15000);
  }

  async function correr(accion: () => Promise<string | void>, deshacerCon?: { texto: string; hacer: () => Promise<void> }) {
    setOcupado(true);
    try {
      const msg = await accion();
      if (msg) avisar(msg);
      if (deshacerCon) ofrecerDeshacer(deshacerCon.texto, deshacerCon.hacer);
      recargar();
    } catch (e) {
      avisar(mensajeDe(e), "error");
    } finally {
      setOcupado(false);
    }
  }

  /** Soltar una frase sobre un día: libre → mover (o asignar); ocupado → intercambiar (o cambiar por otra si venía del backlog). */
  async function soltar(fecha: string) {
    const a = arrastre;
    setArrastre(null);
    setSobre(null);
    if (!a || !mes || a.desde === fecha) return;
    const destino = mes.frases[fecha];
    if (destino?.cerrada) {
      avisar("La frase de ese día ya está en la cola o ya salió: no se puede cambiar.", "error");
      return;
    }
    if (!destino) {
      await correr(
        async () => (await apiFrases.mover(a.id, fecha)).mensaje,
        a.desde ? { texto: `Movida del ${diaMes(a.desde)} al ${diaMes(fecha)}.`, hacer: async () => void (await apiFrases.mover(a.id, a.desde!)) } : { texto: `Asignada al ${diaMes(fecha)}.`, hacer: async () => void (await apiFrases.sacar(a.id)) },
      );
    } else {
      await correr(
        async () => (a.desde ? `Intercambiadas: ${diaMes(a.desde)} ↔ ${diaMes(fecha)}.` : `Cambiada: la del ${diaMes(fecha)} volvió al backlog.`) && (await apiFrases.intercambiar(a.id, destino.id)).mensaje,
        { texto: a.desde ? `Intercambiadas ${diaMes(a.desde)} y ${diaMes(fecha)}.` : `Cambiada la frase del ${diaMes(fecha)}.`, hacer: async () => void (await apiFrases.intercambiar(a.id, destino.id)) },
      );
    }
  }

  // (2/11, Franco) el checklist de canales de la cabecera
  async function cambiarCanales(canales: string[]) {
    setOcupado(true);
    try {
      const r = await apiFrases.canales(canales);
      avisar(r.mensaje);
      recargar();
    } catch (e) {
      avisar(mensajeDe(e), "error");
    } finally {
      setOcupado(false);
    }
  }
  async function alternarActiva() {
    if (!resumen?.admin) return;
    await correr(async () => (await apiFrases.activa(!resumen.activa)).mensaje);
  }

  const meses = useMemo(() => {
    if (!resumen?.hoy) return [];
    const [y0, m0] = resumen.hoy.split("-").map(Number);
    const out: { anio: number; mes: number }[] = [];
    let y = y0;
    let m = m0;
    for (let i = 0; i < 13; i++) {
      out.push({ anio: y, mes: m });
      m += 1;
      if (m > 12) {
        m = 1;
        y += 1;
      }
    }
    return out;
  }, [resumen?.hoy]);

  const aprueba = resumen ? !!resumen.aprueba : !!yo?.rol.aprueba;
  const c = resumen?.conteos ?? {};


  return { avisar, yo, resumen, setResumen, proximas, setProximas, cuando, setCuando, mes, setMes, diaSel, setDiaSel, error, setError, arrastre, setArrastre, sobre, setSobre, deshacer, setDeshacer, modal, setModal, verMail, setVerMail, verWa, setVerWa, verMailDetalles, setVerMailDetalles, solapaPedida, setSolapaPedida, ocupado, setOcupado, version, setVersion, timerDeshacer, cargarResumen, cargarMes, recargar, ofrecerDeshacer, correr, soltar, cambiarCanales, alternarActiva, meses, aprueba, c };
}

export type EstadoFrase = ReturnType<typeof useFraseDelDia>;
