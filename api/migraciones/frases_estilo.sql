-- (2/11, noche) Pedido de Franco: usar en la Frase del día las mismas herramientas de diseño de imagen que tiene Diseñar
-- (logo, posición del logo, tipografía, peso, posición y alineación del texto). Hasta hoy el estilo era uno solo para todas
-- las frases (config frase_estilo, Administración → Configuración → Estilo). Ahora cada frase puede tener el suyo, que pisa
-- el global campo por campo; null = el global. Lo usan la imagen compuesta (vista previa, mail, redes, cola).
-- Aplicada en Supabase (proyecto khgfqklieprcpxryqhtu) el 2/11/2026 con el MCP de Supabase.
alter table frases add column if not exists estilo jsonb;
comment on column frases.estilo is '(2/11) estilo de la imagen compuesta propio de esta frase (logo, posicion_logo, tipografia, peso, posicion, alineacion); pisa el global de config frase_estilo. null = el global';
