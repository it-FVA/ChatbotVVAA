-- (25/11) El vigía (vigilar_api.py, rol «cola») mandaba el aviso rojo pero nunca guardaba la fila 'caida' en salud_historial:
-- el grant del 17/11 dio insert sobre la tabla pero no USAGE sobre la secuencia del id («permission denied for sequence
-- salud_historial_id_seq»). Sin la fila, el vigía no sabía que estaba caída y nunca mandó el aviso verde «Volvió la API».
-- Lo mismo para usuarios_cambios, por si la cola llega a registrar un cambio. Aplicadas con el MCP de Supabase el 25/11. Idempotentes.
grant usage, select on sequence public.salud_historial_id_seq to cola;
grant usage, select on sequence public.usuarios_cambios_id_seq to cola;
