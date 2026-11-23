-- (23/11) Frase del día, segunda etapa («Daily practice», Beto 18/11): cada frase puede traer una práctica del día y el texto
-- original en inglés (las 998 de Grateful Living, curadas por Pato el 21/11, entran como Pendiente: no van al calendario).
-- Solo lectura por ahora: la pieza de Instagram y el mail siguen igual hasta el diseño de Julián y el OK de Beto.
-- Grants: el rol `cola` tiene select/insert/update/delete sobre la TABLA frases (manual_cola_rol.sql), así que las columnas
-- nuevas quedan cubiertas sin grant aparte. Idempotente.
alter table public.frases add column if not exists practica text;
alter table public.frases add column if not exists texto_original text;
comment on column public.frases.practica is '(23/11) práctica del día que acompaña a la frase (modelo «Daily practice» de Grateful Living); null = sin práctica';
comment on column public.frases.texto_original is '(23/11) texto original en inglés cuando la frase es una traducción (Grateful Living 2026)';
