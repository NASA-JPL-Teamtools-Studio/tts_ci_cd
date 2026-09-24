# tts-ctx — Where to start

The TTS (Teamtools Studio) workspace is a collection of ~24 core libraries under
`tts_core/` and ~70 mission adaptation repos grouped by mission (`demosat/`,
`oco2/`, `fss/`, etc.). Each repo is an independent Git repository with its own
`AGENTS.md` and `docs/agents/README.md` pointer.

## Navigation strategy

1. **`tts-ctx core`** — see the shared libraries (data_utils, tower, events, …)
2. **`tts-ctx adaptations`** — see how missions extend core libraries
3. **`tts-ctx class <dotted.path>`** — dive into a specific class and its MRO
4. **`tts-ctx search <query>`** — fuzzy search any symbol across all repos
5. **`tts-ctx repo <repo-name>`** — get key classes + dependencies for one repo

## Key relationships

- Core libraries depend on `tts_utilities` (logger, Python compat shims).
- `tts_data_utils` → `tts_papertrail` → `tts_html_utils` → `tts_tower` is the
  core pipeline.
- Mission adapters (`demosat_data_utils`, `oco2_seq`, etc.) subclass TTS core
  classes and override behavior.

## Conventions

- **Imports**: Fully-qualified (`from tts_data_utils.core.data_frame import TtsDataFrame`),
  no relative imports in production code.
- **Python**: 3.6.8+ floor — avoid 3.9+ syntax.
- **Tests**: mirror the `src/` tree exactly; `inspection` markers require
  human-certified `.sha256` sidecar files.
- **Coding**: Class-based, subclassable, with `classmethod` hooks.

## Before you edit

Run `tts-ctx class <class>` to see the MRO and understand which methods are
inherited vs. overridden. Then `tts-ctx class <class> --depth 3` to read just
the class's source lines.
