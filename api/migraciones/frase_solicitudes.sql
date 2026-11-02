-- (2/11) Pedido de Franco (reunión 2/11): los creadores de contenido ven el calendario de la Frase del día y pueden
-- pedir un cambio («me gustaría que este día salga esta frase»). El pedido queda acá hasta que un aprobador lo acepta
-- (se aplica al calendario: mover / intercambiar / crear la frase) o lo rechaza con una respuesta.
-- Aplicada en Supabase (proyecto khgfqklieprcpxryqhtu) el 2/11/2026 con el MCP de Supabase.
create table if not exists frase_solicitudes (
  id uuid primary key default gen_random_uuid(),
  creado timestamptz not null default now(),
  usuario text not null,                       -- quién pide
  fecha date not null,                         -- para qué día
  frase_id uuid references frases(id) on delete set null,   -- una frase que ya existe (validada, sin día o en otro día)
  texto text,                                  -- o una frase nueva (texto + autor)
  autor text,
  nota text,                                   -- por qué / comentario para quien aprueba
  estado text not null default 'pendiente',    -- pendiente | aceptada | rechazada | retirada
  resuelta_por text,
  resuelta_en timestamptz,
  respuesta text                               -- lo que contesta el aprobador (sobre todo al rechazar)
);
create index if not exists frase_solicitudes_estado on frase_solicitudes (estado, creado desc);
create index if not exists frase_solicitudes_usuario on frase_solicitudes (usuario, creado desc);
comment on table frase_solicitudes is '(2/11) pedidos de cambio del calendario de la Frase del día hechos por creadores de contenido; los resuelve un aprobador';
