-- (22/10) Búsqueda vectorial y léxica en Postgres para bajar la memoria de la API (VECTORES=supabase / LEXICO=supabase en nucleo.py).
-- Aplicada en Supabase (proyecto khgfqklieprcpxryqhtu) el 22/10/2026 con el MCP de Supabase. Los datos los sube subir_embeddings.py.
create extension if not exists vector with schema extensions;
create extension if not exists unaccent with schema extensions;

-- unaccent() es STABLE; para usarlo en una columna generada hace falta un envoltorio IMMUTABLE (truco estándar).
create or replace function public.fva_unaccent(t text) returns text
language sql immutable parallel safe as $$ select extensions.unaccent('extensions.unaccent'::regdictionary, t) $$;

create table if not exists public.fragmentos_emb (
  idx integer primary key,                 -- posición en fragmentos.jsonl (el índice de nucleo._FRS)
  fragmento_id text not null unique,
  documento_id text,
  texto text,
  embedding extensions.vector(512) not null, -- text-embedding-3-small, 512 dim, normalizado (= fragmentos_openai.npy)
  tsv tsvector generated always as (to_tsvector('spanish', public.fva_unaccent(coalesce(texto, '')))) stored
);
create index if not exists fragmentos_emb_hnsw on public.fragmentos_emb using hnsw (embedding extensions.vector_cosine_ops);
create index if not exists fragmentos_emb_tsv on public.fragmentos_emb using gin (tsv);
alter table public.fragmentos_emb enable row level security;

-- Los k fragmentos más parecidos (coseno). ef_search >= k: con HNSW el índice no devuelve más filas que ef_search.
create or replace function public.match_fragmentos(query_embedding extensions.vector(512), k int default 300)
returns table (idx int, fragmento_id text, similitud float)
language plpgsql stable as $$
begin
  perform set_config('hnsw.ef_search', greatest(k, 40)::text, true);
  return query
    select f.idx, f.fragmento_id, (1 - (f.embedding operator(extensions.<=>) query_embedding))::float
    from public.fragmentos_emb f
    order by f.embedding operator(extensions.<=>) query_embedding
    limit k;
end $$;

-- Varias consultas a la vez (la consulta, su traducción al inglés, la expansión): fusión por máximo, como hace nucleo._buscar.
create or replace function public.match_fragmentos_varios(query_embeddings jsonb, k int default 300)
returns table (idx int, similitud float)
language sql stable as $$
  select m.idx, max(m.similitud)
  from jsonb_array_elements(query_embeddings) e,
       lateral public.match_fragmentos((e::text)::extensions.vector(512), k) m
  group by m.idx
  order by 2 desc
$$;

-- Búsqueda léxica (reemplazo de BM25): OR de los lexemas en español sin tildes, ranking ts_rank_cd.
create or replace function public.match_lexico(consulta text, k int default 300)
returns table (idx int, rank float)
language sql stable as $$
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
