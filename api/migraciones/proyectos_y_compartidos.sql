-- (22/10, «Proyectos» de la interfaz nueva) Carpetas colaborativas: tabla `proyectos` (con subcarpetas por padre_id),
-- `proyecto_items` (qué hay adentro: solo REFERENCIAS a conversaciones, clips y publicaciones; nada se mueve de su tabla)
-- y `compartidos` (con quién está compartido un proyecto o una conversación suelta, y con qué permiso).
-- Correr UNA vez en Supabase (SQL Editor o apply_migration `proyectos_y_compartidos`). Es idempotente.
--
-- Reglas (las aplica api/proyectos.py, no la base):
--   · ve y edita un proyecto: su dueño; con quien se compartió (o se compartió una carpeta de arriba) según el permiso.
--   · «editar» permite agregar/sacar/mover ítems, renombrar y crear subcarpetas; «ver» es solo lectura. Borrar: solo el dueño.
--   · una conversación/recorte/pieza está en UN proyecto o suelta (al agregarla a otro, se saca del anterior).

create table if not exists proyectos (
  id uuid primary key default gen_random_uuid(),
  nombre text not null,
  descripcion text,
  dueno text not null,                                  -- usuario (como `conversaciones.usuario`); "dueño" sin ñ por el SQL
  padre_id uuid references proyectos (id) on delete cascade,   -- null = carpeta de primer nivel
  color text,                                           -- opcional: un color de la paleta (hex) para el icono de la carpeta
  emoji text,                                           -- opcional: un emoji en vez del icono
  creado timestamptz not null default now(),
  actualizado timestamptz not null default now()
);
create index if not exists proyectos_dueno_idx on proyectos (dueno, actualizado desc);
create index if not exists proyectos_padre_idx on proyectos (padre_id);
alter table proyectos enable row level security;

create table if not exists proyecto_items (
  id uuid primary key default gen_random_uuid(),
  proyecto_id uuid not null references proyectos (id) on delete cascade,
  tipo text not null check (tipo in ('conversacion', 'recorte', 'pieza', 'imagen')),
  item_id text not null,                                -- id (uuid) de conversaciones / clips / publicaciones; para 'imagen', la URL
  datos jsonb,                                          -- solo 'imagen': {url, miniatura, titulo} (una foto del banco con frase y logo, reutilizable)
  agregado_por text not null,
  agregado timestamptz not null default now(),
  unique (proyecto_id, tipo, item_id)
);
create index if not exists proyecto_items_item_idx on proyecto_items (tipo, item_id);
alter table proyecto_items enable row level security;

create table if not exists compartidos (
  id uuid primary key default gen_random_uuid(),
  tipo text not null check (tipo in ('proyecto', 'conversacion')),
  item_id text not null,                                -- id del proyecto o de la conversación
  con_usuario text not null,                            -- usuario (tabla `usuarios`) con quien se comparte
  permiso text not null default 'ver' check (permiso in ('ver', 'editar')),
  compartido_por text not null,
  creado timestamptz not null default now(),
  unique (tipo, item_id, con_usuario)
);
create index if not exists compartidos_con_idx on compartidos (con_usuario);
create index if not exists compartidos_item_idx on compartidos (tipo, item_id);
alter table compartidos enable row level security;
