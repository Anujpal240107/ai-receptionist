# AI Restaurant Receptionist × Ugly SaaS

This is the native Python integration of the original Streamlit/Groq restaurant receptionist. It preserves Python, Streamlit, Groq, the English menu conversation and the fixed INR menu. Ugly SaaS adds an authenticated backend and durable, validated orders.

**Current state: working and tested local native app, with real hosted Supabase integration. Public Python deployment and marketplace publication are not complete.** See SERVICE-STATUS.md for all sixteen areas. An integration-test count is not a claim that every public launch condition passed.

## What changed

- Supabase Auth sign-in, signup, refresh and sign-out. User access and refresh tokens remain in the Streamlit server session.
- Eleven PostgreSQL tables with relationships, RLS, account ownership and a database migration. Seven native read policies. Direct client writes are denied.
- Persistent conversations, messages, orders and menu items. A new server session reloads saved work.
- A separate restaurant-operator role. Only appointed staff can view the restaurant's order desk and perform allowed status transitions.
- Authoritative menu validation, quantity limits, totals and idempotent confirmation. Chat never authorizes an order or collects money.
- Private order attachments: 256 KB each, 10 per order and 5 MB per account. Bytes are saved under owner policies in PostgreSQL and included in the same encrypted recovery snapshot.
- Atomic database quotas across processes. Chat has a per-account allowance of 10 turns/minute and 100/day; orders 5/minute and 30/day.
- A bounded Groq context, request timeout and output allowance. Customer chat is sent to Groq only after the UI consent checkbox. Delivery-form details are not automatically sent to Groq.
- Export and deletion of the customer's actual conversations/orders/items/files, plus a daily retention job.
- Whitelisted Sentry error events without request bodies, prompts, cookies, credentials or customer records.
- Pinned Python dependency graph, advisory checks, unit/UI tests and a GitHub Actions workflow.

## Run

Use Python 3.12:

    python -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt
    .venv\Scripts\python -m streamlit run app.py

On macOS/Linux, use .venv/bin/python instead. Configure server secrets before accepting orders. Use .env.example as a list of setting names; the app reads environment variables or .streamlit/secrets.toml, not a plain .env automatically.

Required settings: SUPABASE_URL, EXPECTED_SUPABASE_PROJECT and SUPABASE_PUBLISHABLE_KEY. Use only the public/anon key here; this runtime does not use a Supabase service-role key. Apply migrations/001_receptionist.sql to the intended Supabase project with the database administrator's connection.

For AI chat, set GROQ_API_KEY and GROQ_MODEL privately on the server. Choose a model available to your actual Groq account. Missing AI configuration is shown honestly; structured order placement works independently.

For a public release, set RECEPTION_ENV=production and RECEPTION_ORIGIN to the actual HTTPS URL. Use a WebSocket-capable Python/Streamlit host. The existing Vercel/browser importer does not run Streamlit.

In the existing Ugly SaaS workspace, Start-Receptionist.cmd uses the private operator's Infisical connection and Windows-encrypted Groq configuration. Those operator credentials are not included in this repository.

## Customer flow

1. Sign in, then start a conversation.
2. Use Receptionist for AI menu assistance. Chat messages require consent to be sent to Groq.
3. In Order, choose quantities and enter the name, phone, delivery address and payment preference.
4. Review the details and confirm once. Only the saved database receipt means an order was placed.
5. Return to My orders to reload the receipt or add/download/delete a private attachment.
6. Use My data to export or delete the active receptionist data.

The menu is Pizza INR 200, Burger INR 150, Pasta INR 180 and Cold Drink INR 50. A payment preference remains **unpaid**. There is no payment processor, delivery integration, live merchant inventory or claim of actual food fulfillment.

Staff must be appointed by the database operator in reception_staff; customers cannot appoint themselves. The operator can accept a placed order, complete an accepted order or cancel it. Staff cannot edit quantities, totals or payment status.

## Verification

    python -m unittest tests.test_services -v
    python -m scripts.audit_dependencies
    python -m compileall -q app.py ugly_services

The real hosted integration runner belongs to the Ugly SaaS operator workspace at work/verify-receptionist-hosted.mjs. It creates isolated synthetic users, exercises direct API/RLS bypass attempts, quotas, files, export/deletion, sign-out and the real Streamlit UI, then removes the users. The optional recovery test restores actual attachment bytes into a temporary PostgreSQL database.

Do not put privileged database credentials in a public GitHub Actions workflow. tests/test_ui.py requires disposable hosted credentials and is skipped without them. The hosted tests were run against both the development and isolated release databases.

## Privacy and recovery

Conversation/order/attachment retention is 90 days from conversation creation. Security events are retained 30 days; usage buckets two days. Account-wide deletion of the shared Ugly SaaS identity is handled by the platform; the native app's delete button deletes only its own app data and leaves the shared login intact.

Encrypted backup copies have a seven-day policy with at least three verified copies. Offline maintenance can retain copies longer. Deleting active data does not retroactively erase previously downloaded exports or encrypted backups. A disaster restoration must reapply deletion requests before reopening service. The existing operator backup schedule depends on the Windows computer being online and the user signed in.

Downloads are created as data URLs through an authorized Streamlit session. No public Streamlit media URL is created for private attachment bytes. Sharing or downloading those bytes creates a copy outside the app's custody. Attachments are downloaded, never executed or rendered as HTML.

## Support boundary

This reviewed adapter supports this restaurant conversation/order application and its declared model. It is not an automatic repair engine for arbitrary Python applications. The source intake on the main marketplace still needs a native deployment/publication integration before this app can be listed as publicly usable.

Supabase/PostgreSQL/Auth, Streamlit, Groq and Sentry are their established upstream implementations; they are not counterfeit recreations of proprietary services. App-specific SQL, validation and integration code is maintained here. See THIRD-PARTY.md.

