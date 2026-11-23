# Security policy

## Supported versions

The latest release is supported with security fixes.

## Reporting a vulnerability

Report vulnerabilities privately through
[GitHub Security Advisories](https://github.com/8cylinder/dotfig/security/advisories/new).
Do not open a public issue for a suspected vulnerability.

Include the affected version, a description of the impact, and a minimal
reproduction when possible. You will receive a response after the report is
triaged.

## Secrets

The repository blocks commits that contain secrets with gitleaks. If you
suspect a secret was committed, rotate it first: rewriting history does not
revoke a leaked credential. Then report it privately so the history can be
cleaned up and other clones notified.
