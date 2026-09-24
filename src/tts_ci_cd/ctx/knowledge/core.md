# TTS Core Libraries

The `tts_core/` directory contains shared infrastructure libraries. Each is a
standalone pip package with its own repo and Git remote.

## Dependency hierarchy

```
tts_utilities
  ↓
tts_html_utils ──────┬── tts_dictionary_interface
                     └── tts_papertrail
                         ↓
                    tts_data_utils ── tts_dante
                    tts_seq ───────── tts_fresh
                    tts_tower
                    tts_dexter (extends data_utils)
                    tts_spice
                    tts_plan
                    tts_events
                    tts_dtat
                    tts_starter_template
```

## What each library provides

### tts_utilities
Logger (`create_logger`), Python compat helpers (`as_list`, `ensure_dir`). The
base of every other library. No dependencies outside stdlib.

### tts_html_utils
`PowerTable` (tabular HTML generation), `HtmlComponent` component model,
`HtmlCompiler` template engine. Used by tower reports and dexter.

### tts_dictionary_interface
`BaseSemanticDictionary` — declarative XML/YAML/JSON dictionary reader with
`ATTR_PATHS`, `ITEM_PATHS`, and `ITEM_CLASSES` mapping tables. Mission adapters
subclass this to add mission-specific parsing logic.

### tts_papertrail
`TtsEvent` base class, event filtering/query infrastructure. Provides the
event model that both core and mission-specific events extend.

### tts_data_utils
`TtsDataFrame` (pandas DataFrame subclass), `TtsRowSeries`, `TtsColumnSeries`.
Expression engine for filtering and derivation (`derive_values`, `filter_expr`).
The central data abstraction.

### tts_tower
`Tower` orchestrator — loads checkers, manages input state, runs report
compilation. Mission adapters subclass `Tower` to add mission-specific
checkers, inputs, and report pages.

### tts_telemetry_store
EHA/query infrastructure for accessing telemetry databases (AMPCS-backed).

### tts_dexeter
Row-level mixins for disposition/review workflows built on `TtsDataFrame`.

### tts_events
`TtsEvent` model for rule-based event detection. Mission adapters subclass
`TtsEvent` and `TtsEventGenerator`.

### tts_seq
`SeqCollection` and `SeqTemplate` for sequence file manipulation
(SPICE/SEQR/FP models).

### tts_fresh
Flight Rule Evaluation Script Helper — runs rule-based checks against
telemetry data, typically for pre-uplink validation.

### tts_dtat
EVR/log viewers built on `tts_html_utils` — ipywidgets-based interactive
explorers for mission logs.
