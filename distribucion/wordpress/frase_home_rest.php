<?php
// (2/11) Frase del día en la home de viviragradecidos.org — snippet para el plugin Code Snippets (ya instalado y activo).
//
// Qué hay hoy en el sitio (visto el 2/11 por la API): la home es la página «home 2026» (id 64008), armada con Elementor.
// La sección «Frase del Día» es un widget Posts de Elementor Pro que lista la ÚLTIMA entrada del tipo de contenido «frase»
// (post type `frase`, por ejemplo la entrada 53493: «El vivir agradecidos nos ayuda a darnos cuenta… —David Steindl-Rast»).
// Antes Maxi entraba a WordPress y cargaba esa entrada a mano. Ese tipo de contenido NO está expuesto en la API REST
// (wp-json/wp/v2/types no lo lista), así que la plataforma no puede crearla… hasta que este snippet lo exponga.
//
// Qué hace: con `show_in_rest`, WordPress publica wp-json/wp/v2/frase (leer, crear, editar; crear y editar solo con la
// contraseña de aplicación del usuario administrador que ya usa la plataforma). No cambia nada de lo que se ve en el sitio.
// Qué usa: publicar.publicar_frase_home (ChatbotVVAA), que la cola llama para el canal «home» de la Frase del día
// (Administración → Configuración → Frase del día → canales).
//
// Cómo instalarlo (lo hace Franco; la plataforma no tiene permiso para escribir snippets):
//   WordPress → Snippets → Añadir nuevo → nombre «Frase del día en la API (home)» → pegar el código de abajo (sin la
//   línea <?php) → Ámbito: «Ejecutar en todas partes» → Guardar cambios y activar.
//   Verificar: https://viviragradecidos.org/wp-json/wp/v2/frase?per_page=3 tiene que devolver las últimas frases.
//   Para volver atrás: desactivar el snippet.

add_filter( 'register_post_type_args', function ( $args, $post_type ) {
    if ( 'frase' === $post_type ) {
        $args['show_in_rest']          = true;
        $args['rest_base']             = 'frase';
        $args['rest_controller_class'] = 'WP_REST_Posts_Controller';
    }
    return $args;
}, 10, 2 );
