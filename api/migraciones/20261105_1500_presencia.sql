-- (05/11) presencia: quién está mirando o editando una pieza o un recorte en este momento (Franco: «presencia y avisos»).
-- La pantalla late cada 20 s por la API (POST /presencia/{tipo}/{id}); la fila vive mientras `visto` sea reciente (60 s para mostrarla,
-- 10 min para que la cola la borre). No hay Realtime ni websockets: la web solo habla con la API.
-- Aplicar con `python api/migrar.py --aplicar` (o SQL Editor + `--registrar 20261105_1500_presencia`). Idempotente (if not exists).
-- Después, si el rol «cola» ya existe, volver a correr api/migraciones/manual_cola_rol.sql (la cola borra las filas viejas).

create table if not exists public.presencia (
  tipo    text not null,                      -- 'pieza' | 'recorte'
  item_id text not null,
  usuario text not null,
  modo    text not null default 'mira',       -- 'mira' | 'edita'
  visto   timestamptz not null default now(),
  primary key (tipo, item_id, usuario)
);
create index if not exists presencia_visto_idx on public.presencia (visto);
alter table public.presencia enable row level security;
