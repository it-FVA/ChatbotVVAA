-- (25/11) Banco de imágenes: la sincronización comparaba modifiedTime de Drive y, cuando Julián volvía a tocar un archivo,
-- lo subía de nuevo a WordPress como imagen nueva (65 medios para 36 fotos). Ahora compara el md5Checksum de Drive: si el
-- contenido no cambió, no sube; si cambió, sube el nuevo y borra el medio anterior. El rol `cola` ya tiene permisos sobre la
-- tabla (manual_cola_rol.sql). Idempotente. Aplicada con el MCP de Supabase el 25/11.
alter table public.banco_imagenes add column if not exists md5 text;
comment on column public.banco_imagenes.md5 is '(25/11) md5Checksum de Drive del archivo subido: si no cambia, no se vuelve a subir aunque cambie modifiedTime (antes se duplicaba en WordPress)';
