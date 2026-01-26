# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## Unreleased

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
