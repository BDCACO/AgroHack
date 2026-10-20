import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { router } from './router'
// Fraunces com o eixo de tamanho óptico: a serifa se ajusta sozinha do título ao número.
import '@fontsource-variable/fraunces/opsz.css'
import '@fontsource-variable/ibm-plex-sans'
import './styles/main.css'

createApp(App).use(createPinia()).use(router).mount('#app')
