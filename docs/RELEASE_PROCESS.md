# Release Process

Medburg CRM follows a strict Git tagging and deployment strategy to ensure production stability.

## Versioning Scheme

We use Semantic Versioning (SemVer): `vMAJOR.MINOR.PATCH`
- **MAJOR:** Significant architectural changes (e.g., ARCH-2A Snapshot Accounting).
- **MINOR:** New features, reports, or workflow additions (e.g., adding Postpaid Ledgers).
- **PATCH:** Bug fixes, UI polish, or minor adjustments.

## Release Candidates

Before a release hits production, it is tagged as a Release Candidate (e.g., `v1.3.0-rc1`).
- RC tags are deployed to a staging environment (or audited locally against a production database dump).
- QA Engineers and Stakeholders verify the RC.
- If bugs are found, fixes are committed, and a new RC is tagged (`v1.3.0-rc2`).

## Stable Releases

Once an RC is approved via a formal Production QA Checklist, it is tagged as stable (e.g., `v1.3.0-stable`).

**Only `-stable` tags should be deployed to the production VPS.**

## Production Deployment Workflow

1.  **Branching:** Features are developed on `feature/` branches.
2.  **Merging:** Features are merged into a release branch or `main`.
3.  **Tagging:** `git tag v1.3.0-stable -m "Release v1.3.0"`
4.  **Pushing:** `git push origin v1.3.0-stable`
5.  **Deployment:** The system administrator logs into the VPS, fetches the tags, checks out the specific tag, and executes the [Deployment Guide](DEPLOYMENT.md).

## Database Migration Safety

The release process mandates a strict audit of all database migrations.

Before tagging a release as stable, the Lead Release Engineer MUST verify:
- No destructive migrations (e.g., dropping tables) are included unless they follow a multi-release deprecation path.
- `python manage.py makemigrations --check --dry-run` confirms the schema is fully covered.
- Data migrations (like the ARCH-2A backfill) are tested against a copy of production data.
