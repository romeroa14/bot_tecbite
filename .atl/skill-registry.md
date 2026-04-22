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
- Always use issue templates; avoid blank issues.
- Open issues only for bugs/features; route generic Q&A to Discussions.
- Search duplicates before creating a new issue.
- Start issues with `status:needs-review`.
- Wait for `status:approved` before opening implementation PRs.
- For bugs, include reproducible steps and expected vs actual behavior.
- For features, include problem statement and proposed solution.

### branch-pr
- Link each PR to an approved issue using `Closes/Fixes/Resolves #N`.
- Use exactly one `type:*` label in each PR.
- Name branches as `type/description` using lowercase safe characters.
- Keep commit messages in Conventional Commits format.
- Run required checks before merge.
- Keep PR body complete (summary, changed files, test plan, checklist).
- Do not open PRs before issue-first workflow is satisfied.

### skill-creator
- Create skills only for reusable patterns, not one-off tasks.
- Use standard layout: `skills/<name>/SKILL.md` plus optional assets.
- Keep frontmatter complete: `name`, trigger-based description, license, metadata.
- Write critical patterns as direct, actionable rules.
- Prefer concise runnable examples over long narrative explanations.
- Store references locally when possible.
- Register newly created skills in project conventions when applicable.

### go-testing
- Prefer table-driven tests for deterministic logic.
- Test Bubbletea state transitions via direct `Model.Update()` calls.
- Use `teatest` for interactive TUI integration flows.
- Use golden files for stable UI rendering assertions.
- Cover happy path and failure path in each test suite.
- Use `t.TempDir()` for isolated filesystem tests.
- Validate with `go test ./...` and `go test -cover ./...`.

### judgment-day
- Run two blind judges in parallel for adversarial review.
- Resolve and inject compact rules into judge/fixer prompts first.
- Merge findings by confirmed, suspect, and contradiction buckets.
- Fix only confirmed critical/real warnings before re-judging.
- Report theoretical concerns as INFO, not blockers.
- Approve only when no confirmed critical or real warnings remain.
- Ask user before continuing beyond configured retry/escalation limits.

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| No convention index found | — | `agents.md`, `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `GEMINI.md`, and `copilot-instructions.md` were not found in project root. |

Read the convention files listed above for project-specific patterns and rules. All referenced paths have been extracted — no need to read index files to discover more.
