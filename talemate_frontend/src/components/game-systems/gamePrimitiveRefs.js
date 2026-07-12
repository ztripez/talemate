function segment(value, label) {
    const normalized = String(value ?? '').trim();
    if (!normalized || normalized.includes('/') || normalized.includes(':')) {
        throw new Error(`${label} must be a non-empty canonical path segment`);
    }
    return normalized;
}

/**
 * Build the canonical wire reference for an anchor.
 * @param {unknown} kind Anchor kind path segment.
 * @param {unknown} id Anchor identifier path segment.
 * @returns {string} Canonical `<kind>:<id>` anchor reference.
 * @throws {Error} A segment is empty or reserved, or a relationship ID is malformed.
 */
export function canonicalAnchorRef(kind, id) {
    const normalizedKind = segment(kind, 'Anchor kind');
    const normalizedId = segment(id, 'Anchor id');
    if (normalizedKind === 'relationship') {
        const participants = normalizedId.split('->').map((item) => item.trim());
        if (participants.length !== 2 || participants.some((item) => !item)) {
            throw new Error("Relationship anchor id must use '<source>-><target>' syntax");
        }
        return `${normalizedKind}:${participants.join('->')}`;
    }
    return `${normalizedKind}:${normalizedId}`;
}

/**
 * Build the canonical wire reference for a primitive instance.
 * @param {unknown} anchor Canonical anchor reference.
 * @param {unknown} kind Primitive kind path segment.
 * @param {unknown} id Primitive identifier path segment.
 * @returns {string} Canonical `<anchor>/<kind>/<id>` primitive reference.
 * @throws {Error} The anchor or any primitive segment is malformed.
 */
export function canonicalPrimitiveRef(anchor, kind, id) {
    const canonicalAnchor = parseAnchorRef(anchor).ref;
    return `${canonicalAnchor}/${segment(kind, 'Primitive kind')}/${segment(id, 'Primitive id')}`;
}

/**
 * Parse and normalize a canonical anchor wire reference.
 * @param {unknown} value Candidate anchor reference.
 * @returns {{kind: string, id: string, ref: string}} Parsed canonical reference.
 * @throws {Error} The value does not satisfy canonical anchor syntax.
 */
export function parseAnchorRef(value) {
    const normalized = String(value ?? '').trim();
    const match = /^([^/:]+):([^/:]+)$/.exec(normalized);
    if (!match) throw new Error("Anchor ref must use '<kind>:<id>' syntax");
    const ref = canonicalAnchorRef(match[1], match[2]);
    const separator = ref.indexOf(':');
    return { kind: ref.slice(0, separator), id: ref.slice(separator + 1), ref };
}

/**
 * Parse and normalize a canonical primitive wire reference.
 * @param {unknown} value Candidate primitive reference.
 * @returns {{anchor: string, anchorKind: string, anchorId: string, kind: string, id: string, ref: string}} Parsed canonical reference.
 * @throws {Error} The value does not satisfy canonical primitive syntax.
 */
export function parsePrimitiveRef(value) {
    const normalized = String(value ?? '').trim();
    const match = /^([^/]+)\/([^/]+)\/([^/]+)$/.exec(normalized);
    if (!match) throw new Error("Primitive ref must use '<anchor>/<kind>/<id>' syntax");
    const anchor = parseAnchorRef(match[1]);
    const kind = segment(match[2], 'Primitive kind');
    const id = segment(match[3], 'Primitive id');
    return { anchor: anchor.ref, anchorKind: anchor.kind, anchorId: anchor.id, kind, id, ref: `${anchor.ref}/${kind}/${id}` };
}
