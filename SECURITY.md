# Security Policy

## Reporting a vulnerability

Report privately through GitHub's [Security Advisories](https://github.com/HibikiHata/game-of-life-svg/security/advisories/new).
Please do not open a public issue for a security problem.

Expect an initial response within a week.

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
