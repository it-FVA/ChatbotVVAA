# Migraciones históricas (hasta el 3/11/2026)

Las migraciones que se aplicaron a mano en Supabase antes de que existiera el registro. **Ya están incluidas en
`../000_esquema_base.sql`**: no se vuelven a correr en una base nueva. Quedan como historia de por qué existe cada cosa.

| Archivo | Aplicada (versión en `supabase_migrations`) |
|---|---|
| `autorizados_login_google.sql` | 21/10 (`20261021193036`) |
| `salud_historial.sql` | 22/10 (`20261022024239`) |
| `fragmentos_emb_pgvector.sql` | 22/10 (`20261022025259`, `20261022025944` tamano_base) |
| `usuarios_y_lista_blanca.sql` | 22/10 (`20261022032058`) |
| `proyectos_y_compartidos.sql` | 22/10 (`20261022122514`) |
| `clips_compartido.sql` | 2/11 (`20261102141337`) |
| `frase_solicitudes.sql` | 2/11 (`20261102144921`) |
| `frase_solicitudes_foto.sql` | 2/11 (`20261102162927`) |
| `frases_estilo.sql` | 2/11 (`20261102195041`) |
| `publicaciones_compartido.sql` | 2/11 (`20261103024637`) |

Las tablas `conversaciones`, `publicaciones`, `clips`, `config`, `frases`, `frase_envios`, `servicios` y `uso_openai` nunca tuvieron
archivo en el repo (se crearon desde el SQL Editor o el MCP: `crear_publicaciones` 24/9, `cola_publicaciones` 24/9,
`conversaciones_papelera` 15/10, `clips_*` 15 y 19/10, `config_tabla_y_clips_estilo` 19/10, `frases_del_dia` 19/10,
`frases_rotacion_y_canales` 19/10, `uso_openai` 21/10, `servicios_costos` 22/10, `frase_envios_mail` 26/10). Su DDL real está en
`000_esquema_base.sql`.
