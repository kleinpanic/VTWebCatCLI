# Publishing Plan

This upgrade belongs in the existing `kleinpanic/VTWebCatCLI` repository on
`main`. It should land through the repository's existing history so old users
can pull normally and keep the classic `WebcatCLI.py` command.

## Published State

```text
main: 8a3b1fa
merged PR: https://github.com/kleinpanic/VTWebCatCLI/pull/1
```

The profile-aware upgrade has been merged into the real VTWebCatCLI mainline
through the existing repository history. The temporary upgrade branches were
deleted after merge.

## Mainline Requirements

Before merging:

- `WebcatCLI.py` must remain available at the repository root.
- The classic checker must remain first-class supported functionality.
- `bin/webcat` must be additive, not a replacement for existing workflows.
- Public CI must pass.
- Public docs must describe CS2505 and CS3114 as peer course profiles.
- Any official-looking score must distinguish local CLI output from Web-CAT
  output.

## CI Expectations

The current CI proves:

- classic `WebcatCLI.py` parses, reports version, and passes its style-rule
  shell harness;
- classic `WebcatCLI.py --run-tests` runs Maven/JUnit/JaCoCo on a fixture;
- profile-aware `webcat doctor` works for `cs2505` and `cs3114`;
- the `cs2505` wrapper returns schema JSON through the classic backend;
- `cs2505` mutation is explicitly unsupported;
- `cs3114` direct-JUnit execution works through a hermetic fixture.

The current CI does not yet prove a broad set of real CS2505 course projects
through the `bin/webcat --profile cs2505` wrapper or Web-CAT authenticated
submission. Those remain future phase work.
