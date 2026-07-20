# What & Why

<!-- What does this PR change, and what problem does it solve?
     For anything non-trivial, link the issue where it was discussed —
     see CONTRIBUTING.md: features should be discussed before code. -->

## How was this tested?

<!-- Check all that apply and add detail. -->

- [ ] `python -m pytest -v` passes, with new tests covering the change
- [ ] Dry-run (`DRY_RUN=true`) against real UniFi/AdGuard — plan output looked correct
- [ ] Live run against real hardware

## Checklist

- [ ] No secrets in the diff (keys, passwords, real MACs/hostnames beyond examples)
- [ ] The ownership-tag fence is intact — untagged AdGuard clients are never touched
- [ ] README updated if configuration variables or operational behavior changed
- [ ] One focused change (split unrelated changes into separate PRs)
