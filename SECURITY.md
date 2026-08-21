# Security Policy

## Reporting a vulnerability

Report privately through GitHub's [Security Advisories](https://github.com/HibikiHata/game-of-life-svg/security/advisories/new).
Please do not open a public issue for a security problem.

You will get an acknowledgment within 7 days.

After triage I will confirm or decline the report, develop a fix privately,
and publish a security advisory crediting you (unless you prefer otherwise)
once a fixed release is out. This is a solo-maintained project; complex fixes
may take a few weeks.

## Supported versions

Only the latest release (and the moving `v1` tag that follows it) is
supported. Fixes are not backported.

## What this project touches

Knowing the boundaries is usually enough to judge whether something is a
security problem here.

- **The token.** The Action reads the contribution calendar with the workflow's
  own `GITHUB_TOKEN` by default. It is passed only through the environment,
  never as a command-line argument, so it does not reach the process list or
  the workflow log. The calendar is public data; the token is not needed for
  access, only for authenticated API rate limits.
- **Network.** One call, to `https://api.github.com/graphql`. There is no other
  network access anywhere in the package, and the test suite never touches the
  network at all.
- **Dependencies.** The package uses the Python standard library only. The test
  suite additionally needs `pytest` and `PyYAML`.
- **Persistence.** Nothing is stored between runs. A run reads only the calendar
  it just fetched, and a test asserts that no module outside the CLI and the
  gallery builder can write files at all.
- **The generated SVGs.** They are self-contained: no `<script>`, no
  `<foreignObject>`, no external reference other than the SVG namespace
  declaration. This is asserted for every artefact the build produces.
- **Third-party Actions.** Every `uses:` in this repository is pinned to a full
  commit SHA.

## Out of scope

- Vulnerabilities in GitHub Actions itself or in the third-party actions this
  repository pins — report those upstream.
- A dependency version with a known CVE, unless the vulnerable code is
  actually reachable from this project.
- Anything that requires write access to this repository or a compromised
  workflow token.

If you used AI tools to find or write up the issue, say so, and verify the
proof of concept reproduces before reporting. Unverified machine-generated
reports are closed without response.
