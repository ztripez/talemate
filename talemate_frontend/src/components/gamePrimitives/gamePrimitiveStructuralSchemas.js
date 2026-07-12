import { z } from 'zod';

/** Validates a non-empty trimmed structural string owned by client-side forms. */
export const structuralStringSchema = z.string().trim().min(1);
/** Validates the render-policy wire value; the server owns the allowed registry. */
export const renderPolicySchema = structuralStringSchema;

/** Validates the exact meter definition shape sent to and received from the server. */
export const meterSchema = z.object({
    id: structuralStringSchema.refine((value) => !value.includes('/'), 'Must not contain /'),
    label: z.string().nullable(),
    min: z.number().finite(),
    max: z.number().finite(),
    value: z.number().finite(),
    render_policy: renderPolicySchema,
}).strict();
