-- (2/11, tarde) Reunión del 2/11, Julián (16:27): «no nos da la opción de, por cada frase, poner un fondo distinto»; Alberto:
-- poder cambiar la foto de fondo por frase desde la vista previa. Los aprobadores ya la cambian en el detalle del día;
-- ahora los creadores también la PROPONEN: una solicitud puede traer una foto (sola, para la frase que ya está ese día, o
-- junto con la frase pedida). Al aceptar, la foto queda guardada en la frase (frases.imagen_url) y la usan la imagen
-- compuesta, el mail y las redes.
-- Aplicada en Supabase (proyecto khgfqklieprcpxryqhtu) el 2/11/2026 con el MCP de Supabase.
alter table frase_solicitudes add column if not exists imagen_url text;
comment on column frase_solicitudes.imagen_url is '(2/11) foto de fondo propuesta para ese día (URL); puede venir sola (cambiar solo la foto de la frase que ya está) o junto con la frase pedida';
