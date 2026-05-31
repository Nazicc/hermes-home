---
name: ghcr-docker-auth-with-gh-token
description: "Authenticate to GHCR (GitHub Container Registry) using the GitHub CLI token, then pull images. Also handles large image timeout workarounds. NOT for: public images on Docker Hub, or environments where `gh` CLI is not authenticated."
category: general
---

# GHCR Docker Auth + Large Image Pull

## When to use
Pulling images from ghcr.io (GitHub Container Registry) when the image requires authentication, or when the image is large enough to exceed the terminal timeout.

## Step 1: Authenticate to GHCR

If `docker pull ghcr.io/...` fails with "UNAUTHORIZED" or "authentication required":

bash
# Get GitHub token and login to GHCR (non-interactive)
docker login ghcr.io -u nazicc -p "$(gh auth token)"


Or with `--password-stdin` to avoid credential storage warning:
bash
printf '%s' "$(gh auth token)" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin


Verify login succeeded:
bash
docker login ghcr.io  # should print "Login Succeeded"


## Step 2: Pull with Background Timeout Handling

For large images (ML models, full-stack apps), the pull will likely exceed the 600s foreground timeout. Use background mode:

bash
# Start pull in background
docker pull ghcr.io/NAMESPACE/IMAGE:TAG 2>&1 &
PULL_PID=$!
echo "Pull PID: $PULL_PID"

# Monitor progress
echo "Waiting for pull to complete..."
for i in $(seq 1 60); do
  sleep 10
  if ! kill -0 $PULL_PID 2>/dev/null; then
    echo "Pull completed at ${i}x10s"
    break
  fi
  # Check partial progress
  docker images "ghcr.io/NAMESPACE/IMAGE:TAG" --format "{{.Repository}}:{{.Tag}} {{.Size}}" 2>/dev/null || echo "Still pulling..."
done


Or use the terminal tool's built-in background mode:
bash
terminal({
  "command": "docker pull ghcr.io/NAMESPACE/IMAGE:TAG",
  "background": true,
  "notify_on_complete": true,
  "watch_patterns": ["Download complete", "Pull complete", "error", "Error", "fatal"]
})


## Step 3: Verify

After pull completes:
bash
docker images ghcr.io/NAMESPACE/IMAGE:TAG --format "{{.Repository}}:{{.Tag}} {{.Size}}"


## Common Issues

- **`gh auth token` returns empty**: Use `gh auth token --hostname github.com` explicitly, or check `gh auth status` to verify login state.
- **Image tag not found with `:latest`**: Try specific version tags. Check available tags via `gh api repos/NAMESPACE/IMAGE/releases --jq '.[].tag_name'`.
- **`docker pull --mirror` flag doesn't exist**: This flag does not exist in Docker CLI. Remove it.
- **Image very large (5GB+)**: Expect 5-15 minutes on typical connections. Use background mode.

## Notes
- GHCR images are often multi-GB because they bundle full Python/Node environments + ML models
- After first successful `docker login ghcr.io`, credentials are cached in `~/.docker/config.json`
- Use `http2=False` in httpx/OpenAI client configs when behind corporate proxies that interfere with HTTP/2 ALPN negotiation
