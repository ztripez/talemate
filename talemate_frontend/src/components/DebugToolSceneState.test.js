import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import DebugToolSceneState from './DebugToolSceneState.vue';
import {
  createWebsocketHarness,
  vuetifyStubs,
} from '../test/websocketHarness.js';

function mountComponent() {
  const websocket = createWebsocketHarness();
  const wrapper = mount(DebugToolSceneState, {
    global: {
      provide: {
        ...websocket.provide,
        setWaitingForInput: () => {},
      },
      stubs: {
        ...vuetifyStubs,
        Codemirror: true,
      },
    },
  });

  return { websocket, wrapper };
}

describe('DebugToolSceneState', () => {
  it.each([
    ['success', { type: 'devtools', action: 'scene_state_updated' }],
    ['error', {
      type: 'devtools',
      action: 'scene_state_update_failed',
      error: { message: 'Invalid scene state' },
    }],
  ])('filters messages and cleans up busy state on %s', (_, operationDone) => {
    const { websocket, wrapper } = mountComponent();
    const registeredHandler = websocket.registerMessageHandler.mock.calls[0][0];

    expect(websocket.handlerCount).toBe(1);
    wrapper.vm.sceneStateJSON = JSON.stringify({ title: 'Test scene' });
    wrapper.vm.updateSceneState();

    expect(wrapper.vm.busy).toBe(true);
    expect(websocket.outgoing).toEqual([{
      type: 'devtools',
      action: 'update_scene_state',
      state: { title: 'Test scene' },
    }]);

    websocket.dispatch({
      type: 'devtools',
      action: 'operation_done',
      error: { message: 'Unrelated failure' },
    });
    expect(wrapper.vm.busy).toBe(true);

    websocket.dispatch(operationDone);
    expect(wrapper.vm.busy).toBe(false);
    expect(wrapper.vm.error).toBe(operationDone.error?.message || null);

    wrapper.unmount();
    expect(websocket.unregisterMessageHandler).toHaveBeenCalledOnce();
    expect(websocket.unregisterMessageHandler).toHaveBeenCalledWith(registeredHandler);
    expect(websocket.handlerCount).toBe(0);
  });

  it('surfaces malformed error envelopes explicitly', () => {
    const { websocket, wrapper } = mountComponent();
    wrapper.vm.sceneStateJSON = '{}';
    wrapper.vm.updateSceneState();

    websocket.dispatch({
      type: 'devtools',
      action: 'scene_state_update_failed',
      error: {},
    });

    expect(wrapper.vm.busy).toBe(false);
    expect(wrapper.vm.error).toBe('Scene state update failed without an error message');
    wrapper.unmount();
  });

  it('surfaces malformed JSON without entering busy state', () => {
    const { websocket, wrapper } = mountComponent();
    wrapper.vm.sceneStateJSON = '{invalid';

    wrapper.vm.updateSceneState();

    expect(wrapper.vm.busy).toBe(false);
    expect(wrapper.vm.error).toContain('JSON');
    expect(websocket.outgoing).toEqual([]);
    wrapper.unmount();
  });

  it('surfaces synchronous websocket send failures', () => {
    const { websocket, wrapper } = mountComponent();
    websocket.websocket.send.mockImplementationOnce(() => {
      throw new Error('socket closed');
    });
    wrapper.vm.sceneStateJSON = '{}';

    wrapper.vm.updateSceneState();

    expect(wrapper.vm.busy).toBe(false);
    expect(wrapper.vm.error).toBe('socket closed');
    wrapper.unmount();
  });
});
