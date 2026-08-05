# Contributing to Medburg CRM

Thank you for your interest in contributing to Medburg CRM.

This repository hosts the **production source code** for the Medburg CRM platform. The application manages real business workflows and financial records, so contributions should prioritize correctness, maintainability, and data integrity over feature velocity.

---

# Project Philosophy

Before making any change, understand these principles:

- Financial data is more important than UI.
- Existing production workflows must never break.
- Database integrity takes priority over convenience.
- Changes should be small, reviewable, and reversible.
- Every release must be deployable with minimal risk.

---

# Development Workflow

Every feature should follow this workflow:

```
Understand Requirement
        ↓
Impact Analysis
        ↓
Implementation
        ↓
Local Testing
        ↓
Regression Testing
        ↓
Documentation Update
        ↓
Commit
        ↓
Push
        ↓
Release Candidate Tag
        ↓
Production Deployment
```

Never skip impact analysis for changes affecting:

- Financial calculations
- Database models
- Reports
- Dashboard analytics
- Authentication
- Production deployment

---

# Branching Strategy

Use feature branches for development.

Examples:

```
feature/dashboard-redesign
feature/postpaid-ledger
feature/report-improvements
```

Do **not** develop directly on `main`.

---

# Commit Message Convention

Follow Conventional Commits.

Examples:

```
feat(reports): add prepaid doctor summary

fix(dashboard): preserve active tab after filtering

docs(deployment): update VPS deployment guide

refactor(sales): simplify ROI calculation

test(reports): add regression tests
```

---

# Versioning

The project follows Semantic Versioning.

Examples:

```
v1.2.0

v1.2.1

v1.2.3-rc1

v1.2.3

v1.3.0
```

Release Candidates must be fully tested before becoming stable releases.

---

# Coding Standards

- Follow PEP 8.
- Prefer readable code over clever code.
- Keep business logic inside services or models.
- Avoid duplicated logic.
- Add comments only when they explain *why*, not *what*.

---

# Database Guidelines

Database schema changes require additional care.

Before introducing migrations:

- Confirm the migration is necessary.
- Consider impact on production data.
- Verify rollback strategy.
- Test migration locally.

Avoid unnecessary migrations.

---

# Financial Integrity Rules

The following rules must never be violated.

## Snapshot Accounting

Historical sales must always preserve the original medicine price.

Never recalculate historical transactions using current medicine prices.

---

## Append-only Financial Records

Financial history should not be overwritten.

Corrections should create new records instead of modifying historical transactions whenever possible.

---

## Investment Lifecycle

Investments remain active until manually completed by an administrator.

Automatic completion logic should not be reintroduced without a full architectural review.

---

# Testing

Before opening a pull request:

- Run the full test suite.
- Verify affected business workflows.
- Confirm reports still generate correctly.
- Verify dashboard calculations.
- Check migrations (if any).

Production-impacting changes should always include regression testing.

---

# Documentation

Update documentation whenever you change:

- Business workflows
- Deployment process
- Architecture
- Database schema
- Configuration
- Release process

Documentation is considered part of the feature.

---

# Production Deployment

Production deployments should always follow the documented deployment runbook.

Every deployment must include:

- PostgreSQL backup
- Git tag verification
- Environment verification
- Migration check
- Static collection
- Smoke testing

Never deploy directly from untested local code.

---

# Pull Requests

Each pull request should clearly explain:

- What changed
- Why the change was necessary
- Any database impact
- Any deployment considerations
- Any backward compatibility concerns

Screenshots are encouraged for UI changes.

---

# Issue Reporting

When reporting bugs, include:

- Steps to reproduce
- Expected behaviour
- Actual behaviour
- Screenshots (if applicable)
- Browser/device information
- Relevant logs

---

# AI-Assisted Development

AI tools are welcome for:

- Refactoring
- Documentation
- Code reviews
- Test generation
- Boilerplate code

However, all AI-generated code must be:

- Reviewed manually
- Tested locally
- Understood before merging

Never merge AI-generated code without verification.

---

# Thank You

Every contribution helps improve Medburg CRM.

Our goal is not only to build features, but to build reliable software that can be safely maintained and evolved over time.
