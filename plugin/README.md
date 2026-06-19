# Neovim Plugin Loader

Reserved for the optional Neovim integration layer. This directory is the
single home for both command registration and any future Lua module code.

Actual Neovim commands are out of scope for Phase 1. They should be implemented
after the CLI-side `test`, `mutate`, `targets`, and `submit` JSON contracts are
stable.

The plugin must remain a thin consumer of the CLI's `schema:1` JSON output. It
should not parse raw JUnit, PIT, JaCoCo, or Web-CAT submitter output directly.
