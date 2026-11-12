-- (12/11) La cola (rol «cola») captura las métricas cada hora pero la migración del 8/11 creó la tabla con RLS y política y SIN el
-- grant: «permission denied for table metricas» en cada pasada (visto en el log de la cola el 12/11; no hubo capturas automáticas
-- del 8 al 12/11). Aplicar en el SQL Editor y registrar con `python api/migrar.py --registrar 20261112_1200_metricas_grant_cola`.
-- Idempotente.
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'cola') then
    grant select, insert, update on public.metricas to cola;
    grant select on public.proyecto_items to cola;   -- por si la cola necesita saber a qué campaña pertenece una pieza
    grant select on public.proyectos to cola;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'proyecto_items' and policyname = 'cola_lee') then
      create policy cola_lee on public.proyecto_items for select to cola using (true);
    end if;
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'proyectos' and policyname = 'cola_lee') then
      create policy cola_lee on public.proyectos for select to cola using (true);
    end if;
  end if;
end $$;
