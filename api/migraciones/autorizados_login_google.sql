-- (21/10, fase 0 de la API) Login con Google: además de las cuentas del dominio de la Fundación (DOMINIO_FVA),
-- entran los emails de esta lista, con su rol. La administra un aprobador (alta desde el panel: fase posterior).
-- Correr UNA vez en Supabase → SQL Editor (o con apply_migration, nombre `autorizados_login_google`).
-- Mientras la tabla no exista, el login con Google admite solo el dominio (db.autorizado falla y se ignora).
create table if not exists autorizados (
  email text primary key,
  rol text not null default 'creador' check (rol in ('creador', 'aprobador')),
  agregado_por text,
  creado timestamptz not null default now()
);
