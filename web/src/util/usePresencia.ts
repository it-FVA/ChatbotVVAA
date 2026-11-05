// (5/11, Franco: «presencia y avisos») Quién más está en esta pieza o recorte. Late a la API cada 20 s mientras la pantalla está
// montada y la pestaña a la vista; al volver a la pestaña late enseguida; al desmontar (o cerrar la pestaña) avisa que salió.
// Es un adorno: si la API falla, la lista queda como estaba y la pantalla sigue andando. Sin id (una pieza que todavía no se guardó), no late.
import { useEffect, useState } from "react";
import { apiPresencia, type Presente } from "../api";

export const LATIDO_MS = 20_000;

export function usePresencia(tipo: "pieza" | "recorte", id: string | null | undefined, modo: "mira" | "edita"): Presente[] {
  const [presentes, setPresentes] = useState<Presente[]>([]);

  useEffect(() => {
    setPresentes([]);
    if (!id) return;
    let vivo = true;
    const latir = () => {
      if (document.hidden) return; // pestaña oculta: no late (en un minuto deja de figurar)
      apiPresencia
        .latir(tipo, id, modo)
        .then((r) => vivo && setPresentes(r.presentes || []))
        .catch(() => {});
    };
    const salir = () => {
      apiPresencia.salir(tipo, id).catch(() => {});
    };
    const alVer = () => {
      if (!document.hidden) latir();
    };
    latir();
    const reloj = window.setInterval(latir, LATIDO_MS);
    document.addEventListener("visibilitychange", alVer);
    window.addEventListener("pagehide", salir);
    return () => {
      vivo = false;
      window.clearInterval(reloj);
      document.removeEventListener("visibilitychange", alVer);
      window.removeEventListener("pagehide", salir);
      salir();
    };
  }, [tipo, id, modo]);

  return presentes;
}
