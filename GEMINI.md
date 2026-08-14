# Project Guidelines & Agent Memories

## 1. Cloud Build & Deployment Best Practices
- Always use a dedicated, self-contained .gcloudignore file to ensure build files (Dockerfile, requirements.txt, app.py, main.py, src/) are uploaded even if untracked or in .gitignore.
- Always build with --no-cache or unique timestamped image tags when deploying to Cloud Run.
- Always execute gcloud run services update-traffic <service_name> --region <region> --to-latest on every deploy. If traffic remains pinned to an old revision ID, Cloud Run will serve 100% of live traffic from the legacy revision even if new builds succeed.
- Always verify that gcloud run services describe reports Ready: True and traffic is serving 100% on the newly deployed revision.

## 2. Configuration & Text Parsing (ConfigParser)
- Always instantiate configparser.ConfigParser(interpolation=None) when reading or writing .ini configuration files across all modules. This prevents ValueError: invalid interpolation syntax when user briefings or inputs contain % characters (e.g. 100% arábica, 100% elétricos).

## 3. Streamlit Session State & UI Progress Binding
- Always initialize session state keys independently at the top of app.py using key-by-key checks: if key not in st.session_state:.
- When creating key-bound widgets (e.g., st.checkbox("...", key="..."), st.slider("...", key="...")), omit the redundant value= parameter to avoid session state AttributeErrors when users reconnect to active sessions.
- Parse execution stdout for stage markers ([STAGE 1], [STAGE 2], Evaluating batch) to update st.progress and st.status_text dynamically in real time, preventing frozen UI progress states.

## 4. Git Repository & File Commitment Constraints
- NEVER commit build/deployment scratch files (Dockerfile, .dockerignore, .gcloudignore, cloudbuild.yaml, deploy.sh, scratch/, tests/) to Git or GitHub.
- Git repository MUST track strictly core source code (app.py, main.py, src/, templates/, config.ini.example, requirements.txt, README.md, GEMINI.md).

## 5. Google Drive API & Shared Drives Integration
- When querying files or verifying uploads inside Google Drive folders (especially Shared Drives), ALWAYS include 'supportsAllDrives': True AND 'includeItemsFromAllDrives': True in files().list() kwargs. Without includeItemsFromAllDrives=True, queries on subfolders in Shared Drives return empty items = [] causing false positive verification warnings.

## 6. Gemini LLM Selection & Fallback Hierarchy
- Strictly use Flash models for batch processing and semantic relevance filtering using the fallback sequence: gemini-3.7-flash -> gemini-3.6-flash -> gemini-3.5-flash.
- Avoid Pro models in automated batch sentiment extraction pipelines unless explicitly requested.
