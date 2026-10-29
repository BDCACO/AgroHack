import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import GradeDeMesesDeSafra from '@/components/GradeDeMesesDeSafra.vue'

describe('GradeDeMesesDeSafra', () => {
  it('marca os meses já selecionados', () => {
    const wrapper = mount(GradeDeMesesDeSafra, { props: { modelValue: [1, 12] } })

    const pressionados = wrapper
      .findAll('button')
      .filter((b) => b.attributes('aria-pressed') === 'true')
      .map((b) => b.text())

    expect(pressionados).toEqual(['Jan', 'Dez'])
  })

  it('clicar num mês solto adiciona, e num já marcado remove', async () => {
    const wrapper = mount(GradeDeMesesDeSafra, { props: { modelValue: [1] } })

    await wrapper.findAll('button').find((b) => b.text() === 'Mar')!.trigger('click')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([[1, 3]])

    await wrapper.setProps({ modelValue: [1, 3] })
    await wrapper.findAll('button').find((b) => b.text() === 'Jan')!.trigger('click')
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([[3]])
  })
})
