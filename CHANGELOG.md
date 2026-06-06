# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## Unreleased

## 0.3.0 - 2026-06-06

### Changed

- Rewrote the converter and CLI in TypeScript/Node.js.
- Published the npm package as `@metyatech/tracklms-to-qti-results` with the `tracklms-to-qti-results` binary.
- Preserved the CSV input, QTI Results XML output, CLI flags, status filtering, and rubric scoring behavior from the Python 0.2.x line.
- Replaced Python development tooling with npm scripts for build, lint, typecheck, tests, and verification.

### Removed

- Removed the Python package entrypoint and PyPI packaging configuration.

## 0.2.1 - 2026-01-27

### Added

- Security audit step in CI and release checklist (pip-audit).
- Python packaging configuration and publishing steps.
- Module entrypoint test for `python -m tracklms_to_qti_results`.

### Changed

- Packaging metadata now uses SPDX license expression.

## 0.2.0 - 2026-01-27

### Added

- Status filtering for completed-only conversions.
- CLI support for `--only-status`, `--dry-run`, `--json`, `--output -`, and `--yes`.
- Linting configuration and CI workflow.
- Repository governance files (security, contributing, code of conduct, templates).
- CLI logging controls (`--quiet`, `--verbose`, `--trace`) and `--version`.

### Changed

- Documentation now lists known Track LMS status values and CLI options.
