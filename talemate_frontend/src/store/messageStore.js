import { reactive, watch } from 'vue'

export const messageStore = reactive({
  messages: []
})

export function hydrateMessages() {
  const saved = localStorage.getItem('talemate_messages')
  if (saved) {
    try {
      messageStore.messages = JSON.parse(saved)
    } catch (e) {
      console.error('Failed to parse saved messages from localStorage', e)
      messageStore.messages = []
    }
  }
}

watch(
  () => messageStore.messages,
  (msgs) => {
    localStorage.setItem('talemate_messages', JSON.stringify(msgs))
  },
  { deep: true }
)

export default messageStore
