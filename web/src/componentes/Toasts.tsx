// Avisos breves («toasts») abajo a la derecha: guardado, borrado, errores. useToast().avisar(texto, tipo).
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { Icono } from "./Iconos";

type Tipo = "ok" | "error" | "info";
interface Toast {
  id: number;
  texto: string;
  tipo: Tipo;
}

const Ctx = createContext<{ avisar: (texto: string, tipo?: Tipo) => void }>({ avisar: () => {} });
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [lista, setLista] = useState<Toast[]>([]);
  const n = useRef(0);
  const sacar = useCallback((id: number) => setLista((l) => l.filter((t) => t.id !== id)), []);
  const avisar = useCallback(
    (texto: string, tipo: Tipo = "ok") => {
      const id = ++n.current;
      setLista((l) => [...l.slice(-3), { id, texto, tipo }]);
      window.setTimeout(() => sacar(id), tipo === "error" ? 8000 : 4500);
    },
    [sacar],
  );
  const valor = useMemo(() => ({ avisar }), [avisar]);
  return (
    <Ctx.Provider value={valor}>
      {children}
      <div className="toasts" aria-live="polite">
        {lista.map((t) => (
          <div key={t.id} className={"toast " + t.tipo} role={t.tipo === "error" ? "alert" : "status"}>
            <Icono nombre={t.tipo === "ok" ? "check" : t.tipo === "error" ? "alerta" : "info"} tam={18} />
            <span>{t.texto}</span>
            <button type="button" className="toast-cerrar" onClick={() => sacar(t.id)} aria-label="Cerrar el aviso">
              <Icono nombre="cruz" tam={14} />
            </button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
