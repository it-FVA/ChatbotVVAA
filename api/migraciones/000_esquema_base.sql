-- 000_esquema_base.sql · El esquema COMPLETO de la base en Supabase (proyecto khgfqklieprcpxryqhtu) tal como estaba el 3/11/2026.
-- (revisión 3/11, 5.2 punto 11) Sacado de la base real con el MCP de Supabase: pg_attribute / pg_indexes / pg_proc / pg_constraint,
-- no escrito de memoria. 17 tablas, 5 funciones, 4 extensiones. Sirve para levantar una base de prueba desde cero:
--   1. correr este archivo (es idempotente: create ... if not exists),
--   2. correr las migraciones numeradas que vengan después (api/migraciones/AAAAMMDD_HHMM_nombre.sql) en orden,
--   3. cada una queda anotada en la tabla `migraciones` (python api/migrar.py).
-- Las migraciones anteriores al 3/11 (api/migraciones/historicas/) ya están incluidas acá: no se vuelven a correr.
-- RLS: todas las tablas tienen RLS habilitado y SIN políticas (la API y la cola entran con la clave service_role, que lo saltea),
-- salvo frase_solicitudes, que quedó con RLS deshabilitado (aviso del advisor de Supabase el 3/11; decide Franco).

create extension if not exists pgcrypto with schema extensions;
create extension if not exists "uuid-ossp" with schema extensions;
create extension if not exists vector with schema extensions;
create extension if not exists unaccent with schema extensions;

-- ---------------------------------------------------------------- chat
create table if not exists conversaciones (
  id uuid primary key default gen_random_uuid(),
  usuario text not null,
  titulo text,
  mensajes jsonb not null default '[]'::jsonb,
  creado timestamptz not null default now(),
  actualizado timestamptz not null default now(),
  revisado boolean not null default false,
  nota text,
  borrada timestamptz                              -- (15/10) papelera: cuándo se borró; null = viva
);
create index if not exists conversaciones_usuario_actualizado_idx on conversaciones (usuario, actualizado desc);
create index if not exists conversaciones_borrada_idx on conversaciones (borrada);
alter table conversaciones enable row level security;

create table if not exists uso_openai (
  id uuid primary key default gen_random_uuid(),
  creado timestamptz not null default now(),
  usuario text,
  modelo text not null,
  que text not null,                               -- chat | auxiliar | embedding
  tokens_entrada integer not null default 0,
  tokens_salida integer not null default 0,
  tokens_cache integer not null default 0
);
create index if not exists uso_openai_creado_idx on uso_openai (creado desc);
alter table uso_openai enable row level security;

-- ---------------------------------------------------------------- publicación
create table if not exists publicaciones (
  id uuid primary key default gen_random_uuid(),
  creado timestamptz not null default now(),
  usuario text not null,
  canal text not null,                             -- clave de canales.py (wordpress, instagram, facebook, youtube, mail, home, whatsapp, newsletter)
  modo text not null,
  titulo text,
  texto text,
  imagen_url text,
  fecha_programada timestamptz,
  estado text not null default 'registrada',       -- borrador, prueba, a_aprobar, pendiente, procesando, enviando, publicada, simulada, rechazada, cancelada, error, lista…
  resultado jsonb not null default '{}'::jsonb,
  procesado_en timestamptz,
  intentos integer not null default 0,
  compartido boolean not null default false
);
comment on table publicaciones is 'Registro de cada intento de publicación desde la pestaña Publicar del chatbot (simulado, borrador o real). Semilla de la cola de publicación.';
comment on column publicaciones.compartido is '(2/11) la persona dueña la comparte con el equipo: aparece en Mis publicaciones → Del equipo de las demás (solo lectura), como clips.compartido';
create index if not exists publicaciones_creado_idx on publicaciones (creado desc);
create index if not exists publicaciones_pendientes on publicaciones (fecha_programada) where estado = 'pendiente';
alter table publicaciones enable row level security;

create table if not exists clips (
  id uuid primary key default gen_random_uuid(),
  creado timestamptz default now(),
  video_id text not null,
  inicio_ms integer not null,
  fin_ms integer not null,
  titulo text,
  pedido_por text,
  estado text not null default 'pedido',           -- pedido | listo | error
  url text,
  error text,
  procesado_en timestamptz,
  formato text not null default 'horizontal',      -- horizontal | vertical
  srt text,
  srt_editado text,
  nota text,
  edicion jsonb,
  estilo jsonb,
  compartido boolean not null default false
);
comment on column clips.compartido is '(2/11) true = el dueño lo compartió con el equipo: aparece en «Del equipo» y se puede guardar en proyectos ajenos';
create unique index if not exists clips_tramo_idx on clips (video_id, inicio_ms, fin_ms, formato);
alter table clips enable row level security;

-- ---------------------------------------------------------------- configuración
create table if not exists config (
  clave text primary key,
  valor jsonb not null,
  actualizado timestamptz not null default now(),
  por text
);
alter table config enable row level security;

-- ---------------------------------------------------------------- Frase del día
create table if not exists frases (
  id uuid primary key default gen_random_uuid(),
  texto text not null,
  autor text,
  origen text not null default 'sheet',
  validada boolean not null default false,
  fecha date unique,                               -- un día tiene una sola frase
  imagen_url text,
  estado text not null default 'programada',       -- programada | saltada | publicada | simulada
  publicacion_id uuid,
  orden integer,
  fuente text,
  tema text,
  creado timestamptz not null default now(),
  actualizado timestamptz not null default now(),
  ultima_publicada timestamptz,
  veces_publicada integer not null default 0,
  piezas jsonb,                                    -- {salida: publicacion_id} (historia, instagram, facebook, mail, home, whatsapp)
  estilo jsonb
);
comment on column frases.estilo is '(2/11) estilo de la imagen compuesta propio de esta frase (logo, posicion_logo, tipografia, peso, posicion, alineacion); pisa el global de config frase_estilo. null = el global';
create unique index if not exists frases_texto_idx on frases (texto);
create index if not exists frases_fecha_idx on frases (fecha);
create index if not exists frases_ultima_publicada_idx on frases (ultima_publicada nulls first);
alter table frases enable row level security;

create table if not exists frase_envios (
  id uuid primary key default gen_random_uuid(),
  publicacion_id uuid references publicaciones(id) on delete set null,
  fecha date not null,
  email text not null,
  estado text not null default 'pendiente',        -- pendiente | enviado | error
  prueba boolean not null default false,
  enviado_en timestamptz,
  error text,
  creado timestamptz not null default now()
);
create index if not exists frase_envios_pieza_estado on frase_envios (publicacion_id, estado);
create index if not exists frase_envios_fecha on frase_envios (fecha);
alter table frase_envios enable row level security;

create table if not exists frase_solicitudes (
  id uuid primary key default gen_random_uuid(),
  creado timestamptz not null default now(),
  usuario text not null,
  fecha date not null,
  frase_id uuid references frases(id) on delete set null,
  texto text,
  autor text,
  nota text,
  estado text not null default 'pendiente',        -- pendiente | aceptada | rechazada
  resuelta_por text,
  resuelta_en timestamptz,
  respuesta text,
  imagen_url text
);
comment on table frase_solicitudes is '(2/11) pedidos de cambio del calendario de la Frase del día hechos por creadores de contenido; los resuelve un aprobador';
comment on column frase_solicitudes.imagen_url is '(2/11) foto de fondo propuesta para ese día (URL); puede venir sola (cambiar solo la foto de la frase que ya está) o junto con la frase pedida';
create index if not exists frase_solicitudes_estado on frase_solicitudes (estado, creado desc);
create index if not exists frase_solicitudes_usuario on frase_solicitudes (usuario, creado desc);
-- (RLS deshabilitado en la base real; ver la nota de arriba)

-- ---------------------------------------------------------------- cuentas
create table if not exists usuarios (
  id uuid primary key default gen_random_uuid(),
  usuario text not null unique,
  email text unique,
  nombre text,
  rol text not null default 'creador' check (rol in ('creador', 'aprobador', 'admin')),
  clave_hash text,
  clave_temporal boolean not null default false,
  activo boolean not null default true,
  creado timestamptz not null default now(),
  actualizado timestamptz not null default now(),
  ultimo_login timestamptz,
  creado_por text
);
create index if not exists usuarios_email_idx on usuarios (lower(email));
alter table usuarios enable row level security;

create table if not exists usuarios_cambios (
  id bigserial primary key,
  cuando timestamptz not null default now(),
  quien text not null,
  accion text not null,
  usuario text,
  detalle jsonb
);
alter table usuarios_cambios enable row level security;

create table if not exists autorizados (                -- lista blanca del login con Google
  email text primary key,
  rol text not null default 'creador' check (rol in ('creador', 'aprobador', 'admin')),
  agregado_por text,
  creado timestamptz not null default now(),
  nota text
);
alter table autorizados enable row level security;

-- ---------------------------------------------------------------- proyectos (carpetas) y compartidos
create table if not exists proyectos (
  id uuid primary key default gen_random_uuid(),
  nombre text not null,
  descripcion text,
  dueno text not null,
  padre_id uuid references proyectos(id) on delete cascade,
  color text,
  emoji text,
  creado timestamptz not null default now(),
  actualizado timestamptz not null default now()
);
create index if not exists proyectos_dueno_idx on proyectos (dueno, actualizado desc);
create index if not exists proyectos_padre_idx on proyectos (padre_id);
alter table proyectos enable row level security;

create table if not exists proyecto_items (
  id uuid primary key default gen_random_uuid(),
  proyecto_id uuid not null references proyectos(id) on delete cascade,
  tipo text not null check (tipo in ('conversacion', 'recorte', 'pieza', 'imagen')),
  item_id text not null,
  datos jsonb,
  agregado_por text not null,
  agregado timestamptz not null default now(),
  unique (proyecto_id, tipo, item_id)
);
create index if not exists proyecto_items_item_idx on proyecto_items (tipo, item_id);
alter table proyecto_items enable row level security;

create table if not exists compartidos (
  id uuid primary key default gen_random_uuid(),
  tipo text not null check (tipo in ('proyecto', 'conversacion')),
  item_id text not null,
  con_usuario text not null,
  permiso text not null default 'ver' check (permiso in ('ver', 'editar')),
  compartido_por text not null,
  creado timestamptz not null default now(),
  unique (tipo, item_id, con_usuario)
);
create index if not exists compartidos_con_idx on compartidos (con_usuario);
create index if not exists compartidos_item_idx on compartidos (tipo, item_id);
alter table compartidos enable row level security;

-- ---------------------------------------------------------------- administración: servicios y salud
create table if not exists servicios (
  id uuid primary key default gen_random_uuid(),
  nombre text not null,
  proveedor text,
  para_que text,
  plan text,
  costo_mensual_usd numeric(10,2),
  confirmado boolean not null default false,
  desde date,
  url text,
  notas text,
  activo boolean not null default true,
  actualizado_por text,
  actualizado timestamptz not null default now()
);
alter table servicios enable row level security;

create table if not exists salud_historial (
  id bigserial primary key,
  creado timestamptz not null default now(),
  estado text not null,
  detalle jsonb not null default '{}'::jsonb
);
create index if not exists salud_historial_creado on salud_historial (creado desc);
alter table salud_historial enable row level security;

create or replace function tamano_base() returns jsonb language sql stable security definer as $$
  select jsonb_build_object(
    'bytes', pg_database_size(current_database()),
    'tablas', (select jsonb_object_agg(c.relname, jsonb_build_object('filas', c.reltuples::bigint, 'bytes', pg_total_relation_size(c.oid)))
               from pg_class c join pg_namespace n on n.oid = c.relnamespace
               where n.nspname = 'public' and c.relkind = 'r')
  )
$$;

-- ---------------------------------------------------------------- búsqueda en Postgres (VECTORES=supabase / LEXICO=supabase)
create or replace function fva_unaccent(t text) returns text language sql immutable parallel safe as
$$ select extensions.unaccent('extensions.unaccent'::regdictionary, t) $$;

create table if not exists fragmentos_emb (
  idx integer primary key,                         -- posición en fragmentos.jsonl
  fragmento_id text not null unique,
  documento_id text,
  texto text,
  embedding extensions.vector(512) not null,
  tsv tsvector generated always as (to_tsvector('spanish'::regconfig, fva_unaccent(coalesce(texto, '')))) stored
);
create index if not exists fragmentos_emb_hnsw on fragmentos_emb using hnsw (embedding extensions.vector_cosine_ops);
create index if not exists fragmentos_emb_tsv on fragmentos_emb using gin (tsv);
alter table fragmentos_emb enable row level security;

create or replace function match_fragmentos(query_embedding extensions.vector, k integer default 300)
returns table(idx integer, fragmento_id text, similitud double precision) language plpgsql stable as $$
begin
  perform set_config('hnsw.ef_search', greatest(k, 40)::text, true);
  return query
    select f.idx, f.fragmento_id, (1 - (f.embedding operator(extensions.<=>) query_embedding))::float
    from public.fragmentos_emb f
    order by f.embedding operator(extensions.<=>) query_embedding
    limit k;
end $$;

create or replace function match_fragmentos_varios(query_embeddings jsonb, k integer default 300)
returns table(idx integer, similitud double precision) language sql stable as $$
  select m.idx, max(m.similitud)
  from jsonb_array_elements(query_embeddings) e,
       lateral public.match_fragmentos((e::text)::extensions.vector(512), k) m
  group by m.idx
  order by 2 desc
$$;

create or replace function match_lexico(consulta text, k integer default 300)
returns table(idx integer, rank double precision) language sql stable as $$
  with q as (
    select string_agg('''' || replace(lexeme, '''', '') || '''', ' | ')::tsquery as tq
    from unnest(tsvector_to_array(to_tsvector('spanish', public.fva_unaccent(coalesce(consulta, ''))))) lexeme
  )
  select f.idx, ts_rank_cd(f.tsv, q.tq)::float
  from public.fragmentos_emb f, q
  where q.tq is not null and f.tsv @@ q.tq
  order by 2 desc
  limit k
$$;
