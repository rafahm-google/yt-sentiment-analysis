# Project Guidelines & Agent Memories

## 1. Cloud Build & Deployment Best Practices
- Always use a dedicated, self-contained .gcloudignore file to ensure build files (Dockerfile, requirements.txt, app.py, main.py, src/) are uploaded even if untracked or in .gitignore.
- Always build with --no-cache or unique timestamped image tags when deploying to Cloud Run.
- Always verify that gcloud run services describe reports Ready: True and traffic is serving 100% on the newly deployed revision.

## 2. Configuration & Text Parsing (ConfigParser)
- Always instantiate configparser.ConfigParser(interpolation=None) when reading or writing .ini configuration files. This prevents ValueError: invalid interpolation syntax when user briefings or inputs contain % characters (e.g. 100% arábica).

## 3. Streamlit Session State & UI Component Binding
- Always initialize session state keys independently at the top of app.py using key-by-key checks: if key not in st.session_state.
- When creating key-bound widgets (e.g. st.checkbox("...")), omit the redundant value parameter to avoid session state AttributeErrors when users reconnect to active sessions.
