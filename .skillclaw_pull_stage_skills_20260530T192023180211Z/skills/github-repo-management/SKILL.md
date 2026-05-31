---
name: github-repo-management
description: "Clone, create, fork, configure, and manage GitHub repositories. Manage remotes, secrets, releases, and workflows. Works with gh CLI or falls back to git + GitHub REST API via curl. NOT for: code review (use github-code-review), issue management (use github-issues), or CI/CD configuration."
category: skills
version: 1.1.0
...
author: Hermes Agent
...
license: MIT
...
metadata: {hermes: {related_skills: [github-auth, github-pr-workflow, github-issues], tags: [
      GitHub, Repositories, Git, Releases, Secrets, Configuration]}, sources: []}
---

---
name: github-repo-management
description: Clone, create, fork, configure, and manage GitHub repositories. Manage remotes, secrets, releases, and workflows. Works with gh CLI or falls back to git + GitHub REST API via curl. NOT for: code review (use github-code-review), issue management (use github-issues), or CI/CD configuration.
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  sources: []
  hermes:
    tags: [github, git, repo, clone, fork, secrets, releases, workflows]
    related_skills: [github-code-review, github-issues, github-pr-workflow, github-auth]
---

## Tools

### GitHub CLI (preferred)

gh repo clone <owner/repo>
gh repo create [--private|--public] <name>
gh repo fork <owner/repo>
gh repo edit <owner/repo> --add-topic <topic>
gh secret set <name> --body <value>
gh release create <tag> --title <title> --notes <notes>


### Git + GitHub REST API (fallback)
bash
# Clone
git clone https://github.com/<owner>/<repo>.git

# Create repo via API
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/user/repos \
  -d '{"name":"<repo>","private":true}'

# Fork via API
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/<owner>/<repo>/forks


## Common Rationalizations

- "I'll just use the web interface" — the CLI/API is faster for batch operations and scripting
- "gh is not installed so I can't do this" — git + curl fallback works without gh
- "I need to share credentials" — use gh auth login or environment tokens instead of sharing
- "I forgot the repo is private" — gh automatically handles private repo visibility

## Quality Red Lines

- Never commit secrets to git history even in private repos — use GitHub Secrets
- Always confirm before force-pushing to shared branches
- Verify repo visibility (public/private) before creating

