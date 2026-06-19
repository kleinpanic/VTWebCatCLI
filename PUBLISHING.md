# Publishing Plan

This repository is an upgrade path for `kleinpanic/VTWebCatCLI`, not a
destructive replacement.

## Current Remote State

- Existing GitHub repo: `git@github.com:kleinpanic/VTWebCatCLI.git`
- Existing default branch: `main`
- Existing remote `main` tip observed during prep: `fd72a54`
- Local upgrade branch starts from a separate scaffold history.

Because the histories are different, do not push local `main` directly to
remote `main`.

## Safe Publication Flow

Two public branches exist:

- `profile-aware-upgrade`: clean orphan branch containing only public-safe
  upgrade files. CI passed, but GitHub cannot open it as a PR because it has no
  common history with `main`.
- `profile-aware-upgrade-pr`: PR-compatible branch based on remote `main`, with
  the upgrade tree overlaid. This is the branch used for the draft PR.

The draft PR is:

```text
https://github.com/kleinpanic/VTWebCatCLI/pull/1
```

If recreating the safe flow:

1. Add the existing GitHub repo as `origin`.
2. Push clean public work to a review branch:

   ```sh
   git push -u origin HEAD:refs/heads/profile-aware-upgrade
   ```

3. For an actual PR, create a second branch from `origin/main` and overlay the
   same public tree so GitHub has common history.
4. Open a draft pull request.
5. Decide whether to:
   - merge the upgrade branch into the original history,
   - reset the repo intentionally after archiving the old state,
   - or publish under a separate repository name.

## CI Expectations

The current CI proves:

- imported legacy `VTWebCatCLI` still parses, reports version, and passes its
  style-rule shell harness;
- profile-aware `webcat doctor` works for `cs2505` and `cs3114`;
- the `cs2505` wrapper returns schema JSON;
- `cs2505` mutation is explicitly unsupported;
- `cs3114` direct-JUnit execution works through a hermetic fixture.

The current CI does not yet prove full CS2505 Maven/JaCoCo coverage execution
or Web-CAT authenticated submission. Those remain future phase work.
