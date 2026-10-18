import js from '@eslint/js'
import vueTsConfig from '@vue/eslint-config-typescript'
import eslintPluginVue from 'eslint-plugin-vue'

export default [
  { ignores: ['dist/**', 'node_modules/**'] },
  js.configs.recommended,
  ...eslintPluginVue.configs['flat/recommended'],
  ...vueTsConfig(),
]
