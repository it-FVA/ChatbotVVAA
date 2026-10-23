// Icono o miniatura de un ítem de proyecto según el tipo (22/10): conversación (globo), recorte (miniatura del video),
// pieza (su imagen, o el megáfono), imagen (la foto). Lo usan la grilla y la lista de la vista grande y el panel de detalles.
import type { ItemProyecto, TipoItem } from "../../tiposProyectos";
import { Icono, type NombreIcono } from "../Iconos";

export const TIPO_TXT: Record<TipoItem, string> = { conversacion: "Conversación", recorte: "Recorte", pieza: "Pieza", imagen: "Imagen" };
export const TIPO_ICONO: Record<TipoItem, NombreIcono> = { conversacion: "chat", recorte: "pelicula", pieza: "megafono", imagen: "imagen" };

export function IconoTipo({ tipo, tam = 18 }: { tipo: TipoItem; tam?: number }) {
  return <Icono nombre={TIPO_ICONO[tipo]} tam={tam} />;
}

/** Miniatura grande (grilla) o chica (lista). */
export function Miniatura({ it, chica = false }: { it: ItemProyecto; chica?: boolean }) {
  const clase = "item-mini tipo-" + it.tipo + (chica ? " chica" : "") + (it.formato === "vertical" ? " vertical" : "");
  if (it.miniatura && it.existe) {
    return (
      <div className={clase}>
        <img src={it.miniatura} alt="" loading="lazy" />
        {it.tipo === "recorte" && (
          <span className="item-mini-play" aria-hidden="true">
            <Icono nombre="reproducir" tam={chica ? 10 : 18} relleno />
          </span>
        )}
      </div>
    );
  }
  return (
    <div className={clase + " sin-foto"}>
      <IconoTipo tipo={it.tipo} tam={chica ? 16 : 34} />
    </div>
  );
}

/** A dónde lleva «Abrir» cada tipo (null si no tiene pantalla propia). */
export function rutaDe(it: ItemProyecto): string | null {
  if (!it.existe) return null;
  if (it.tipo === "conversacion") return `/chat/${it.item_id}`;
  if (it.tipo === "recorte") return it.estado === "listo" ? `/recortes/${it.item_id}` : "/recortes";
  if (it.tipo === "pieza") return "/publicaciones";
  return null;
}

export const ESTADO_TXT: Record<string, string> = {
  pedido: "en proceso",
  listo: "listo",
  error: "con error",
  borrador: "borrador",
  a_aprobar: "a aprobar",
  pendiente: "aprobada",
  programada: "programada",
  publicada: "publicada",
  PUBLICADO: "publicada",
  rechazada: "rechazada",
  cancelada: "cancelada",
  borrada: "en la papelera",
  no_existe: "ya no existe",
};
