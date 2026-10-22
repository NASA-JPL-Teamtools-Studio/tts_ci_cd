# Key Abstractions

This is not exhaustive — run `tts-ctx search <term>` for deeper details.

## TtsDataFrame
A `pandas.DataFrame` subclass that survives pandas operations via
`_constructor`. Carries `SCHEMA`, `TIME_FORMATS`, `DEFAULT_TIME_LABEL`.
Key methods: `filter_expr`, `at_times_where`, `derive_values`,
`contiguous_runs`, `moving_average`, `time_average`, `block_average`.

Look with: `tts-ctx class tts_data_utils.TtsDataFrame`

## TtsRowSeries
Per-row view of a `TtsDataFrame`. Allows methods to be called on individual
rows while still having access to DataFrame-level context (e.g. `.document`).
Defined inside `TtsDataFrame` as a nested class.

Look with: `tts-ctx class tts_data_utils.TtsDataFrame.TtsRowSeries`

## TtsColumnSeries
Per-column view of a `TtsDataFrame`. Similar to TtsRowSeries but column-oriented.

Look with: `tts-ctx class tts_data_utils.TtsColumnSeries`

## PowerTable
A table component in `tts_html_utils` for generating tabular HTML. Uses
`Cell`, `Row`, `Table` component hierarchy. Each table gets a UUID id for
stable HTML certification.

Look with: `tts-ctx class tts_html_utils.PowerTable`

## HtmlComponent / HtmlComponentSimple
Base classes for HTML generation components. `HtmlComponentSimple` provides
the basic tag/children model; `HtmlComponent` adds class_name/style/id
management.

Look with: `tts-ctx class tts_html_utils.HtmlComponent`

## BaseSemanticDictionary
Generic base for reading structured dictionaries (XML, YAML, JSON) using
declarative path mappings (`ATTR_PATHS`, `ITEM_PATHS`, `ITEM_CLASSES`).
Mission adapters subclass this to define mission-specific attribute and
item paths.

Look with: `tts-ctx class tts_dictionary_interface.base.BaseSemanticDictionary`

## SeqCollection / SeqTemplate
Core abstractions in `tts_seq` for working with sequence files.
`SeqTemplate` defines a sequence plan; `SeqCollection` represents a
collection of sequences.

Look with: `tts-ctx class tts_seq.SeqCollection`

## TtsEvent
Base class for rule-based event detection. Mission adapters subclass this
to define mission-specific event types (e.g., `Oco2Event`, `DemoSatEvent`).

Look with: `tts-ctx class tts_events.core.event.TtsEvent`

## Tower
The main orchestrator for report generation and rule checking. Manages
input state, loads checkers, compiles reports. Mission adapters subclass
to add mission-specific checkers and inputs.

Look with: `tts-ctx class tts_tower.tower.Tower`
