-- (05/11) banco_imagenes: registro de las imágenes del banco que banco.sincronizar_banco ya subió desde Drive a la biblioteca de
-- WordPress (una fila por archivo de Drive). Sirve para no subir dos veces lo mismo y para re-subir si cambia modifiedTime. Pedido: Franco y
-- Julián (3/11), «Banco de Imágenes» en la carpeta compartida de Drive.
-- Aplicar con `python api/migrar.py --aplicar` (o SQL Editor + `--registrar 20261105_0045_banco_imagenes`). Idempotente (if not exists).
-- Después hay que correr las líneas de banco_imagenes de api/migraciones/manual_cola_rol.sql si el rol «cola» ya existe (la cola sube el banco).

create table if not exists public.banco_imagenes (
  drive_id      text primary key,
  nombre        text not null,
  modified_time text,
  wp_id         bigint,
  url           text,
  formato       text,
  etiquetas     jsonb not null default '[]'::jsonb,
  subido_en     timestamptz not null default now()
);
create index if not exists banco_imagenes_formato_idx on public.banco_imagenes (formato);
create index if not exists banco_imagenes_subido_idx on public.banco_imagenes (subido_en desc);
