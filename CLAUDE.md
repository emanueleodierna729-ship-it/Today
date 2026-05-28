# CLAUDE.md

Questo file fornisce indicazioni a Claude Code (claude.ai/code) quando lavora con il codice in questo repository.

## Cos'è Questo Repository

**Antigravity Awesome Skills** è un catalogo di oltre 1.453 playbook agentici `SKILL.md` installabili in Claude Code, Gemini CLI, Cursor, Codex CLI e altri assistenti di coding basati su AI. Il repo include un installer CLI npm, bundle di plugin, una web app React per sfogliare le skill e una toolchain Python/Node per validare e generare gli artefatti derivati del registro.

## Comandi

Tutti gli script Python devono essere eseguiti tramite il wrapper Node (gestisce automaticamente venv/path):

```bash
node tools/scripts/run-python.js <python_script> [args]
```

### Validazione e Test

```bash
npm run validate                  # Valida tutti i file SKILL.md
npm run validate:strict           # Modalità strict (tratta i warning come errori)
npm run security:docs             # Scansione di sicurezza sul contenuto della doc (comandi shell, token, ecc.)
npm run test                      # Suite di test locale completa
npm run test:local                # Come npm run test
npm run validate:references       # Controlla i riferimenti incrociati tra doc/link
npm run check:warning-budget      # Applica il limite massimo di warning di validazione
npm run check:readme-credits      # Verifica i crediti README per le skill modificate
npm run audit:skills              # Verifica la qualità delle skill
```

Eseguire un singolo file di test JS direttamente:
```bash
node tools/scripts/tests/<test-file>.test.js
```

Eseguire un singolo test Python:
```bash
node tools/scripts/run-python.js tools/scripts/tests/<test-file>.py
```

### Build / Sincronizzazione degli Artefatti Derivati

```bash
npm run chain          # validate → plugin-compat sync → index → bundles → metadata
npm run build          # chain + catalog (tutti gli artefatti derivati eccetto web assets)
npm run catalog        # Genera solo CATALOG.md e data/catalog.json
npm run index          # Rigenera skills_index.json e data/*.json
```

Questi comandi rigenerano i **file derivati** che non devono mai essere modificati manualmente (vedi sotto).

### Web App

```bash
npm run app:setup      # Copia i dati delle skill nella cartella public della web app
npm run app:dev        # Server di sviluppo (esegue app:setup prima)
npm run app:install    # npm ci in apps/web-app/
npm run app:test       # Vitest (non-watch)
npm run app:test:coverage  # Copertura Vitest
npm run app:build      # Build di produzione
```

### Release (Solo Maintainer)

```bash
npm run release:preflight   # Controlli pre-release
npm run sync:repo-state     # Sincronizzazione completa del repo (derivati + web assets + contributors)
```

## Architettura

### Registro delle Skill (`skills/`)

Ogni skill è una cartella contenente un file obbligatorio:

```
skills/
└── nome-skill/
    └── SKILL.md          # Obbligatorio: frontmatter + istruzioni
    └── (opzionali: examples/, templates/, scripts/, README.md)
```

**Frontmatter di `SKILL.md`** (validato da `tools/scripts/validate_skills.py`):

| Campo | Obbligatorio | Note |
|---|---|---|
| `name` | Sì | Deve corrispondere al nome della cartella, lowercase-con-trattini |
| `description` | Sì | Una frase, max 200 caratteri |
| `risk` | Sì | `none` \| `safe` \| `critical` \| `offensive` \| `unknown` |
| `source` | Sì | `community`, `self`, o un URL |
| `source_type` | Sì | `official` \| `community` \| `self` |
| `source_repo` | Se upstream | Formato `OWNER/REPO` |
| `date_added` | Sì | `YYYY-MM-DD` |

Ogni `SKILL.md` deve includere una sezione `## When to Use` (o una variante accettata) e una sezione `## Limitations`. Le skill offensive (`risk: offensive`) devono includere il disclaimer "Authorized Use Only".

### File Derivati / Generati

Questi file sono **generati automaticamente** — non modificarli mai direttamente:

- `CATALOG.md`, `skills_index.json`
- `data/` — tutti i file JSON
- `plugins/` e `.agents/plugins/` — distribuzioni dei bundle di plugin
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- `apps/web-app/public/sitemap.xml`, `apps/web-app/public/skills.json.backup`

L'insieme canonico è definito in `tools/config/generated-files.json`. Ad ogni push su `main`, la CI rigenera e committa automaticamente questi file tramite `npm run sync:repo-state`.

### Contratto Source-Only per le PR

**Le pull request non devono mai includere artefatti generati.** La CI lo impone: se il diff di una PR tocca qualsiasi file in `derivedFiles`, fallisce. Aggiungere o modificare solo file sorgente (`skills/`, `docs/`, `tools/scripts/`, `apps/web-app/src/`, ecc.). La CI sul branch main rigenera tutti gli output derivati dopo il merge.

### Toolchain (`tools/`)

- `tools/scripts/*.py` — Script Python per validazione, generazione index, sync, auditing
- `tools/scripts/*.js` / `*.cjs` — Script Node per build del catalogo, installer, release
- `tools/scripts/tests/` — Suite di test (JS e Python); i singoli file di test possono essere eseguiti direttamente
- `tools/lib/` — Librerie Node condivise (`workflow-contract.js`, `project-root.js`, ecc.)
- `tools/config/generated-files.json` — Definisce il contratto dei file derivati usato dalla CI e da `generated_files.js`
- `tools/requirements.txt` — Dipendenze Python (solo `pyyaml>=6.0`)

### Web App (`apps/web-app/`)

React 19 + Vite + TypeScript + Tailwind CSS + Supabase. I dati delle skill vengono iniettati a build time tramite `npm run app:setup`, che copia `skills_index.json` in `apps/web-app/public/skills.json`. Per il resto è una SPA Vite standard con Vitest per i test.

### Plugin (`plugins/`)

Ogni sottodirectory è un bundle di plugin (per la distribuzione nel marketplace di Claude Code o Codex). Vengono generati da `npm run plugin-compat:sync` a partire dalle skill sorgente e non vengono mai modificati manualmente.

## Aggiungere una Skill

1. `mkdir skills/nome-skill`
2. Copia il template: `cp docs/contributors/skill-template.md skills/nome-skill/SKILL.md`
3. Compila frontmatter e contenuto
4. `npm run validate` — deve passare senza nuovi errori
5. `npm run security:docs` — obbligatorio se la skill include comandi shell, chiamate di rete o stringhe simili a token
6. Apri una PR; includi il Quality Bar Checklist da `.github/PULL_REQUEST_TEMPLATE.md`
7. **Non** includere `CATALOG.md`, `skills_index.json` o `data/*.json` nella PR
