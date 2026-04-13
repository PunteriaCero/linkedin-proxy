# 🐳 Docker Build & Push Workflow Guide

## Status

✅ **Workflow created and ready for activation**
- File: `.github/workflows/build-docker-image.yml`
- Status: Awaiting DOCKER_USERNAME organization secret
- Activation: Ready for setup

## What This Does

Automatically builds and pushes Docker images to DockerHub whenever you push code changes.

### Automated Flow:

```
git push master
    ↓
Changes detected (Dockerfile, requirements.txt, main.py)
    ↓
GitHub Actions triggers build workflow
    ↓
1. Checkout code
2. Set up Docker Buildx
3. Login to DockerHub
4. Build Docker image
5. Push to DockerHub
    ↓
Image available: dockerusername/linkedin-api:latest
    ↓
Portainer can pull image automatically
    ↓
Ready for deployment
```

## 🔧 Setup Instructions

### Step 1: Add DOCKER_USERNAME Organization Secret

1. **Go to Organization Settings:**
   ```
   https://github.com/organizations/PunteriaCero/settings/secrets/actions
   ```

2. **Click "New organization secret"**

3. **Add the secret:**
   - **Name:** `DOCKER_USERNAME`
   - **Value:** Your DockerHub username (same user who created DOCKER_PAT)

4. **Save**

Note: `DOCKER_PAT` is already configured at organization level.

### Step 2: Update docker-compose.yml (Optional)

To use DockerHub image instead of building locally:

```yaml
services:
  linkedin-api:
    image: ${DOCKER_USERNAME}/linkedin-api:latest  # Use DockerHub image
    container_name: ia-linkedin-api
    ports:
      - "8000:8000"
    ...
```

### Step 3: Trigger Build (Optional)

The workflow will auto-trigger on next push. Or manually:

1. **Go to Actions tab:**
   ```
   https://github.com/PunteriaCero/linkedin-proxy/actions
   ```

2. **Select "🐳 Build and Push Docker Image"**

3. **Click "Run workflow"**

4. **Select branch: master**

5. **Click "Run workflow"**

## 📊 Monitoring Build

### View Build Logs:
```
https://github.com/PunteriaCero/linkedin-proxy/actions
→ "🐳 Build and Push Docker Image"
→ [Run ID]
→ Logs
```

### Check DockerHub:
```
https://hub.docker.com/r/{DOCKER_USERNAME}/linkedin-api
```

### Pull Image Locally:
```bash
docker pull {DOCKER_USERNAME}/linkedin-api:latest
```

## 🎯 Workflow Triggers

### Automatic:
- ✅ Push to `master` branch
- ✅ Changes to `Dockerfile`
- ✅ Changes to `requirements.txt`
- ✅ Changes to `main.py`
- ✅ Changes to `.github/workflows/build-docker-image.yml`

### Manual:
- ✅ GitHub UI Actions → Run workflow
- ✅ Workflow dispatch with options

## 📋 Workflow Details

### Build Configuration:
- **Base image:** python:3.11-slim (from Dockerfile)
- **Multi-stage build:** Optimized for production
- **Layer caching:** Speeds up subsequent builds
- **Tags:** latest, branch-sha, semver

### Push Configuration:
- **Registry:** docker.io (DockerHub)
- **Authentication:** DOCKER_PAT (organization secret)
- **Credentials:** Automatically injected by GitHub Actions

### Image Tags:
```
{DOCKER_USERNAME}/linkedin-api:latest
{DOCKER_USERNAME}/linkedin-api:master-{git-sha}
{DOCKER_USERNAME}/linkedin-api:buildcache
```

## 🔄 CI/CD Integration

### Full Pipeline:

```
Commit → Push
    ↓
[Build Docker Image]
    ↓
Image tagged and pushed to DockerHub
    ↓
[Deploy to Portainer] (existing workflow)
    ↓
Portainer pulls DockerHub image
    ↓
Container deployed and running
```

## 📈 Performance Tips

### Build Speed:
- Layer caching reduces build time by ~80%
- Buildx multi-platform support (optional)
- Parallel builds if multiple workflows

### Image Size:
- Python 3.11-slim base: ~125MB
- Final image: ~400-500MB (with dependencies)
- Tag latest + SHA for version tracking

## 🛠️ Manual Build (Fallback)

If workflow fails, build locally:

```bash
# Build image
docker build -t {DOCKER_USERNAME}/linkedin-api:latest .

# Login to DockerHub
docker login

# Push image
docker push {DOCKER_USERNAME}/linkedin-api:latest
```

## 🔐 Security

### Secrets Management:
- ✅ DOCKER_PAT stored in organization secrets (encrypted)
- ✅ DOCKER_USERNAME stored in organization secrets
- ✅ Never visible in logs
- ✅ Only accessible during workflow execution
- ✅ Rotatable if needed

### Best Practices:
1. Use personal access token (PAT) with minimal scopes
2. Rotate secrets periodically
3. Audit workflow runs
4. Use branch protection

## 📝 Next Steps

1. ✅ Add `DOCKER_USERNAME` to organization secrets
2. ✅ Push code or manually trigger workflow
3. 📊 Monitor build in Actions tab
4. 🐳 Check image on DockerHub
5. 🚀 Deploy via Portainer

## 🎯 Success Indicators

Build is successful when:
- ✅ Workflow shows "✓" (green checkmark)
- ✅ Image appears on DockerHub
- ✅ Image tags: latest, branch-sha, buildcache
- ✅ Ready for Portainer deployment

## 🆘 Troubleshooting

### Workflow fails with auth error:
- Verify DOCKER_PAT is valid
- Check DOCKER_USERNAME is correct
- Ensure secrets are organization-level

### Image not appearing on DockerHub:
- Check workflow logs for errors
- Verify push is enabled (default: true)
- Check DockerHub account permissions

### Build takes too long:
- First build is slower (no cache)
- Subsequent builds use layer cache
- Multi-platform builds take longer

---

## 📚 References

- **Workflow File:** `.github/workflows/build-docker-image.yml`
- **Repository:** https://github.com/PunteriaCero/linkedin-proxy
- **Organization Secrets:** https://github.com/organizations/PunteriaCero/settings/secrets/actions
- **DockerHub:** https://hub.docker.com
- **Buildx Docs:** https://docs.docker.com/build/buildx/

---

**Status:** ✅ Ready for DOCKER_USERNAME configuration and activation
