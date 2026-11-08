import { Navigate, useLocation } from "react-router-dom";

// (8/11, Franco) Métricas se mudó de Administración a Gestión: los links viejos (y el regreso de WordPress.com con ?wordpress=…) siguen andando.
export default function RedirigeMetricas() {
  const { search } = useLocation();
  return <Navigate to={`/aprobacion/metricas${search}`} replace />;
}
