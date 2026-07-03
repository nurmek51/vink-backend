# Vink Backend

FastAPI backend for wallet and eSIM flows, prepared for deployment to Google Cloud Run through GitHub Actions.

## Local setup

1. Create `.env` from `.env.example`.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run locally:

```bash
uvicorn app.main:app --reload
```

If you use a local Firebase service account file, keep its path in `FIREBASE_CREDENTIALS_PATH`. In Google Cloud Run, Firebase Admin SDK will use the attached runtime service account automatically, so no JSON key file is required.

## Cloud Run CI/CD

The repository now includes:

- `Dockerfile` compatible with Cloud Run and dynamic `PORT`
- `.dockerignore` to keep secrets and local files out of the build context
- `.github/workflows/deploy-cloud-run.yml` for test + build + deploy
- `.env.example` as the configuration contract for local/dev/prod values

### Deployment flow

On every push to `main`:

1. GitHub Actions runs `pytest`.
2. The workflow authenticates to Google Cloud through Workload Identity Federation.
3. Docker image is built and pushed to Artifact Registry.
4. The image is deployed to Cloud Run.
5. Runtime secrets are pulled from Google Secret Manager.

## What must be created manually in Google Cloud

### 1. Enable APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com
```

### 2. Create Artifact Registry repository

```bash
gcloud artifacts repositories create vink-backend \
  --repository-format=docker \
  --location=YOUR_REGION
```

### 3. Create runtime service account for Cloud Run

```bash
gcloud iam service-accounts create vink-cloud-run
```

Grant it the minimum required roles:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:vink-cloud-run@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:vink-cloud-run@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

If your Firebase/Firestore setup requires broader permissions, adjust the role set accordingly.

### 4. Create deployer service account for GitHub Actions

```bash
gcloud iam service-accounts create github-deployer
```

Grant it deployment permissions:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-deployer@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-deployer@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-deployer@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

### 5. Configure Workload Identity Federation for GitHub Actions

Create a Workload Identity Pool and Provider, then allow your GitHub repository to impersonate the deployer service account.

You will need the provider resource name in this format:

```text
projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID
```

Then bind GitHub to the deployer service account:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  github-deployer@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/attribute.repository/YOUR_GITHUB_OWNER/YOUR_GITHUB_REPO"
```

### 6. Create Secret Manager secrets

Create these secrets in Google Cloud Secret Manager:

- `SECRET_KEY`
- `IMSI_USERNAME`
- `IMSI_PASSWORD`
- `ADMIN_API_KEY`
- `ADMIN_API_KEY_HASH`
- `EPAY_CLIENT_ID`
- `EPAY_CLIENT_SECRET`
- `EPAY_TERMINAL_ID`

Example:

```bash
printf 'your-secret-value' | gcloud secrets create SECRET_KEY --replication-policy=automatic --data-file=-
```

If a secret already exists, add a new version instead:

```bash
printf 'your-secret-value' | gcloud secrets versions add SECRET_KEY --data-file=-
```

Optional secrets if you want real Twilio verification instead of mock OTP:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_SERVICE_SID`

## What must be added in GitHub

### GitHub Secrets

- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOYER_SERVICE_ACCOUNT`

Example value for `GCP_DEPLOYER_SERVICE_ACCOUNT`:

```text
github-deployer@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### GitHub Variables

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `ARTIFACT_REGISTRY_REPOSITORY`
- `CLOUD_RUN_SERVICE`
- `CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT`
- `BACKEND_CORS_ORIGINS`
- `IMSI_API_URL`
- `EPAY_OAUTH_URL`
- `EPAY_API_URL`
- `EPAY_OAUTH_FALLBACK_URL`
- `EPAY_API_FALLBACK_URL`
- `EPAY_PAYMENT_PAGE_JS`
- `EPAY_POSTLINK_BASE_URL`
- `EPAY_CHECKOUT_BASE_URL`
- `EPAY_DEFAULT_BACK_LINK`
- `EPAY_DEFAULT_FAILURE_BACK_LINK`
- `EPAY_ESIM_AUTOPAY_ENABLED`
- `EPAY_ESIM_AUTOPAY_THRESHOLD_MB`
- `EPAY_ESIM_AUTOPAY_PACKAGE_MB`
- `EPAY_ESIM_AUTOPAY_COOLDOWN_MINUTES`
- `EPAY_HTTP_TIMEOUT_SECONDS`
- `EPAY_HTTP_RETRIES`
- `EPAY_REQUEST_DEADLINE_SECONDS`
- `EPAY_PENDING_TTL_MINUTES`

Recommended values:

- `ARTIFACT_REGISTRY_REPOSITORY`: `vink-backend`
- `CLOUD_RUN_SERVICE`: `vink-backend`
- `GCP_PROJECT_ID`: `bamboo-creek-481315-d5`
- `GCP_REGION`: `europe-west1`
- `CLOUD_RUN_RUNTIME_SERVICE_ACCOUNT`: `vink-cloud-run@bamboo-creek-481315-d5.iam.gserviceaccount.com`
- `BACKEND_CORS_ORIGINS`: `["https://app.vinksim.com","https://vink-sim.vercel.app","http://localhost:3000"]`

For the repository `nurmek51/vink-backend`, the Workload Identity binding must use:

```text
principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/attribute.repository/nurmek51/vink-backend
```

## Notes

- Do not store `.env` or Firebase JSON keys in the repository or Docker image.
- Cloud Run injects `PORT` automatically; the container is already configured for that.
- Firebase Admin SDK can use the Cloud Run service account via Application Default Credentials.
- If you want private access only, remove `--allow-unauthenticated` from the workflow.
- Mobile apps do not use browser CORS, so `BACKEND_CORS_ORIGINS` only needs web origins.
