# Deploying ClinicalSafe NIM Backend to Railway

This project is configured to be easily deployed to [Railway](https://railway.app/).

## Prerequisites
- Railway CLI installed (`npm i -g @railway/cli` or `brew install railway`)
- A Railway account

## Option 1: Deploy via Dashboard (Recommended)

1. Connect your GitHub repository in the Railway Dashboard.
2. Railway will detect the repository.
3. In the Service Settings:
   - Go to the **Settings** tab.
   - Under **Build**, change the **Root Directory** to `/backend`.
   - The builder should automatically detect the `Dockerfile`.
4. **Persistent Storage (Important!)**:
   - Go to the **Volumes** tab.
   - Add a new Volume.
   - Set the Mount Path to `/app/data` (this ensures your SQLite database isn't lost on every redeploy).
5. **Environment Variables**:
   - Go to the **Variables** tab.
   - Add `MASTER_KEY` with a strong secure password.
   - (Optional) Add `NVIDIA_API_KEY` if you want it seeded by default.

## Option 2: Deploy via CLI

1. Authenticate with Railway:
   ```bash
   railway login
   ```
2. Navigate to the backend directory:
   ```bash
   cd backend
   ```
3. Initialize the project:
   ```bash
   railway init
   ```
4. Link the deployment:
   ```bash
   railway up
   ```
5. Add a volume for the SQLite database so data persists:
   ```bash
   railway volume add --mount-path /app/data
   ```
6. Add environment variables:
   ```bash
   railway variables set MASTER_KEY="your-secure-key"
   railway variables set NVIDIA_API_KEY="your-nvidia-key"
   ```
7. Deploy the updates:
   ```bash
   railway up
   ```
