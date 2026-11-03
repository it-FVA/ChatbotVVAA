// Un conteo de la cabecera.


export function Conteo({ n, texto, ayuda, suave }: { n: number | undefined; texto: string; ayuda?: string; suave?: boolean }) {
  return (
    <span className={"fd-conteo" + (suave ? " suave" : "")} title={ayuda}>
      <strong>{n ?? 0}</strong> {texto}
    </span>
  );
}
