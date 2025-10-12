# Changelog

All notable changes to this project are documented through Git tags and GitHub releases.

## Version History

See **[GitHub Releases](https://github.com/stephan-aichholzer/lg-r290-control/releases)** for detailed release notes and changelogs.

## Latest Versions

- **[v1.0.0](https://github.com/stephan-aichholzer/lg-r290-control/releases/tag/v1.0.0)** - Production-Ready System
  - Time-based scheduler with weekday/weekend patterns
  - Enhanced AI Mode (enabled by default)
  - Comprehensive API documentation (OpenAPI 3.1.0)
  - Complete logging and traceability
  - Monitoring tools and scripts
  - Improved UI responsiveness

- **[v0.8](https://github.com/stephan-aichholzer/lg-r290-control/releases/tag/v0.8)** - AI Mode with Adaptive Heating Curve
  - Autonomous weather compensation
  - Three heating curves (ECO, Comfort, High Demand)
  - Thermostat integration

- **[v0.7](https://github.com/stephan-aichholzer/lg-r290-control/releases/tag/v0.7)** - Temperature Badge Redesign

- **[v0.6](https://github.com/stephan-aichholzer/lg-r290-control/releases/tag/v0.6)** - Performance Optimizations

- **[v0.5](https://github.com/stephan-aichholzer/lg-r290-control/releases/tag/v0.5)** - Thermostat Integration

## Viewing Changes

Use Git to view changes between versions:

```bash
# View all tags
git tag

# View commits between versions
git log v0.8..v1.0.0 --oneline

# View detailed commit messages
git log v0.8..v1.0.0

# View changes in files
git diff v0.8..v1.0.0
```

## Semantic Versioning

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version (v1.x.x) - Incompatible API changes
- **MINOR** version (vx.1.x) - New functionality (backward compatible)
- **PATCH** version (vx.x.1) - Bug fixes (backward compatible)
