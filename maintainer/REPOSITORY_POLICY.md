# Repository Protection And Delivery Policy

The authoritative configuration is the active GitHub ruleset
[Protect main](https://github.com/Mattboxx/Clipboard-Bridge/rules/20001324).
It was read back through both the ruleset and effective-branch APIs on
20 October 2026. This document does not configure GitHub automatically.

## Main Branch

- Changes require a pull request, even for the repository administrator.
- `validate`, `windows-client` and `android-client` must pass from the GitHub Actions
  integration (ID `15368`), with the branch up to date before merging.
- Review conversations must be resolved. Zero external approvals are required
  because this is currently a solo-maintained project; this is not independent review.
- Squash and rebase merging are allowed; linear history remains required.
- Deletion and force pushes remain blocked. There are no bypass actors.

The native Windows jobs have path filters, so they are not universal required checks:
making them mandatory would leave unrelated changes waiting for jobs that never run.
For changes affecting Windows delivery, both applicable native build checks must
still be examined as part of release acceptance. A merge is not release approval.

If CI job names or their GitHub App change, update the ruleset deliberately after
observing the replacement checks. Do not remove protections or publish a fabricated
passing status to unblock a failed build. A branch that has fallen behind main
must incorporate the new base and pass tests again.

## Evidence And Releases

- Draft PRs and CI artifacts are candidates, not production releases.
- Keep public releases, the AppStore image and the installed desktop application
  unchanged until the maintainer approves publication/replacement.
- Native x64 provenance identifies the checked-out/tested source commit separately
  from the PR head and GitHub workflow commit. Pull-request builds normally test a
  synthetic merge commit, not the head alone.
- Read the Inno Setup version from its actual compilation output, not Windows file
  metadata that can report `0.0.0.0`. Preserve package checksums and dependency lists.
- Installer hash tests must use actual application profile paths. Disposable runner
  installation is not proof of a real standard-user upgrade or Windows reputation.
- Follow [the acceptance gates](QUALITY_PLAN.md) and [physical test plan](MANUAL_TESTS.md).

GitHub documents these mechanisms in
[available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
and the [ruleset API](https://docs.github.com/en/rest/repos/rules).
