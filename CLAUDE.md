# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repository Is

**Antigravity Awesome Skills** is a catalog of 1,453+ agentic `SKILL.md` playbooks installable into Claude Code, Gemini CLI, Cursor, Codex CLI, and other AI coding assistants. The repo ships an npm CLI installer, plugin bundles, a React web app for browsing skills, and a Python/Node toolchain for validating and generating derived registry artifacts.

## Commands

All Python scripts must be run via the Node wrapper (handles venv/path automatically):

```bash
node tools/scripts/run-python.js <python_script> [args]
```

### Validation and Testing

```bash
npm run validate                  # Validate all SKILL.md files
npm run validate:strict           # Strict mode (treats warnings as errors)
npm run security:docs             # Security scan on doc content (shell cmds, tokens, etc.)
npm run test                      # Full local test suite
npm run test:local                # Same as npm run test
npm run validate:references       # Check cross-file doc/link references
npm run check:warning-budget      # Enforce validation warning count ceiling
npm run check:readme-credits      # Verify README credits for changed skills
npm run audit:skills              # Audit skill quality
```

Run a single JS test file directly:
```bash
node tools/scripts/tests/<test-file>.test.js
```

Run a single Python test:
```bash
node tools/scripts/run-python.js tools/scripts/tests/<test-file>.py
```

### Building / Syncing Derived Artifacts

```bash
npm run chain          # validate → plugin-compat sync → index → bundles → metadata
npm run build          # chain + catalog (all derived artifacts except web assets)
npm run catalog        # Build CATALOG.md and data/catalog.json only
npm run index          # Regenerate skills_index.json and data/*.json
```

These commands regenerate the **derived files** that must never be edited by hand (see below).

### Web App

```bash
npm run app:setup      # Copy skills data into the web app's public dir
npm run app:dev        # Dev server (runs app:setup first)
npm run app:install    # npm ci in apps/web-app/
npm run app:test       # Vitest (non-watch)
npm run app:test:coverage  # Vitest coverage
npm run app:build      # Production build
```

### Release (Maintainers Only)

```bash
npm run release:preflight   # Pre-release checks
npm run sync:repo-state     # Full repo sync (all derived + web assets + contributors)
```

## Architecture

### Skills Registry (`skills/`)

Each skill is a folder containing one required file:

```
skills/
└── skill-name/
    └── SKILL.md          # Required: frontmatter + instructions
    └── (optional extras: examples/, templates/, scripts/, README.md)
```

**`SKILL.md` frontmatter** (validated by `tools/scripts/validate_skills.py`):

| Field | Required | Notes |
|---|---|---|
| `name` | Yes | Must match folder name, lowercase-with-hyphens |
| `description` | Yes | One sentence, under 200 chars |
| `risk` | Yes | `none` \| `safe` \| `critical` \| `offensive` \| `unknown` |
| `source` | Yes | `community`, `self`, or a URL |
| `source_type` | Yes | `official` \| `community` \| `self` |
| `source_repo` | When upstream | `OWNER/REPO` format |
| `date_added` | Yes | `YYYY-MM-DD` |

Every `SKILL.md` must include a `## When to Use` section (or an accepted variant) and a `## Limitations` section. Offensive skills (`risk: offensive`) must include an "Authorized Use Only" disclaimer.

### Derived / Generated Files

These files are **auto-generated** — never edit them directly:

- `CATALOG.md`, `skills_index.json`
- `data/` — all JSON files
- `plugins/` and `.agents/plugins/` — plugin bundle distributions
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- `apps/web-app/public/sitemap.xml`, `apps/web-app/public/skills.json.backup`

The canonical set is defined in `tools/config/generated-files.json`. On pushes to `main`, CI automatically regenerates and commits these files via `npm run sync:repo-state`.

### PR Source-Only Contract

**Pull requests must never include generated artifacts.** CI enforces this: if a PR diff touches any file in `derivedFiles`, it fails. Add or edit only source files (`skills/`, `docs/`, `tools/scripts/`, `apps/web-app/src/`, etc.). The main branch CI regenerates all derived outputs after merge.

### Toolchain (`tools/`)

- `tools/scripts/*.py` — Python scripts for validation, index generation, sync, auditing
- `tools/scripts/*.js` / `*.cjs` — Node scripts for catalog build, installer, release
- `tools/scripts/tests/` — Test suite (JS and Python); individual test files can be run directly
- `tools/lib/` — Shared Node libraries (`workflow-contract.js`, `project-root.js`, etc.)
- `tools/config/generated-files.json` — Defines the derived-file contract used by CI and `generated_files.js`
- `tools/requirements.txt` — Python deps (only `pyyaml>=6.0`)

### Web App (`apps/web-app/`)

React 19 + Vite + TypeScript + Tailwind CSS + Supabase. Skills data is injected at build time via `npm run app:setup`, which copies `skills_index.json` into `apps/web-app/public/skills.json`. The app is otherwise a standard Vite SPA with Vitest for tests.

### Plugins (`plugins/`)

Each subdirectory is a plugin bundle (for Claude Code or Codex marketplace distribution). These are generated by `npm run plugin-compat:sync` from source skills and are never edited by hand.

## Adding a Skill

1. `mkdir skills/your-skill-name`
2. Copy template: `cp docs/contributors/skill-template.md skills/your-skill-name/SKILL.md`
3. Fill in frontmatter and content
4. `npm run validate` — must pass with no new errors
5. `npm run security:docs` — required if skill includes shell commands, network calls, or token-like strings
6. Open a PR; include the Quality Bar Checklist from `.github/PULL_REQUEST_TEMPLATE.md`
7. Do **not** include `CATALOG.md`, `skills_index.json`, or `data/*.json` in the PR
