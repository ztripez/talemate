import { mount } from '@vue/test-utils';
import { defineComponent } from 'vue';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';

import { createWebsocketHarness } from '../../test/websocketHarness.js';
import { IndeterminateWebsocketRequestError, useCorrelatedWebsocketRequest } from './useCorrelatedWebsocketRequest.js';

const responseSchema = z.object({
    type: z.literal('world_state_manager'), action: z.literal('completed'), request_id: z.string(),
    revision: z.string().min(1),
}).strict();

function mountTransport(options = {}) {
    const websocket = createWebsocketHarness();
    const Host = defineComponent({ setup: () => useCorrelatedWebsocketRequest(options), template: '<div />' });
    return { websocket, wrapper: mount(Host, { global: { provide: websocket.provide } }) };
}

function request(wrapper) {
    return wrapper.vm.request({ action: 'mutate', responseAction: 'completed', schema: responseSchema });
}

describe('useCorrelatedWebsocketRequest', () => {
    afterEach(() => vi.useRealTimers());

    it('rejects send exceptions, timeout, and socket closure', async () => {
        const sent = mountTransport();
        sent.websocket.websocket.send.mockImplementationOnce(() => { throw new Error('send failed'); });
        await expect(request(sent.wrapper)).rejects.toThrow('send failed');
        sent.wrapper.unmount();

        vi.useFakeTimers();
        const timed = mountTransport({ timeoutMs: 25 });
        const timedRequest = expect(request(timed.wrapper)).rejects.toThrow('timed out');
        await vi.advanceTimersByTimeAsync(25);
        await timedRequest;
        timed.wrapper.unmount();

        const closed = mountTransport();
        const closedRequest = request(closed.wrapper);
        closed.websocket.dispatchSocketEvent('close');
        await expect(closedRequest).rejects.toThrow('websocket closed');
        closed.wrapper.unmount();
    });

    it('models committed-but-unconfirmed and rejects malformed authoritative responses', async () => {
        const indeterminate = mountTransport();
        const pending = request(indeterminate.wrapper);
        indeterminate.websocket.dispatch({
            type: 'world_state_manager', action: 'game_primitives_indeterminate',
            request_id: indeterminate.websocket.outgoing[0].request_id, request_action: 'mutate',
            outcome: 'committed_but_unconfirmed', revision: 'revision-2', error: { message: 'ack failed' },
        });
        await expect(pending).rejects.toMatchObject({
            name: 'IndeterminateWebsocketRequestError', revision: 'revision-2', outcome: 'committed_but_unconfirmed',
        });
        expect(indeterminate.wrapper.vm.indeterminate).toBeInstanceOf(IndeterminateWebsocketRequestError);
        indeterminate.wrapper.unmount();

        const malformed = mountTransport();
        const malformedRequest = request(malformed.wrapper);
        malformed.websocket.dispatch({
            type: 'world_state_manager', action: 'completed', request_id: malformed.websocket.outgoing[0].request_id,
        });
        await expect(malformedRequest).rejects.toThrow('Malformed mutate response');
        malformed.wrapper.unmount();
    });

    it('rejects pending work and removes all listeners on unmount', async () => {
        const { websocket, wrapper } = mountTransport();
        const pending = request(wrapper);
        wrapper.unmount();
        await expect(pending).rejects.toThrow('owner unmounted');
        expect(websocket.handlerCount).toBe(0);
        expect(websocket.websocket.removeEventListener).toHaveBeenCalledTimes(2);
    });
});
