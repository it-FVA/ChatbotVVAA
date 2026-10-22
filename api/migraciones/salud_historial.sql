-- (22/10) Historial de GET /salud/servicios: una fila por corrida, para que la pantalla «Salud» diga desde cuándo está mal algo.
-- Aplicada en Supabase (proyecto khgfqklieprcpxryqhtu) el 22/10/2026 con el MCP de Supabase.
create table if not exists salud_historial (
  id bigserial primary key,
  creado timestamptz not null default now(),
  estado text not null,                 -- ok | aviso | error (el peor de los chequeos)
  detalle jsonb not null default '{}'   -- {chequeos: [{nombre, estado, detalle}], ms}
);
create index if not exists salud_historial_creado on salud_historial (creado desc);
alter table salud_historial enable row level security;   -- la API usa la clave service_role; nadie más la lee
