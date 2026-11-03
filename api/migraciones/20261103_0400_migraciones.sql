-- (3/11, revisión 5.2 punto 11) La tabla que registra qué migraciones del repo están aplicadas en esta base.
-- La escribe python api/migrar.py (o apply_migration del MCP de Supabase, que además la anota en supabase_migrations).
-- Aplicada en Supabase (proyecto khgfqklieprcpxryqhtu) el 3/11/2026 con el MCP de Supabase.
create table if not exists migraciones (
  nombre text primary key,                         -- el nombre del archivo en api/migraciones/ (sin .sql)
  aplicada timestamptz not null default now(),
  por text,
  nota text
);
alter table migraciones enable row level security;

-- El esquema base describe la base tal como estaba el 3/11: cuenta como aplicado. Las historicas/ están incluidas en él.
insert into migraciones (nombre, por, nota) values
  ('000_esquema_base', 'claude', 'esquema completo sacado de la base real el 3/11/2026; incluye historicas/*'),
  ('20261103_0400_migraciones', 'claude', 'tabla de registro')
on conflict (nombre) do nothing;
