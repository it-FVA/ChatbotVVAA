-- (17/11) El vigía de la API (vigilar_api.py, corre en GitHub Actions con la clave de la cola) guarda en salud_historial
-- una fila 'caida' / 'vuelta' por cada cambio de estado, y lee la última para avisar una sola vez por caída.
grant select, insert on public.salud_historial to cola;
