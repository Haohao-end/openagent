# Live execution traces

OpenAgent can show a Callable Trace timeline during supported live chat and workflow debug runs. The timeline is an execution aid alongside the answer or workflow output.

## Events and timeline

The UI receives traces as `callable_trace` stream events. Schema version 1 events identify a run with `run_id`, optionally link it to a parent with `parent_run_id`, and describe a `chain`, `llm`, `tool`, or `retriever` lifecycle. A run can report `start`, `end`, or `error`; payloads may include its name, status, inputs, outputs, error, and `latency_ms`.

The timeline groups lifecycle updates by run ID, ignores duplicate event IDs, and nests child runs when their parent is available. Start events remain visible as running until a terminal update arrives. Errors and available input/output details are shown with the run. Invalid or unsupported events are skipped, and an empty event list does not render an empty timeline.

## Trace lifetime

Trace events are transient stream data. They are kept with the live message or debug run in the current UI state; they are not reconstructed from persisted thoughts or historical chat records. Reloading a conversation or fetching an older history page therefore cannot restore a previous Trace timeline. Start a new live debug run to collect its events.

See the [Chinese Trace guide](trace.zh-CN.md) and the [architecture guide](architecture.md).
