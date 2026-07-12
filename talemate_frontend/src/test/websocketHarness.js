import { defineComponent, h } from 'vue';
import { createVuetify } from 'vuetify';
import { vi } from 'vitest';

const DEFAULT_VUETIFY_COMPONENTS = [
  'VAlert',
  'VBtn',
  'VCard',
  'VCardActions',
  'VCardText',
  'VCardTitle',
  'VCheckbox',
  'VChip',
  'VCol',
  'VDialog',
  'VIcon',
  'VList',
  'VListItem',
  'VListItemSubtitle',
  'VListItemTitle',
  'VListSubheader',
  'VNumberInput',
  'VProgressCircular',
  'VProgressLinear',
  'VRow',
  'VSlider',
  'VSpacer',
  'VTextField',
];

function createComponentStub(name) {
  return defineComponent({
    name: `${name}TestStub`,
    inheritAttrs: false,
    setup(_, { attrs, slots }) {
      return () => h(
        `test-${name.replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase()}`,
        attrs,
        Object.values(slots).flatMap((slot) => slot?.() ?? []),
      );
    },
  });
}

export function createVuetifyStubs(names = DEFAULT_VUETIFY_COMPONENTS) {
  return Object.fromEntries(names.map((name) => [name, createComponentStub(name)]));
}

export const vuetifyStubs = createVuetifyStubs();

export function createVuetifyTestPlugin(options = {}) {
  return createVuetify(options);
}

export function createWebsocketHarness() {
  const handlers = new Set();
  const socketHandlers = new Map();
  const outgoing = [];
  const websocket = {
    send: vi.fn((payload) => {
      outgoing.push(JSON.parse(payload));
    }),
    addEventListener: vi.fn((type, handler) => {
      if (!socketHandlers.has(type)) socketHandlers.set(type, new Set());
      socketHandlers.get(type).add(handler);
    }),
    removeEventListener: vi.fn((type, handler) => socketHandlers.get(type)?.delete(handler)),
  };

  const getWebsocket = vi.fn(() => websocket);
  const registerMessageHandler = vi.fn((handler) => handlers.add(handler));
  const unregisterMessageHandler = vi.fn((handler) => handlers.delete(handler));

  function dispatch(message) {
    for (const handler of [...handlers]) {
      handler(message);
    }
  }

  function dispatchSocketEvent(type, event = new Event(type)) {
    for (const handler of [...(socketHandlers.get(type) ?? [])]) {
      handler(event);
    }
  }

  return {
    websocket,
    outgoing,
    dispatch,
    dispatchSocketEvent,
    get handlerCount() {
      return handlers.size;
    },
    getWebsocket,
    registerMessageHandler,
    unregisterMessageHandler,
    provide: {
      getWebsocket,
      registerMessageHandler,
      unregisterMessageHandler,
    },
  };
}
