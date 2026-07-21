# Contributing to Formula Forge

Thanks for helping improve Formula Forge. Bug fixes, accessibility work,
interface polish, asset improvements, tests, documentation, and new circuits
are all welcome.

## Before you start

- Open an issue before a large or behavior-changing contribution so its scope
  can be agreed on early.
- Keep the established driving feel, handling, speed, and manual shifting
  intact unless a change is explicitly addressing a confirmed gameplay bug.
- Do not add licensed series branding, team logos, or assets copied from other
  games.

## Development workflow

Build and run the game from the repository root:

```sh
make
make run
```

Run the complete deterministic suite before submitting code:

```sh
make test
```

Add or update a focused audit when changing a behavior that can be tested
deterministically. Keep commits small enough to review and use commit messages
that describe the resulting behavior.

## Asset changes

All 3D asset changes must remain reproducible through the Blender Python API.
Use the `uv`-managed environment and update the generator, editable `.blend`,
runtime export, preview, and metadata together.

```sh
uv sync --frozen
make assets-validate
```

See [tools/README.md](tools/README.md) for the production asset commands and
[tools/blender/tracks/README.md](tools/blender/tracks/README.md) for circuit
contracts.

## Pull requests

Describe the user-visible outcome, note the tests you ran, and include before
and after images for visual changes. By contributing, you agree that your work
may be distributed under the repository's MIT license.
