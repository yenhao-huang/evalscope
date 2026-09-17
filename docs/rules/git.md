# Git rules

- Read this file before staging, committing, or changing branches/remotes. Verify `git rev-parse --show-toplevel`.
- Inspect `git status --short`; preserve unrelated changes. Stage explicit paths only, inspect `git diff --cached`, run `git diff --check`, then create focused local Conventional Commits after validation.
- Follow upstream AGENTS.md Submission checks. Use a feature branch for this fork.
- `origin` is yenhao-huang/evalscope; `upstream` is modelscope/evalscope. Never push to either without an explicit user push request. Fork creation and requested issue creation are authorized in this task.
- Never commit secrets, .venv, weights, dataset rows/images, raw predictions or runtime logs. Small experiment configuration, dataset manifests (hashes/counts), aggregate scores and reports are tracked.
- Keep issues, docs/feature-list.md and experiment reports current. Do not close an issue with unmet acceptance criteria.
