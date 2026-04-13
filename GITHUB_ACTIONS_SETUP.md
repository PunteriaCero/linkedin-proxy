# 🚀 GitHub Actions Deployment Guide

## Status

✅ **Workflow created and pushed to GitHub**
- Commit: db156ad
- Workflow file: `.github/workflows/deploy-portainer.yml`
- Status: Ready for activation

## 🎯 What This Does

The GitHub Actions workflow automatically deploys the LinkedIn API to Portainer whenever you push to master.

### Automated Flow:

```
git push → GitHub Actions triggers
    ↓
Validates docker-compose.yml
    ↓
Tests Portainer connectivity
    ↓
Deploys stack to Portainer
    ↓
Verifies container status
    ↓
Runs health checks
    ↓
Reports deployment status
```

## ⚙️ Setup Instructions

### Step 1: Add Portainer Token to GitHub Secrets

1. **Open GitHub:**
   ```
   https://github.com/PunteriaCero/linkedin-proxy/settings/secrets/actions
   ```

2. **Click "New repository secret"**

3. **Add the secret:**
   - **Name:** `PORTAINER_TOKEN`
   - **Value:** `ptr_yrEIS3/ZQKfYtJkcYc97dN4u0XPDpvY9TRFmtU3cNn0=`

4. **Click "Add secret"**

### Step 2: Trigger the Workflow

The workflow will auto-trigger on the next push. Or manually trigger:

1. **Go to Actions tab:**
   ```
   https://github.com/PunteriaCero/linkedin-proxy/actions
   ```

2. **Select "🐳 Deploy to Portainer"**

3. **Click "Run workflow"**

4. **Select branch: master**

5. **Click "Run workflow"**

## 📊 Monitoring Deployment

### View Workflow Status:
```
https://github.com/PunteriaCero/linkedin-proxy/actions
```

### Check Container:
```
http://192.168.0.214:9000/#!/docker/containers
```

### Access Service:
```
http://192.168.0.214:8000/consumer-ui.html
```

## 📋 Workflow Details

### Triggers:
- ✅ Push to `master` branch
- ✅ Changes to `docker-compose.yml`, `Dockerfile`, `main.py`
- ✅ Manual trigger via "Run workflow"

### Workflow Steps:

1. **Checkout code** - Clone the repository
2. **Verify files** - Check Dockerfile, docker-compose.yml, main.py
3. **Prepare compose** - Validate docker-compose syntax
4. **Test connectivity** - Verify Portainer is reachable
5. **Build/Deploy** - Create and deploy the container
6. **Verify container** - Check if container is running
7. **Health check** - Test service is responding
8. **Summary** - Report deployment status

### Outputs:

After successful deployment:
- 🐳 Container: `ia-linkedin-api`
- 📍 Stack: `linkedin-api-gateway`
- 🌐 Service: `http://192.168.0.214:8000`
- ✅ Status: Deployed and running

## 🔄 Deployment Flow

### On Each Push to Master:

```
1. Workflow triggers automatically
2. Validates all files
3. Tests Portainer connection
4. Deploys docker-compose.yml
5. Waits for container startup (10s)
6. Verifies container is running
7. Performs health checks
8. Reports final status
```

### Container Lifecycle:

```
1. New container created: ia-linkedin-api
2. Port 8000 exposed and mapped
3. Environment variables set
4. Startup check: /health endpoint
5. Container ready for use
```

## 🛠️ Manual Deployment (Fallback)

If workflow fails, deploy manually:

### Option 1: Docker Compose
```bash
cd /home/node/.openclaw/workspace/linkedin-n8n-gateway
docker-compose build
docker-compose up -d
```

### Option 2: Portainer UI
```
1. http://192.168.0.214:9000
2. Stacks → Add Stack
3. Paste docker-compose.yml
4. Deploy
```

### Option 3: Deploy Scripts
```bash
# Via Portainer API
./deploy-portainer.sh

# Via local docker-compose
./deploy-local.sh
```

## 📈 Workflow Statistics

- **Current Status:** ✅ Ready
- **Last Deploy:** Workflow available, not yet run
- **Container:** ia-linkedin-api (not running)
- **Service:** http://192.168.0.214:8000 (awaiting deployment)

## 🔐 Security

### Token Management:
- ✅ Token stored in GitHub Secrets (encrypted)
- ✅ Not visible in logs
- ✅ Only accessible during workflow execution
- ✅ Rotatable if needed

### Best Practices:
1. Never commit tokens to code
2. Use GitHub Secrets for sensitive data
3. Rotate tokens periodically
4. Audit workflow runs

## 📝 Next Steps

1. ✅ Add `PORTAINER_TOKEN` to GitHub Secrets
2. ⏳ Push code or manually trigger workflow
3. 📊 Monitor deployment in Actions tab
4. 🌐 Access service at http://192.168.0.214:8000/consumer-ui.html
5. ✅ Verify container in Portainer

## 🎯 Success Indicators

Deployment is successful when:
- ✅ Workflow shows "✓" (green checkmark)
- ✅ Container `ia-linkedin-api` is running
- ✅ Service responds to health checks
- ✅ Web UI loads at port 8000

## 🆘 Troubleshooting

### Workflow fails with 405 error:
- Portainer API has limitations with stacks endpoint
- Fallback to manual docker-compose deployment

### Container doesn't start:
- Check logs: `docker logs ia-linkedin-api`
- Verify credentials in config.json
- Ensure port 8000 is available

### Service not responding:
- Wait 15-20 seconds for full startup
- Check container health: `docker inspect ia-linkedin-api`
- View logs for errors

---

## 📚 References

- **Repository:** https://github.com/PunteriaCero/linkedin-proxy
- **Workflow File:** `.github/workflows/deploy-portainer.yml`
- **Portainer URL:** http://192.168.0.214:9000
- **Service URL:** http://192.168.0.214:8000
- **Secrets URL:** https://github.com/PunteriaCero/linkedin-proxy/settings/secrets/actions

---

**Status:** ✅ Ready for deployment via GitHub Actions
