-- (05/11) banco_imagenes quedó sin Row Level Security al crearla (20261105_0045); las demás tablas lo tienen activo.
-- La API entra con la clave de servicio (salta RLS) y la cola con el rol «cola», que necesita la misma política que en las otras tablas.
-- Aplicar en el SQL Editor de Supabase y registrar con `python api/migrar.py --registrar 20261105_1900_banco_imagenes_rls`.
-- Idempotente.

alter table public.banco_imagenes enable row level security;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'cola')
     and not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'banco_imagenes' and policyname = 'cola_todo') then
    create policy cola_todo on public.banco_imagenes for all to cola using (true) with check (true);
  end if;
end $$;
