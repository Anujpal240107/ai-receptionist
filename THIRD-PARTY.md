# Upstream components

This integration uses the actual supported services/SDKs:

- PostgreSQL database, relations, migrations, RLS, transactions and quotas.
- Supabase managed database, Auth and REST API. The native runtime authenticates as the actual user, without a service-role bypass.
- Streamlit Python interface and Groq Python SDK. Pinned versions are in requirements.txt.
- Sentry Python SDK with whitelisted event transmission.
- OSV advisory database and GitHub Dependabot/Actions maintenance configuration.
- Existing Ugly SaaS Infisical operator connection for shared service settings. Native consumer code does not receive machine-identity credentials.

Runtime distribution notices/licenses remain in the official installed packages. This repository does not vendor upstream source or include an upstream project's paid/enterprise code. These integrations are not an assertion of equivalent security to a reference vendor.

Official sources:
https://github.com/streamlit/streamlit
https://github.com/groq/groq-python
https://github.com/supabase/supabase
https://github.com/supabase/auth
https://github.com/postgres/postgres
https://github.com/getsentry/sentry-python
https://github.com/google/osv.dev
https://github.com/Infisical/infisical

Original user-owned app commit: 6f5750d15fff36a9bbd218c6036d1d879f7b837b.

