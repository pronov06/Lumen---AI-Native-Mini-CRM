# Deploying Lumen Mini CRM to the Internet for Free

This guide shows you how to deploy the entire Lumen Mini CRM (React frontend, CRM backend, Channel Simulator, and SQLite database) on the public internet **completely for free** (no credit card required, 100% free tier).

We use a single-container multi-process setup (`Dockerfile.free` managed by Nginx and Supervisor) with a local SQLite database and an in-memory event bus. This eliminates the need for external Postgres or Redis servers.

---

## 🚀 Option A: Hugging Face Spaces (Recommended for 24/7 Uptime)

Hugging Face Spaces allows you to host Docker containers for free, and they **stay online 24/7** without sleeping!

### Step-by-step Deployment

1. **Create a Hugging Face Account**: Go to [huggingface.co](https://huggingface.co/) and sign up.
2. **Create a New Space**:
   - Go to [huggingface.co/new-space](https://huggingface.co/new-space).
   - Give your Space a name (e.g. `lumen-crm`).
   - Select **Docker** as the SDK.
   - Select the **Blank** template (default).
   - Set the Space to **Public** (or **Private** if you only want you to access it).
   - Click **Create Space**.
3. **Configure the Space for Single Dockerfile**:
   - By default, Hugging Face expects the Dockerfile to be named `Dockerfile` in the root of the repository.
   - Since we have `Dockerfile.free` specifically for this, rename or copy it to `Dockerfile`:
     - Rename/copy `Dockerfile.free` to `Dockerfile`.
4. **Set your Gemini API Key**:
   - In your Hugging Face Space page, go to the **Settings** tab.
   - Scroll down to **Variables and secrets**.
   - Click **New secret**.
   - Set the name to `CRM_GEMINI_API_KEY` and paste your Gemini API Key as the value.
5. **Push the Code**:
   - Initialize a git repo (if not already done) and add the Space repository as a remote:
     ```bash
     git init
     git remote add origin https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
     ```
   - Commit all files and push:
     ```bash
     git add -A
     git commit -m "Configure single-container free deployment"
     git push -u origin main --force
     ```
6. **Wait for Build**:
   - Hugging Face will automatically detect the `Dockerfile`, build the image, and deploy it.
   - Once it shows **Running**, you can access the CRM dashboard directly in the embedded Space UI or open it full screen!

---

## ☁️ Option B: Koyeb Free Tier

Koyeb is a modern serverless container platform with a generous free tier (one free nano service, no credit card required in many regions).

### Step-by-step Deployment

1. **Sign up for Koyeb**: Go to [koyeb.com](https://www.koyeb.com/) and register.
2. **Create an App**:
   - Select **GitHub** deployment.
   - Search and select your repository.
   - In the configuration settings:
     - Set the builder type to **Dockerfile**.
     - Set the Dockerfile path to `Dockerfile.free` (or copy it to `Dockerfile` if you want it as the default).
3. **Configure Environment Variables**:
   - Add a variable: `CRM_GEMINI_API_KEY` = `[Your Gemini API Key]`.
   - Koyeb automatically exposes a `$PORT` environment variable. Our `entrypoint.sh` will automatically capture this variable and route Nginx to it.
4. **Deploy**:
   - Click **Deploy**.
   - Koyeb will compile your React app, build the container, and assign you a free public `https://[app-name].koyeb.app` URL.

---

## ⚡ Option C: Render Free Tier

Render offers free web service hosting from GitHub repositories. Note that free services on Render spin down (sleep) after 15 minutes of inactivity. When a new request arrives, it will take about 50 seconds to spin back up.

### Step-by-step Deployment

1. **Sign up for Render**: Go to [render.com](https://render.com/).
2. **Create a New Web Service**:
   - Click **New +** > **Web Service**.
   - Connect your GitHub repository.
3. **Configure the Web Service**:
   - **Runtime**: Select `Docker`.
   - **Docker Path**: Set it to `Dockerfile.free` (or copy `Dockerfile.free` to `Dockerfile` in the root).
   - **Instance Type**: Select **Free**.
4. **Add Environment Variables**:
   - Under the **Env** or **Environment** tab, click **Add Environment Variable**.
   - Key: `CRM_GEMINI_API_KEY`
   - Value: `[Your Gemini API Key]`
5. **Deploy**:
   - Click **Create Web Service**.
   - Render will build the image and deploy it.
   - Your site will be live at `https://[service-name].onrender.com`.

---

## 💾 Data Persistence Note

Since free container platforms (like Hugging Face Spaces, Koyeb, or Render) use ephemeral container filesystems, your SQLite database (`/srv/crm.db`) will reset back to the original seeded state whenever the container restarts or goes to sleep.

*   This is perfect for demoing the app to clients, portfolios, or showing reviewers.
*   The startup script will automatically check if the SQLite database is empty on boot and run the seed script to populate it with 240 customers and 984 orders. You will always have a working demo out of the box!
