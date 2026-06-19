# Publishing Plan

This upgrade belongs in the existing `kleinpanic/VTWebCatCLI` repository on
`main`. It should land through the repository's existing history so old users
can pull normally and keep the classic `WebcatCLI.py` command.

## Active PR

```text
https://github.com/kleinpanic/VTWebCatCLI/pull/1
```

- Base: `main`
- Head: `profile-aware-upgrade-pr`
- Purpose: merge the profile-aware upgrade into the real VTWebCatCLI mainline
  without force-pushing over existing history.

## Mainline Requirements

Before merging:

- `WebcatCLI.py` must remain available at the repository root.
- The classic checker must remain first-class supported functionality.
- `bin/webcat` must be additive, not a replacement for existing workflows.
- Public CI must pass.
- Public docs must describe CS2505 and CS3114 as peer course profiles.
- Any official-looking score must distinguish local CLI output from Web-CAT
  output.

## Branch Notes

An earlier public branch, `profile-aware-upgrade`, was pushed as a clean orphan
branch. It passed CI, but GitHub cannot merge it into `main` normally because
it has unrelated history. Treat it as superseded by `profile-aware-upgrade-pr`.

## CI Expectations

The current CI proves:

- classic `WebcatCLI.py` parses, reports version, and passes its style-rule
  shell harness;
- profile-aware `webcat doctor` works for `cs2505` and `cs3114`;
- the `cs2505` wrapper returns schema JSON through the classic backend;
- `cs2505` mutation is explicitly unsupported;
- `cs3114` direct-JUnit execution works through a hermetic fixture.

The current CI does not yet prove full CS2505 Maven/JaCoCo coverage execution
or Web-CAT authenticated submission. Those remain future phase work.
