---
name: using-git-worktrees
description: Use when starting implementation that needs workspace isolation, multi-repo branch alignment, or root/.worktrees/{branch}/{repo} layout.
---

# Using Worktrees With Careflow

Prefer the user's multi-repo root layout.

## Required Flow

1. Resolve workflow root from `.careflow/`.
2. For business multi-repo apps, prefer `root-*/.worktrees/<branch>/<repo>`.
3. Ensure `.worktrees/` is ignored before creating worktrees.
4. Record target repo and branch/worktree in PLAN or ORDER.
5. Run commands with explicit repo roots such as `git -C <repo>`.
6. Keep careflow artifacts in the workflow root, not scattered in each worktree repo.

## Superpowers Source

Adapted from `third_party/superpowers/skills/using-git-worktrees/SKILL.md`.
