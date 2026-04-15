# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed

- OpenTelemetry optional extra (`opendota-async[otel]`) and `otel` module.

### Added

- GitHub Actions workflows for CI and PyPI publishing; see `docs/publishing.md`.

## [0.1.0] - 2026-04-15

### Added

- Initial release: async `OpenDotaClient` on `niquests.AsyncSession`, optional sync client,
  Pydantic models, retries, rate limiting hooks, multiplexed `gather` helpers, and
  `players` resource with pagination.
