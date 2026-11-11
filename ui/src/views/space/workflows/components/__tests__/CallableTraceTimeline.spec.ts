import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'
import CallableTraceTimeline from '@/views/space/workflows/components/CallableTraceTimeline.vue'

const trace = (overrides: Record<string, unknown> = {}) => ({
  schema_version: 1,
  event_id: 'event-1',
  run_id: 'run-1',
  parent_run_id: null,
  run_type: 'llm',
  phase: 'start',
  name: 'ChatOpenAI',
  status: 'running',
  inputs: { prompt: 'hello' },
  outputs: null,
  error: null,
  latency_ms: null,
  ...overrides,
})

const mountTimeline = (events: unknown[]) => mount(CallableTraceTimeline, { props: { events } })

it('renders a running LLM call with safe input and null output', () => {
  const wrapper = mountTimeline([trace()])

  expect(wrapper.get('[data-testid="callable-trace-call"]').attributes('data-status')).toBe(
    'running',
  )
  expect(wrapper.text()).toContain('ChatOpenAI')
  expect(wrapper.text()).toContain('LLM')
  expect(wrapper.text()).toContain('运行中')
  expect(wrapper.findAll('details')).toHaveLength(2)
  expect(wrapper.text()).toContain('"prompt": "hello"')
  expect(wrapper.text()).toContain('null')
  expect(wrapper.html()).not.toContain('v-html')
  wrapper.unmount()
})

it('updates the same run when its end event arrives', () => {
  const wrapper = mountTimeline([
    trace(),
    trace({
      event_id: 'event-2',
      phase: 'end',
      status: 'succeeded',
      outputs: { answer: 'done' },
      latency_ms: 42,
    }),
  ])

  expect(wrapper.findAll('[data-testid="callable-trace-call"]')).toHaveLength(1)
  expect(wrapper.get('[data-testid="callable-trace-call"]').attributes('data-status')).toBe(
    'succeeded',
  )
  expect(wrapper.text()).toContain('42 ms')
  expect(wrapper.text()).toContain('"answer": "done"')
  wrapper.unmount()
})

it('keeps terminal data when a delayed start event arrives out of order', () => {
  const wrapper = mountTimeline([
    trace({
      event_id: 'event-2',
      phase: 'end',
      status: 'succeeded',
      outputs: { answer: 'done' },
      latency_ms: 42,
    }),
    trace({
      event_id: 'event-1',
      phase: 'start',
      status: 'running',
      outputs: null,
      latency_ms: null,
    }),
  ])

  expect(wrapper.findAll('[data-testid="callable-trace-call"]')).toHaveLength(1)
  expect(wrapper.get('[data-testid="callable-trace-call"]').attributes('data-status')).toBe(
    'succeeded',
  )
  expect(wrapper.text()).toContain('"answer": "done"')
  expect(wrapper.text()).toContain('42 ms')
  wrapper.unmount()
})

it('shows error phase details and error status', () => {
  const wrapper = mountTimeline([
    trace({ phase: 'error', status: 'failed', error: 'Provider timed out', outputs: ['partial'] }),
  ])

  expect(wrapper.get('[data-testid="callable-trace-call"]').attributes('data-status')).toBe(
    'failed',
  )
  expect(wrapper.text()).toContain('Provider timed out')
  expect(wrapper.text()).toContain('partial')
  wrapper.unmount()
})

it('shows nested calls under their parent run', () => {
  const wrapper = mountTimeline([
    trace({ run_id: 'chain-1', run_type: 'chain', phase: 'start', name: 'AgentChain' }),
    trace({
      event_id: 'event-2',
      run_id: 'tool-1',
      parent_run_id: 'chain-1',
      run_type: 'tool',
      phase: 'start',
      name: 'Search',
    }),
  ])

  const calls = wrapper.findAll('[data-testid="callable-trace-call"]')
  expect(calls).toHaveLength(2)
  expect(calls[0].text()).toContain('Chain')
  expect(calls[1].attributes('data-parent-run-id')).toBe('chain-1')
  expect(calls[1].text()).toContain('Tool')
  wrapper.unmount()
})

it('accepts events without optional fields and ignores malformed or unsupported events', () => {
  const wrapper = mountTimeline([
    trace({
      event_id: undefined,
      parent_run_id: undefined,
      inputs: undefined,
      outputs: undefined,
      error: undefined,
      latency_ms: undefined,
      name: undefined,
    }),
    '{not json',
    trace({ schema_version: 2, run_id: 'unsupported-version' }),
    trace({ run_id: '', event_id: 'missing-run-id' }),
    trace({ run_type: 'retriever', event_id: 'unsupported-type' }),
    trace({ phase: 'progress', event_id: 'unsupported-phase' }),
  ])

  expect(wrapper.findAll('[data-testid="callable-trace-call"]')).toHaveLength(1)
  expect(wrapper.text()).toContain('run-1')
  wrapper.unmount()
})

it('truncates long outputs in a scrollable, safely rendered block', () => {
  const longOutput = 'trace-output-'.repeat(1500)
  const wrapper = mountTimeline([trace({ phase: 'end', status: 'succeeded', outputs: longOutput })])
  const output = wrapper.get('[data-testid="callable-trace-output"]')

  expect(output.classes()).toContain('overflow-auto')
  expect(output.text().length).toBeLessThan(longOutput.length)
  expect(output.text()).toContain('[truncated]')
  wrapper.unmount()
})

it('limits oversized values and safely formats circular or unsupported data', () => {
  const circular: Record<string, unknown> = {}
  circular.self = circular
  const broadNestedValue = Array.from({ length: 100 }, () =>
    Array.from({ length: 100 }, () => 'value'),
  )
  const wrapper = mountTimeline([
    trace({
      phase: 'end',
      outputs: { long: 'x'.repeat(10_000), circular, bigInt: 123n, broadNestedValue },
    }),
  ])

  const output = wrapper.get('[data-testid="callable-trace-output"]').text()
  expect(output.length).toBeLessThan(5_000)
  expect(output).toContain('[truncated]')
  expect(output).toContain('[Circular]')
  expect(output).toContain('123n')
  wrapper.unmount()
})
