-- (22/10, gestión de usuarios de la interfaz nueva) Tabla `usuarios` con contraseña hasheada (bcrypt) y la tabla
-- `autorizados` convertida en LISTA BLANCA (email + rol + nota). Un email del dominio DOMINIO_FVA entra siempre;
-- cualquier otro, solo si está en la lista. Correr UNA vez en Supabase (SQL Editor o apply_migration
-- `usuarios_y_lista_blanca`). Es idempotente.
--
-- Transición: mientras una persona NO esté en `usuarios`, la API sigue buscándola en [usuarios]/USUARIOS_JSON
-- (secrets) y su rol en APROBADORES/ADMINS, como hasta ahora. `api/importar_usuarios.py` pasa a todos a la tabla.

create table if not exists usuarios (
  id uuid primary key default gen_random_uuid(),
  usuario text not null unique,                 -- siempre en minúsculas; para las cuentas de Google puede ser el email
  email text unique,                            -- nullable: los usuarios viejos no tienen
  nombre text,
  rol text not null default 'creador' check (rol in ('creador', 'aprobador', 'admin')),
  clave_hash text,                              -- bcrypt; null = «sin clave» (la crea desde «¿Primera vez?»)
  clave_temporal boolean not null default false,-- true = la clave la puso un admin; hay que cambiarla al entrar
  activo boolean not null default true,
  creado timestamptz not null default now(),
  actualizado timestamptz not null default now(),
  ultimo_login timestamptz,
  creado_por text                               -- quién la creó: 'importar_usuarios', 'primera_vez', 'google' o un admin
);
create index if not exists usuarios_email_idx on usuarios (lower(email));

-- Registro de cambios hechos por admins (quién, qué, a quién).
create table if not exists usuarios_cambios (
  id bigserial primary key,
  cuando timestamptz not null default now(),
  quien text not null,
  accion text not null,                         -- crear, rol, renombrar, activar, desactivar, clave, borrar, lista_alta, lista_baja...
  usuario text,                                 -- a quién (usuario o email)
  detalle jsonb
);

-- La lista blanca: `autorizados` suma el rol admin y una nota.
alter table autorizados drop constraint if exists autorizados_rol_check;
alter table autorizados add constraint autorizados_rol_check check (rol in ('creador', 'aprobador', 'admin'));
alter table autorizados add column if not exists nota text;
