-- MANUAL · NO LA APLICA api/migrar.py (el nombre empieza con «manual_»: el patrón de migrar.py solo toma 000_… y AAAAMMDD_HHMM_…).
-- (3/11, revisión de código 5.3 punto 21) Rol de Postgres «cola» con permisos SOLO sobre lo que necesita la cola de
-- publicación y el recorte de clips. Hoy GitHub Actions guarda la clave service_role de Supabase: si se filtran los secrets del
-- repo, dan acceso total a la base (usuarios con sus hashes, conversaciones, todo). Con esta clave acotada, una fuga solo
-- alcanza publicaciones, frases, frase_envios, config, clips, banco_imagenes y (lectura) migraciones.
--
-- (5/11) Si ya estaba aplicada: volver a correrlo (es idempotente) DESPUÉS de aplicar la migración 20261105_0045_banco_imagenes, que crea la
-- tabla banco_imagenes que ahora usa la cola. Si la tabla no existe todavía, el grant de esa línea falla.
--
-- NO está aplicada. Pasos (en este orden; nada se corta si algo falla: la cola sigue con SUPABASE_KEY hasta que exista el secret):
--
--  1. Supabase → SQL Editor → pegar ESTE archivo y correrlo. Es idempotente (se puede correr dos veces).
--  2. Supabase → Project Settings → API → «JWT Secret» (el secreto legado de firma). Copiarlo SOLO a una variable de entorno de
--     tu terminal, nunca a un archivo del repo:
--         set SUPABASE_JWT_SECRET=...            (PowerShell: $env:SUPABASE_JWT_SECRET = "...")
--     Si el panel solo ofrece «JWT Signing Keys» (el sistema nuevo) y no muestra el secreto legado, hay que pasar el proyecto a
--     «Legacy JWT secret» o firmar con la clave que corresponda: en ese caso avisar antes de seguir.
--  3. Generar la clave (un JWT con role = cola, vence a los 5 años):
--         python api/generar_clave_cola.py
--     Imprime la clave una sola vez. No queda guardada en ningún lado.
--  4. Probarla antes de usarla (reemplazar URL y CLAVE):
--         curl -s -H "apikey: CLAVE" -H "Authorization: Bearer CLAVE" "URL/rest/v1/config?select=clave&limit=1"   → 200 con filas
--         curl -s -H "apikey: CLAVE" -H "Authorization: Bearer CLAVE" "URL/rest/v1/usuarios?select=usuario&limit=1" → 401/403 «permission denied»
--  5. GitHub → el repo → Settings → Secrets and variables → Actions → New repository secret:  SUPABASE_KEY_COLA = la clave.
--     (cola.yml y db/_cliente.py ya la usan cuando existe: ver variables_entorno.py.)
--  6. Actions → cola-de-publicacion → Run workflow, y mirar el log: tiene que listar «pendientes vencidas» sin errores 401/403.
--     Un paso queda afuera a propósito: la papelera de conversaciones (vaciar_papelera_vencida) borra de `conversaciones`; con esta
--     clave ese paso imprime «papelera: no pude vaciar» y sigue. Si se quiere que la cola siga vaciándola, descomentar el bloque
--     «OPCIONAL» de más abajo.
--  7. Recién con la cola andando con la clave nueva: en GitHub borrar el secret SUPABASE_KEY (o dejarlo solo para el workflow
--     recortar-pendientes, que también usa `clips` y `config`: puede pasar a SUPABASE_KEY_COLA con el mismo cambio de una línea).
--  8. Marcar como aplicada en la tabla de migraciones (opcional, solo para que quede el registro):
--         python api/migrar.py --registrar manual_cola_rol

-- ---------------------------------------------------------------------------------------------------------------------
-- El rol. NOLOGIN: nadie entra a Postgres con él; solo PostgREST lo asume cuando el JWT trae role = cola.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'cola') then
    create role cola nologin noinherit;
  end if;
end $$;

-- PostgREST se conecta como «authenticator» y cambia al rol del JWT: necesita poder hacerlo.
grant cola to authenticator;
grant usage on schema public to cola;

-- Permisos: lo que la cola hace de verdad (leer y marcar publicaciones, encolar y marcar frases y envíos de mail, leer la config,
-- recortar clips). migraciones solo en lectura.
grant select, insert, update, delete on public.publicaciones to cola;
grant select, insert, update, delete on public.frases        to cola;
grant select, insert, update, delete on public.frase_envios  to cola;
grant select, insert, update, delete on public.config        to cola;
grant select, insert, update, delete on public.clips         to cola;
grant select, insert, update, delete on public.banco_imagenes to cola;   -- (5/11) la cola sincroniza el banco de imágenes desde Drive
grant select                         on public.migraciones   to cola;

-- Si alguna de esas tablas tiene un id con secuencia (serial o identity), el INSERT necesita usarla.
do $$
declare
  r record;
  seq text;
begin
  for r in
    select table_name, column_name
    from information_schema.columns
    where table_schema = 'public'
      and table_name in ('publicaciones', 'frases', 'frase_envios', 'config', 'clips', 'banco_imagenes')
      and (column_default like 'nextval(%' or is_identity = 'YES')
  loop
    seq := pg_get_serial_sequence('public.' || quote_ident(r.table_name), r.column_name);
    if seq is not null then
      execute format('grant usage, select on sequence %s to cola', seq);
    end if;
  end loop;
end $$;

-- Si las tablas tienen RLS activado, un rol que no es service_role no pasa sin una política. Estas dejan pasar al rol cola y a nadie
-- más (no cambian nada para la API ni para la web, que usan service_role y se saltean RLS). Si RLS está apagado, no hacen nada.
do $$
declare t text;
begin
  foreach t in array array['publicaciones', 'frases', 'frase_envios', 'config', 'clips', 'banco_imagenes'] loop
    execute format('drop policy if exists cola_todo on public.%I', t);
    execute format('create policy cola_todo on public.%I for all to cola using (true) with check (true)', t);
  end loop;
  drop policy if exists cola_lee on public.migraciones;
  create policy cola_lee on public.migraciones for select to cola using (true);
end $$;

-- ---------------------------------------------------------------------------------------------------------------------
-- OPCIONAL (descomentar solo si se quiere que la cola siga vaciando la papelera de conversaciones a los 30 días; es un permiso de
-- BORRADO sobre conversaciones que hoy este rol NO tiene):
-- grant select, delete on public.conversaciones to cola;
-- drop policy if exists cola_papelera on public.conversaciones;
-- create policy cola_papelera on public.conversaciones for all to cola using (true) with check (true);

-- Para deshacer todo (por ejemplo si hay que volver a service_role): borrar el secret SUPABASE_KEY_COLA de GitHub y después
--   revoke all on all tables in schema public from cola; revoke usage on schema public from cola; revoke cola from authenticator;
--   drop owned by cola; drop role cola;
