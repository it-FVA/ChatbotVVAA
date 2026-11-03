-- (2/11, noche) Pedido de Franco: en Mis publicaciones falta el botón «Compartir» que tiene Mis recortes. Misma regla que
-- clips.compartido: la persona dueña comparte la pieza con el equipo y aparece en la solapa «Del equipo» de las demás
-- (solo lectura: se ve, se guarda en un proyecto, no se retoma ni se borra). Los aprobadores ya ven todo por Aprobación.
-- Aplicada en Supabase (proyecto khgfqklieprcpxryqhtu) el 2/11/2026 con el MCP de Supabase.
alter table publicaciones add column if not exists compartido boolean not null default false;
comment on column publicaciones.compartido is '(2/11) la persona dueña la comparte con el equipo: aparece en Mis publicaciones → Del equipo de las demás (solo lectura), como clips.compartido';
