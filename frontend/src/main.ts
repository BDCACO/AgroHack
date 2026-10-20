import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { router } from './router'
import '@fontsource-variable/plus-jakarta-sans'
import './styles/main.css'

createApp(App).use(createPinia()).use(router).mount('#app')
