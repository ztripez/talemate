/**
 * Template icon and color mappings
 * Used for displaying template types consistently across the application
 */

/**
 * Resolve the Material Design icon for a template type.
 *
 * @param {{template_type?: string}} template - Template whose registered type is displayed.
 * @returns {string} Registered icon name, or `mdi-cube-scan` for unknown types.
 */
export function iconForTemplate(template) {
    const templateType = template.template_type;
    
    if (templateType == 'character_attribute') {
        return 'mdi-badge-account';
    } else if (templateType == 'character_detail') {
        return 'mdi-account-details';            
    } else if (templateType == 'state_reinforcement') {
        return 'mdi-image-auto-adjust';
    } else if (templateType == 'spices') {
        return 'mdi-chili-mild';
    } else if (templateType == 'writing_style') {
        return 'mdi-script-text';
    } else if (templateType == 'visual_style') {
        return 'mdi-palette';
    } else if (templateType == 'agent_persona') {
        return 'mdi-drama-masks';
    } else if (templateType == 'scene_type') {
        return 'mdi-movie-open';
    } else if (templateType == 'game_primitive_bundle') {
        return 'mdi-package-variant-closed';
    }
    return 'mdi-cube-scan';
}

/**
 * Resolve the theme color for a template type.
 *
 * @param {{template_type?: string}} template - Template whose registered type is displayed.
 * @returns {string} Registered theme color, or `grey` for unknown types.
 */
export function colorForTemplate(template) {
    const templateType = template.template_type;
    
    if (templateType == 'character_attribute') {
        return 'highlight1';
    } else if (templateType == 'character_detail') {
        return 'highlight2';
    } else if (templateType == 'state_reinforcement') {
        return 'highlight3';
    } else if (templateType == 'spices') {
        return 'highlight4';
    } else if (templateType == 'writing_style') {
        return 'highlight5';
    } else if (templateType == 'visual_style') {
        return 'highlight5';
    } else if (templateType == 'agent_persona') {
        return 'persona';
    } else if (templateType == 'scene_type') {
        return 'highlight6';
    } else if (templateType == 'game_primitive_bundle') {
        return 'secondary';
    }
    return 'grey';
}
