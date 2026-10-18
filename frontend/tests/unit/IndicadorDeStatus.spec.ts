import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import IndicadorDeStatus from '@/components/IndicadorDeStatus.vue'

describe('IndicadorDeStatus', () => {
  it.each([
    ['ok', 'Operando'],
    ['erro', 'Indisponível'],
    ['desconhecido', 'Não verificado'],
  ] as const)('estado %s mostra "%s"', (estado, texto) => {
    const wrapper = mount(IndicadorDeStatus, { props: { rotulo: 'API', estado } })

    expect(wrapper.text()).toContain('API')
    expect(wrapper.text()).toContain(texto)
    expect(wrapper.find(`[data-estado="${estado}"]`).exists()).toBe(true)
  })
})
