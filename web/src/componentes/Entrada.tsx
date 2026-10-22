// El cuadro para escribir: crece con el texto, Enter envía, Shift+Enter hace una línea nueva; mientras el bot responde el botón
// pasa a «Detener». El foco llega desde afuera con la tecla / (ref).
import { forwardRef, useImperativeHandle, useRef, useState, type KeyboardEvent } from "react";
import { Icono } from "./Iconos";

interface Props {
  placeholder: string;
  ayuda: string;
  enviando: boolean;
  textoEnviar: string;
  textoDetener: string;
  onEnviar: (texto: string) => void;
  onDetener: () => void;
}

export interface EntradaRef {
  enfocar: () => void;
  poner: (texto: string) => void;
}

const Entrada = forwardRef<EntradaRef, Props>(function Entrada({ placeholder, ayuda, enviando, textoEnviar, textoDetener, onEnviar, onDetener }, ref) {
  const [texto, setTexto] = useState("");
  const area = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    enfocar: () => area.current?.focus(),
    poner: (t: string) => {
      setTexto(t);
      window.setTimeout(() => {
        ajustar();
        area.current?.focus();
      }, 0);
    },
  }));

  function ajustar() {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 220) + "px";
  }

  function enviar() {
    const t = texto.trim();
    if (!t || enviando) return;
    onEnviar(t);
    setTexto("");
    window.setTimeout(ajustar, 0);
  }

  function tecla(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      enviar();
    }
  }

  return (
    <div className="entrada">
      <div className="entrada-caja">
        <textarea
          ref={area}
          value={texto}
          onChange={(e) => {
            setTexto(e.target.value);
            ajustar();
          }}
          onKeyDown={tecla}
          placeholder={placeholder}
          rows={1}
          aria-label={placeholder}
          enterKeyHint="send"
        />
        {enviando ? (
          <button type="button" className="boton peligro entrada-boton" onClick={onDetener} title={textoDetener}>
            <Icono nombre="pausar" tam={16} /> <span>{textoDetener}</span>
          </button>
        ) : (
          <button type="button" className="boton primario entrada-boton" onClick={enviar} disabled={!texto.trim()} title={textoEnviar}>
            <Icono nombre="chevron" tam={16} /> <span>{textoEnviar}</span>
          </button>
        )}
      </div>
      <div className="entrada-ayuda suave chico" aria-hidden="true">
        {ayuda}
      </div>
    </div>
  );
});

export default Entrada;
