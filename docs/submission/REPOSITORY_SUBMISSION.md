# Source repository – preparation and evaluator access

## Current state (local)

The four projects are separate git repositories on the `integration` branch:

| Folder | History |
|---|---|
| `Marg-AppFrontend` | Original history + integration commits |
| `MARG-Mentor-Intelligence` | Original history + integration commits |
| `Marg-AppBackend` | Baseline snapshot (it had no git) + integration commits |
| `Marg-LLM` | Baseline snapshot (it had no git) + integration commits |

`deploy/`, `docs/`, `e2e/`, `scripts/` and the root `README.md` live in the
`D:\AI-MARG` folder, which is not a repository yet.

## Recommended: one private monorepo (history preserved)

A single repository is easier for evaluators. The commands below build it in a
**new** folder, so the existing repositories are not modified. Each project keeps
its history under its own sub-folder.

```bash
mkdir /d/marg-monorepo && cd /d/marg-monorepo && git init -b main
for p in Marg-AppFrontend Marg-AppBackend Marg-LLM MARG-Mentor-Intelligence; do
  git remote add $p /d/AI-MARG/$p && git fetch $p integration
  git merge --allow-unrelated-histories -s ours --no-commit $p/integration
  git read-tree --prefix=$p/ -u $p/integration
  git commit -m "Import $p (integration branch) with history"
  git remote remove $p
done
cp -r /d/AI-MARG/{README.md,docs,deploy,e2e,scripts} .
rm -rf e2e/node_modules e2e/test-results e2e/*.png
git add -A && git commit -m "Add root README, docs, deployment and e2e tests"
```

Before pushing, check that no secrets or large data are included:

```bash
git ls-files | grep -Ei '(^|/)\.env$|\.sqlite3$|chroma|\.pdf$|demo_credentials|local-integration' || echo "clean"
git count-objects -vH        # expect a few MB, not GB
```

The knowledge base (`Marg-LLM/data/`) is **not** in git: it is about 1 GB, and the
source PDFs belong to their publishers. Share it with the deployment server
separately (see DEPLOYMENT.md §5).

## Push to GitHub (private) – requires your action and approval

```bash
gh auth login                                   # once
gh repo create marg --private --source . --push
```

## Give the evaluator access (`csfEvaluation`)

```bash
gh api -X PUT repos/<your-github-username>/marg/collaborators/csfEvaluation -f permission=pull
```

Or in the browser: **Repository → Settings → Collaborators → Add people →
`csfEvaluation`**, with the *Read* role. The evaluator must accept the invitation.
The repository stays **private**. Do not make it public without deciding to.

## Share credentials safely

Send the demo password to evaluators through the submission form or a private
message, never in the repository, README or video.
