# Email Tracking Solution Matrix

## Summary

| Dimension | Plunk | listmonk | Mautic | local_first_party |
|-----------|-------|----------|--------|-------------------|
| **License** | AGPL-3.0 | AGPL-3.0 | GPL-3.0 | MIT (our code) |
| **Language** | TypeScript (Node.js) | Go | PHP | Python |
| **Database** | PostgreSQL | PostgreSQL | MySQL/PostgreSQL | SQLite (our existing) |
| **Docker** | Yes | Yes | Yes | No (pip) |
| **Maintenance** | Active (July 2026) | Active (July 2026) | Active | N/A |
| **SMTP Relay** | Yes | Yes (via external) | Yes | No |
| **API Send** | Yes (REST) | Yes (REST) | Yes (REST) | No |
| **Open Tracking** | Yes | Yes | Yes | Yes |
| **Click Tracking** | Yes | Yes | Yes | Yes |
| **Delivery Events** | Analytics | Via webhook | Yes | Yes (smtp result) |
| **Bounce Handling** | Tracked | Webhook+multi-provider | Yes | Yes (smtp+bounce_log) |
| **Complaint/FBL** | Unclear | Unclear | Yes | No |
| **Unsubscribe** | Implied | Yes | Yes | Manual |
| **Inbound Reply** | Yes (June 2026) | No | Yes | Via IMAP monitor |
| **Webhook** | Unclear | Yes (bounce) | Yes | Yes (custom) |
| **Custom Domain** | Yes (DKIM/SPF) | Yes | Yes | Yes (Nginx proxy) |
| **Multi-tenant** | Unclear | Limited | Yes | N/A |
| **Event Export** | Unclear | API only | Yes (API+reports) | SQL (direct query) |
| **Message-ID Preserved** | Yes (header build) | Yes | Yes | Yes (ours) |
| **Per-email Track Toggle** | Unclear | Yes (config) | Yes | Yes (by design) |
| **SMTP Integration** | Acts AS relay | Connects TO relay | Acts AS relay | Post-send only |
| **Final Send Plan Compat** | Breaks model | Breaks model | Breaks model | Compatible |
| **Org First Outreach** | Destroys | Destroys | Destroys | Preserved |
| **DB Migration Risk** | Postgres required | Postgres required | MySQL/Postgres | SQLite, zero risk |
| **Ops Complexity** | Docker stack | Docker + Postgres | Docker + DB + cron | Single Python process |

## Recommendation: local_first_party (default production)

### Rationale

1. **No external database dependency.** SQLite is our existing store. Plunk/listmonk/Mautic all require PostgreSQL or MySQL — a breaking change.
2. **Final Send Plan preserved.** Our send plan is frozen at 22:30. External SMTP relays break the `plan_entry_id` → `send_log_id` → `organization_key` traceability chain.
3. **Organization-level first outreach limit preserved.** External platforms don't understand our `first_outreach_limit=1` rule.
4. **Zero migration risk.** All tracking tables are additive — no existing rows modified.
5. **Default disabled.** `EMAIL_ENGAGEMENT_PROVIDER=disabled` ensures zero production impact until explicitly enabled.
6. **Privacy-first.** No third-party tracking, no cookies, IP hashing, configurable retention.

### When to Re-evaluate Plunk

Plunk becomes viable only when ALL of:
- Production volume exceeds 500 emails/day (Postgres justified)
- Dedicated ops team available for Docker stack
- Full Plunk API integration tested in PoC
- AGPL-3.0 legal clearance obtained
- Final Send Plan model adapted to Plunk's campaign model
- Organization-level dedup re-implemented in Plunk workflow rules

### Mautic Exclusion

Mautic is over-engineered for our use case (full marketing automation platform). The PHP + MySQL stack introduces unnecessary complexity. Even in evaluation mode, the operational overhead is unjustified for 40-120 emails/day.

## Detailed Evaluations

### Plunk

- **Pros**: Modern TypeScript stack, active development, SMTP relay + API send, inbound email support, $0.001/email pricing if SaaS
- **Cons**: AGPL-3.0, PostgreSQL required, unclear per-email tracking disable, breaks our Frozen Plan model, no clear event-to-plan_entry_id mapping
- **PoC Status**: Isolated Docker PoC planned — see `docs/plunk_poc_report.md`

### listmonk

- **Pros**: Battle-tested (2,022+ commits), single Go binary, REST API, per-email tracking toggle, active maintenance
- **Cons**: AGPL-3.0, PostgreSQL required, single-instance design (no multi-tenant), no inbound reply handling, breaks Frozen Plan model
- **Evaluation**: Reserved for future comparison if volume grows beyond SQLite capacity

### local_first_party

- **Pros**: Zero external deps, SQLite native, pluggable provider interface, cryptography-safe token hashing, configurable retention, default disabled
- **Cons**: Requires Nginx + HTTPS for production tracking pixel, no built-in analytics dashboard, needs manual scaling beyond SQLite limits
- **Production Readiness**: Code complete, awaiting HTTPS domain, privacy policy, and explicit user approval before enabling
