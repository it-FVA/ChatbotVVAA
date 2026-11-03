// Solapa «Foto de fondo» del detalle del día.
import { type Frase, apiFrases } from "../../../apiFrases";
import { ElegirFoto } from "../paneles/ElegirFoto";
import type { PropsSolapa } from "./index";

export function FotoFondo({ f, ocupado, correr }: { f: Frase; ocupado: boolean; correr: (a: () => Promise<string | void>) => Promise<void> }) {
  return (
    <div className="fd-form">
      <p className="suave chico">Foto del banco de imágenes de WordPress (las etiquetadas «cuadrado» primero). Sin elección, va la foto por defecto. La foto elegida va a la imagen compuesta, al mail y a las redes.</p>
      <ElegirFoto
        actual={f.imagen_url}
        ocupado={ocupado}
        textoQuitar="Volver a la foto por defecto"
        onElegir={(url) => correr(async () => (url ? ((await apiFrases.editar(f.id, { imagen_url: url })), "Foto elegida.") : ((await apiFrases.editar(f.id, { quitar_imagen: true })), "Vuelve a la foto por defecto.")))}
      />
    </div>
  );
}

export default function Foto({ f, ocupado, correr }: PropsSolapa) {
  return <FotoFondo f={f} ocupado={ocupado} correr={correr} />;
}
