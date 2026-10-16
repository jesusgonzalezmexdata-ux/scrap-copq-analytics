# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/).

## [1.2.0] - 2026-10-16

### Added
- MVP for real plants: "Tus datos" mode in the dashboard with an Excel template (`scrap_copq/intake.py`), row-level validation with Spanish messages, and processing in the browser on the live demo.
- Generic diagnosis (`scrap_copq/diagnose.py`): no plant-specific names; per-line maintenance thresholds by minimum deviance; levers reported only when significant, with P10–P90 annual savings and an out-of-sample check against the line average.
- One-page report with the 8D action and IATF 16949 / ISO 9001 references (`scrap_copq/report.py`).
- Pilot protocol with success and stop criteria (`docs/MVP_PILOTO.md`); six tests on clean, dirty and minimal workbooks.

## [1.1.0] - 2026-10-16

### Added
- Second baseline (line × 50 h maintenance band): mean absolute error 1.18 / 1.04 / 0.65 pp for the two baselines and the GLM.
- Dashboard Docker image with a health-check job in CI.
- English README with the Spanish version kept as `README.es.md`.
- Project page on GitHub Pages and a live demo on Hugging Face Spaces, published automatically from `main`.
- Release workflow: notes from this changelog and an evidence bundle attached to every tag.

## [1.0.0] - 2026-10-04

### Added
- Synthetic auto-parts plant data with seeded patterns; cleaning with a logged quality report.
- Cost of poor quality, double Pareto, Laney p′ charts and binomial GLM validated out of sample.
- Savings simulation: three levers worth MXN 1.23 M a year; Streamlit dashboard; SQL for PostgreSQL.
