-- (08/11, Franco) Métricas: la app como centro de métricas de campañas. Una fila por CAPTURA (se guarda la historia);
-- «la última» de cada (ambito, ref, fuente) es la que muestra la pantalla. Contrato: web/maquetas/metricas-contrato.md.
-- Aplicar en el SQL Editor de Supabase y registrar con `python api/migrar.py --registrar 20261108_1200_metricas`.
-- Idempotente.

create table if not exists public.metricas (
  id uuid primary key default gen_random_uuid(),
  creado timestamptz not null default now(),
  ambito text not null check (ambito in ('pieza', 'canal', 'resumen')),
  ref text not null,                 -- pieza: publicaciones.id · canal: clave del canal (instagram, facebook…) · resumen: proyecto_id o 'sueltas'
  canal text,                        -- en pieza y canal, siempre; en resumen, null
  fuente text not null check (fuente in ('api', 'manual', 'ia')),
  periodo_desde date,                -- canal: qué período cubren los números (manual: lo que cargó la persona; api: la ventana pedida)
  periodo_hasta date,
  datos jsonb not null default '{}', -- números normalizados + crudo + errores (ver el contrato)
  nota text,
  por text,                          -- quién cargó (usuario) o 'cola' / 'api' / 'ia'
  capturado timestamptz not null default now()
);

create index if not exists metricas_ref_idx on public.metricas (ambito, ref, fuente, capturado desc);

alter table public.metricas enable row level security;

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'cola')
     and not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'metricas' and policyname = 'cola_todo') then
    create policy cola_todo on public.metricas for all to cola using (true) with check (true);
  end if;
end $$;
