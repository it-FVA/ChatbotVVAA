-- (2/11) Pedido de Franco (reunión 2/11): un recorte se comparte con el equipo solo cuando su dueño lo permite.
-- Antes, «Del equipo» mostraba todos los recortes listos de las demás personas (regla del 21/10: «un recorte curado lo
-- puede reutilizar otro»). Ahora solo los que tienen compartido = true; lo prende y apaga el dueño desde Mis recortes.
-- Aplicada en Supabase (proyecto khgfqklieprcpxryqhtu) el 2/11/2026 con el MCP de Supabase.
alter table clips add column if not exists compartido boolean not null default false;
comment on column clips.compartido is '(2/11) true = el dueño lo compartió con el equipo: aparece en «Del equipo» y se puede guardar en proyectos ajenos';
