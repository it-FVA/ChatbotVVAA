<?php
// (2/11) Frase del día en la home de viviragradecidos.org — snippet «Frase del día en la API (home)» (id 8) del plugin
// Code Snippets, activo en el sitio desde el 2/11/2026 (lo cargó Claude desde el Chrome de Franco, con su OK).
//
// Qué hay en el sitio (visto el 2/11): la home es la página «home 2026» (id 64008), armada con Elementor. La sección
// «Frase del Día» es un widget Posts de Elementor Pro que lista la ÚLTIMA entrada del tipo de contenido `frase` (por
// ejemplo la 53493: «El vivir agradecidos nos ayuda a darnos cuenta… —David Steindl-Rast»). Antes Maxi la cargaba a mano.
// Sorpresa: ese tipo de contenido YA NO ESTÁ REGISTRADO (wp-admin → edit.php?post_type=frase dice «Tipo de contenido no
// válido»; el plugin que lo registraba, seguramente Toolset Types, está desactivado). Las entradas siguen en la base y el
// widget las lista igual, pero no se pueden crear ni editar desde el escritorio ni por la API.
//
// Qué hace: registra el tipo `frase` otra vez (menú «Frases del día» en el escritorio, con título, texto y extracto) y lo
// expone en la API REST (wp-json/wp/v2/frase; crear y editar solo con la contraseña de aplicación del administrador que
// usa la plataforma). No es público en el sitio (sin URL propia ni archivo, como estaba): solo lo muestra la home.
// Qué lo usa: publicar.publicar_frase_home (ChatbotVVAA), que la cola llama para el canal «home» de la Frase del día
// (Administración → Configuración → Frase del día → canales).
//
// Mantenimiento: WordPress → Snippets → «Frase del día en la API (home)». Para volver atrás: desactivarlo (las entradas
// quedan en la base y la home las sigue mostrando). Verificar: https://viviragradecidos.org/wp-json/wp/v2/frase?per_page=3

add_action( 'init', function () {
    if ( post_type_exists( 'frase' ) ) {
        return;
    }
    register_post_type( 'frase', array(
        'label'                 => 'Frases del día',
        'labels'                => array(
            'name'          => 'Frases del día',
            'singular_name' => 'Frase del día',
            'add_new_item'  => 'Añadir frase del día',
            'edit_item'     => 'Editar frase del día',
            'menu_name'     => 'Frases del día',
        ),
        'description'           => 'La frase que muestra la sección «Frase del Día» de la home (sale la última publicada). Las carga la plataforma cada día.',
        'public'                => false,
        'show_ui'               => true,
        'show_in_menu'          => true,
        'show_in_rest'          => true,
        'rest_base'             => 'frase',
        'rest_controller_class' => 'WP_REST_Posts_Controller',
        'exclude_from_search'   => true,
        'publicly_queryable'    => false,
        'has_archive'           => false,
        'rewrite'               => false,
        'menu_icon'             => 'dashicons-format-quote',
        'menu_position'         => 21,
        'supports'              => array( 'title', 'editor', 'excerpt', 'author' ),
        'capability_type'       => 'post',
        'map_meta_cap'          => true,
    ) );
}, 5 );
