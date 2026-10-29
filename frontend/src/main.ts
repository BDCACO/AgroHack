import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { router } from './router'
import '@fontsource-variable/plus-jakarta-sans'
import './styles/main.css'
// O tema de Configurações: acompanha o aparelho quando a escolha é "igual ao aparelho".
import './tema'

createApp(App).use(createPinia()).use(router).mount('#app')
