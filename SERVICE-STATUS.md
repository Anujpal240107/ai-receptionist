# Native receptionist: sixteen-service status

Recorded 26 October 2026 (IST). The files under evidence/ contain timestamped test receipts and runtime fingerprints. No sixteen-of-sixteen public launch certificate is claimed.

The native app's real integration tests passed against both Supabase databases. Public HTTPS/WebSocket hosting and source-bound marketplace publication still require work. The earlier main marketplace browser-example badge is not used as evidence for this app.

| # | Service | Actual implementation / verification | Remaining public-launch condition |
|---|---|---|---|
| 1 | Proper data model | Eleven related tables, composite ownership FKs, fixed menu, repeatable migration executed twice, RLS on every table. | Carry the migration and source version into the native deployment. |
| 2 | Persistent storage | Real conversations/orders survive another login and a fresh Streamlit session. | Public-host end-to-end smoke test. |
| 3 | Customer separation | Another customer cannot access or mutate records through RPC, guessed identifiers or direct table reads/writes. Restored file RLS also tested. | Preserve these rules in every new release. |
| 4 | Accounts and sessions | Supabase Auth; refresh tested; real logout removes the session and database access is denied even with the old unexpired JWT. | Public signup/confirmation through the native host. |
| 5 | Permissions | Staff membership cannot be self-assigned; protected order transitions tested, including forbidden customer actions and invalid transitions. | Appoint the actual production restaurant operator. |
| 6 | Credentials | Runtime needs no service-role key. Secrets remain server-side; operator reads shared settings from existing Infisical and stores the local Groq key with Windows encryption. | Put the Groq key into the chosen host's protected configuration after explicit transfer approval. |
| 7 | Safe files | Native private order attachments; actual bytes, ownership, invalid type/path, size limit, deletion and restored access tested. | Verify private downloads in the public native session. |
| 8 | Input checks | PostgreSQL validates menu IDs, quantities, totals, contact fields, allowed keys and FKs. Malformed/oversized requests rejected; all database calls use parameters/RPC. | Keep negative checks in the deployment gate. |
| 9 | Connections/storage | Managed Supabase; verified TLS database connection and HTTPS service calls. Encrypted recovery archive restored successfully. | **Blocked:** native public HTTPS/WebSocket origin has not been deployed/tested. Provider at-rest controls are supplied by Supabase, not independently audited here. |
| 10 | Usage limits | Transactional PostgreSQL account budgets serialize concurrent mutations. Exactly five remaining daily order slots were used by nine simultaneous requests; four were rejected. Network failures fail closed. | Public multi-instance/provider allowance smoke test. |
| 11 | Dependencies | Forty-five runtime packages pinned; OSV returned no published advisories. Python unit checks passed; Dependabot/workflow files supplied. | Run the committed GitHub workflow after publishing the branch and repeat scans before release. |
| 12 | Safe configuration | Dev and release databases tested separately; strict project binding, CORS/XSRF on, development mode/static serving disabled, source watchers off. | **Partial:** chosen public host and protected production settings still need verification. |
| 13 | Backups/recovery | Actual native attachment bytes restored from AES-256-GCM archive into isolated PostgreSQL; all seven native policies and eleven RLS flags checked; owner allowed and other customer denied. | Preserve scheduled/offsite backup coverage and deletion replay at public cutover. Existing Windows backup schedule requires computer online/sign-in. |
| 14 | Logs/alerts | Real native Sentry event accepted HTTP 200. Customer-like sentinel, request/user/extra data removed. Bounded sanitized database audit categories tested. | Confirm alert routing/ownership for public operation. |
| 15 | Data lifecycle | Actual own-data export/delete includes order items and attachment bytes. Another customer remains isolated. Daily pg_cron retention installed and manually executed in dev and release. | Document and replay deletions when restoring older backup copies. |
| 16 | Release control | Original commit preserved, isolated repair branch, versioned SQL and dependency graph, source-bound test receipts, regression workflow supplied. | **Partial:** public native deployment, actual rollback and marketplace publication have not been exercised. |

No paid purchase, actual restaurant fulfillment or delivery service has been added. This does not claim that all unknown rough SaaS applications can be repaired automatically.

