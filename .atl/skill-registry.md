# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

See `_shared/skill-resolver.md` for the full resolution protocol.

## User Skills

| Trigger | Skill | Path |
|---------|-------|------|
| When creating a GitHub issue, reporting a bug, or requesting a feature. | issue-creation | `/home/alfredo/.claude/skills/issue-creation/SKILL.md` |
| When creating a pull request, opening a PR, or preparing changes for review. | branch-pr | `/home/alfredo/.claude/skills/branch-pr/SKILL.md` |
| When user asks to create a new skill, add agent instructions, or document patterns for AI. | skill-creator | `/home/alfredo/.claude/skills/skill-creator/SKILL.md` |
| When writing Go tests, using teatest, or adding test coverage. | go-testing | `/home/alfredo/.claude/skills/go-testing/SKILL.md` |
| When user says "judgment day", "judgment-day", "review adversarial", "dual review", "doble review", "juzgar", "que lo juzguen". | judgment-day | `/home/alfredo/.claude/skills/judgment-day/SKILL.md` |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### issue-creation
- Always use issue templates; blank issues are not valid.
- Create issues only for bugs/features; route questions to Discussions.
- Search duplicates before opening a new issue.
- New issues must start with `status:needs-review`.
- A maintainer must add `status:approved` before PR work starts.
- Include reproducible steps and expected vs actual behavior for bugs.
- Include problem + proposed solution for features.

### branch-pr
- Every PR must link an approved issue (`Closes/Fixes/Resolves #N`).
- PR must have exactly one `type:*` label.
- Branch naming must follow `type/description` with lowercase safe chars.
- Commit messages must follow Conventional Commits.
- Run required checks before merge (validation + shellcheck when applies).
- Keep PR body complete: summary, changed files, test plan, checklist.
- Do not open PRs without issue-first workflow completion.

### skill-creator
- Create skills only for reusable, repeated patterns (not one-off tasks).
- Use standard structure: `skills/<name>/SKILL.md` (+ optional assets/references).
- Frontmatter must include `name`, description with trigger, `license`, metadata.
- Keep critical patterns explicit and actionable for agent execution.
- Prefer concise examples and executable commands over long explanations.
- Use local references for docs in `references/`, not web-only links.
- Register new skills in project convention index if one exists.

### go-testing
- Prefer table-driven tests for deterministic Go logic.
- Test Bubbletea state transitions directly via `Model.Update()`.
- Use `teatest` for interactive TUI integration flows.
- Use golden files for stable UI output assertions.
- Cover success and error paths explicitly in each test table.
- Use `t.TempDir()` for filesystem-safe test isolation.
- Run `go test ./...` and `go test -cover ./...` as default validation.

### judgment-day
- Run two independent blind judges in parallel; never sequential review.
- Resolve skill registry first and inject compact rules into judges/fixer prompts.
- Synthesize verdicts by confirmed vs suspect vs contradiction findings.
- Fix only confirmed critical/real warnings, then re-judge in parallel.
- Treat theoretical warnings as INFO (report, do not block approval).
- Never approve until thresholds pass (no confirmed criticals/real warnings).
- Ask user before continuing beyond iteration limits or escalation.

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| No convention index found | — | `agents.md`, `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `GEMINI.md`, and `copilot-instructions.md` were not found in project root. |

Read the convention files listed above for project-specific patterns and rules. All referenced paths have been extracted — no need to read index files to discover more.
