import { inject, markRaw, onBeforeUnmount, onMounted, ref } from 'vue';
import { v4 as uuidv4 } from 'uuid';

import {
    gamePrimitivesFailureSchema,
    gamePrimitivesIndeterminateSchema,
} from './gamePrimitiveResponseContracts.js';

/** Error indicating that the server committed a request but could not confirm it. */
export class IndeterminateWebsocketRequestError extends Error {
    /**
     * @param {string} message Transport failure description.
     * @param {string} revision Authoritative revision after the commit.
     */
    constructor(message, revision) {
        super(message);
        this.name = 'IndeterminateWebsocketRequestError';
        this.revision = revision;
        this.outcome = 'committed_but_unconfirmed';
    }
}

/**
 * Own strict request correlation and every terminal websocket lifecycle path.
 * @param {object} [options={}] Provider and timeout overrides.
 * @param {() => WebSocket} [options.getWebsocket] Active websocket provider.
 * @param {(handler: Function) => void} [options.registerMessageHandler] Message registration callback.
 * @param {(handler: Function) => void} [options.unregisterMessageHandler] Message removal callback.
 * @param {number} [options.timeoutMs=10000] Request timeout in milliseconds.
 * @returns {{busy: import('vue').Ref<boolean>, error: import('vue').Ref<string|null>, stale: import('vue').Ref<boolean>, indeterminate: import('vue').Ref<IndeterminateWebsocketRequestError|null>, request: Function, handleMessage: Function}} Reactive state and correlated request operations.
 * @throws {Error} Required websocket providers are unavailable.
 */
export function useCorrelatedWebsocketRequest(options = {}) {
    const getWebsocket = options.getWebsocket ?? inject('getWebsocket', null);
    const register = options.registerMessageHandler ?? inject('registerMessageHandler', null);
    const unregister = options.unregisterMessageHandler ?? inject('unregisterMessageHandler', null);
    const timeoutMs = options.timeoutMs ?? 10_000;
    if (!getWebsocket || !register || !unregister) throw new Error('Websocket request providers are required');

    const busy = ref(false);
    const error = ref(null);
    const stale = ref(false);
    const indeterminate = ref(null);
    const pending = new Map();
    let activeSocket = null;

    function asError(value) {
        return value instanceof Error ? value : new Error(String(value));
    }

    function settle(requestId, failure, value) {
        const request = pending.get(requestId);
        if (!request) return;
        clearTimeout(request.timer);
        pending.delete(requestId);
        busy.value = pending.size > 0;
        if (failure) {
            error.value = failure.message;
            stale.value = /stale game primitives revision/i.test(failure.message);
            request.reject(failure);
        } else {
            error.value = null;
            stale.value = false;
            indeterminate.value = null;
            request.resolve(value);
        }
    }

    function malformed(requestId, action, parseError) {
        settle(requestId, new Error(`Malformed ${action} response: ${asError(parseError).message}`));
    }

    function handleMessage(message) {
        const request = pending.get(message?.request_id);
        if (!request || message?.type !== 'world_state_manager') return;
        if (message.action === 'game_primitives_failed') {
            const result = gamePrimitivesFailureSchema.safeParse(message);
            if (!result.success) return malformed(message.request_id, request.action, result.error);
            if (result.data.request_action !== request.action) return;
            settle(message.request_id, new Error(result.data.error.message));
            return;
        }
        if (message.action === 'game_primitives_indeterminate') {
            const result = gamePrimitivesIndeterminateSchema.safeParse(message);
            if (!result.success) return malformed(message.request_id, request.action, result.error);
            if (result.data.request_action !== request.action) return;
            const failure = new IndeterminateWebsocketRequestError(result.data.error.message, result.data.revision);
            indeterminate.value = failure;
            settle(message.request_id, failure);
            return;
        }
        if (message.action !== request.responseAction) return;
        const result = request.schema.safeParse(message);
        if (!result.success) return malformed(message.request_id, request.action, result.error);
        try {
            request.onResponse?.(result.data);
        } catch (responseError) {
            return malformed(message.request_id, request.action, responseError);
        }
        settle(message.request_id, null, result.data);
    }

    function listen(socket) {
        if (activeSocket === socket) return;
        unlisten();
        activeSocket = markRaw(socket);
        activeSocket.addEventListener('close', handleSocketFailure);
        activeSocket.addEventListener('error', handleSocketFailure);
    }

    function unlisten() {
        if (!activeSocket) return;
        activeSocket.removeEventListener('close', handleSocketFailure);
        activeSocket.removeEventListener('error', handleSocketFailure);
        activeSocket = null;
    }

    function handleSocketFailure(event) {
        const reason = event.type === 'close' ? 'closed' : 'encountered an error';
        for (const requestId of [...pending.keys()]) {
            settle(requestId, new Error(`Websocket request failed because the websocket ${reason}`));
        }
    }

    function request({ action, responseAction, schema, fields = {}, onResponse = null, requestKey = null }) {
        if (requestKey) {
            for (const [pendingId, pendingRequest] of pending.entries()) {
                if (pendingRequest.requestKey === requestKey) settle(pendingId, new Error(`${action} superseded an earlier request`));
            }
        }
        const requestId = uuidv4();
        busy.value = true;
        error.value = null;
        stale.value = false;
        indeterminate.value = null;
        const promise = new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                settle(requestId, new Error(`${action} timed out after ${timeoutMs / 1000} seconds`));
            }, timeoutMs);
            pending.set(requestId, { action, responseAction, schema, onResponse, requestKey, resolve, reject, timer });
            try {
                const socket = getWebsocket();
                listen(socket);
                socket.send(JSON.stringify({ type: 'world_state_manager', action, request_id: requestId, ...fields }));
            } catch (sendError) {
                settle(requestId, asError(sendError));
            }
        });
        return promise;
    }

    onMounted(() => {
        register(handleMessage);
        listen(getWebsocket());
    });
    onBeforeUnmount(() => {
        unregister(handleMessage);
        unlisten();
        for (const requestId of [...pending.keys()]) settle(requestId, new Error('Websocket request owner unmounted'));
    });

    return { busy, error, stale, indeterminate, request, handleMessage };
}
