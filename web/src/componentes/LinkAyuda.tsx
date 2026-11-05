import { Link } from "react-router-dom";

// (5/11, Franco) Link chico «¿Cómo se usa?» que va junto al párrafo de ayuda de cada pantalla y abre la sección de /ayuda.
// `seccion` es el id de una sección de paginas/Ayuda.tsx (chat, disenar, publicaciones, recortes, newsletter, frase-del-dia, proyectos, gestion).
export default function LinkAyuda({ seccion }: { seccion: string }) {
  return (
    <Link to={`/ayuda#${seccion}`} className="link-ayuda chico">
      ¿Cómo se usa?
    </Link>
  );
}
