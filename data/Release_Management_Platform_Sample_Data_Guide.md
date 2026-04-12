# Release Management Platform — Sample Data & Test Environment Setup Guide

**Document Version:** 1.0  
**Date:** April 8, 2026  
**Purpose:** Define exactly what data developers must populate in Jira, Confluence, and ServiceNow to build, test, and validate each milestone of the Release Management Platform.

---

## How to Use This Guide

For each milestone, this guide specifies the exact data structures, sample records, and scenarios that must exist in your Jira, Confluence, and ServiceNow sandbox/test instances. Developers should populate this data before beginning development on each milestone. The data builds cumulatively — MVP data remains and is extended in subsequent milestones.

The guide uses 4 fictional projects that represent realistic enterprise diversity:

| Project | Jira Key | Description | Complexity | Team |
|---------|----------|-------------|-----------|------|
| Project Atlas | ATLAS | Payment processing microservice upgrade | High — critical system, DB migration, multiple dependencies | Team Alpha (8 people) |
| Project Beacon | BEACON | Customer portal UI redesign | Medium — frontend-heavy, no DB changes, 1 dependency | Team Beta (5 people) |
| Project Cipher | CIPHER | Security audit remediation (API gateway hardening) | High — infrastructure changes, shared middleware | Team Gamma (4 people) |
| Project Delta | DELTA | Internal reporting dashboard enhancement | Low — standalone, no dependencies, minimal risk | Team Delta (3 people) |

These 4 projects cover the spectrum: high/medium/low risk, with and without dependencies, with and without DB migrations, varying team sizes and readiness levels.

---

## MVP Data Setup — MCP Foundation + Release Dashboard

### Jira Data

**Fix Versions to Create:**

Create a Fix Version in each of the 4 projects:

| Jira Project | Fix Version Name | Release Date | Description |
|-------------|-----------------|-------------|-------------|
| ATLAS | v3.2 — May 2026 Release | 2026-05-16 | Payment service upgrade with PCI compliance fixes |
| BEACON | v2.0 — May 2026 Release | 2026-05-16 | Customer portal complete redesign |
| CIPHER | v1.5 — May 2026 Release | 2026-05-16 | API gateway security hardening |
| DELTA | v4.1 — May 2026 Release | 2026-05-16 | Reporting dashboard enhancements |

**Tickets to Create per Project:**

For each project, create tickets that represent different readiness states. This is critical — you need projects at varying levels of readiness to test dashboard visualization.

**Project Atlas (ATLAS) — Partially Ready (Amber)**

| Ticket Key | Type | Summary | Status | Priority | Assignee | Linked To |
|-----------|------|---------|--------|----------|----------|-----------|
| ATLAS-101 | Story | Implement PCI-compliant tokenization for card data | Done | High | Dev1 | Test: ATLAS-201 |
| ATLAS-102 | Story | Migrate payment_transactions table to new schema | Done | High | Dev2 | Test: ATLAS-202, Blocks: BEACON-105 |
| ATLAS-103 | Story | Update payment gateway API integration | In Progress | High | Dev3 | Test: ATLAS-203, Depends on: CIPHER-104 |
| ATLAS-104 | Story | Add retry logic for failed payment callbacks | Done | Medium | Dev1 | Test: ATLAS-204 |
| ATLAS-105 | Story | Implement audit logging for payment events | To Do | Medium | Dev4 | No test linked |
| ATLAS-106 | Bug | Race condition in concurrent payment processing | Open | Critical | Dev2 | — |
| ATLAS-107 | Bug | Memory leak in connection pool under load | Open | Blocker | Dev3 | — |
| ATLAS-108 | Task | Database migration script for payment_transactions | Done | High | Dev2 | — |
| ATLAS-109 | Task | Update API documentation for v3.2 endpoints | In Progress | Low | Dev4 | — |

Test Execution Tickets (linked to stories):

| Ticket Key | Type | Summary | Status | Linked To |
|-----------|------|---------|--------|-----------|
| ATLAS-201 | Test Execution | Test PCI tokenization — functional | Passed | ATLAS-101 |
| ATLAS-202 | Test Execution | Test schema migration — data integrity | Passed | ATLAS-102 |
| ATLAS-203 | Test Execution | Test gateway API — integration | Not Started | ATLAS-103 |
| ATLAS-204 | Test Execution | Test retry logic — edge cases | Passed | ATLAS-104 |

Why this data matters: Atlas has 2 open critical/blocker bugs (dashboard should show Red for blockers), 1 story still In Progress, 1 story with no linked test (QA coverage gap), and a cross-project dependency on CIPHER. This tests the full range of readiness indicators.

**Project Beacon (BEACON) — Mostly Ready (Green/Amber)**

| Ticket Key | Type | Summary | Status | Priority | Assignee | Linked To |
|-----------|------|---------|--------|----------|----------|-----------|
| BEACON-101 | Story | Redesign customer dashboard layout | Done | High | Dev5 | Test: BEACON-201 |
| BEACON-102 | Story | Implement responsive mobile view | Done | High | Dev6 | Test: BEACON-202 |
| BEACON-103 | Story | Add dark mode theme support | Done | Medium | Dev5 | Test: BEACON-203 |
| BEACON-104 | Story | Migrate to new component library | Done | High | Dev7 | Test: BEACON-204 |
| BEACON-105 | Story | Integrate with updated payment API | In Progress | High | Dev6 | Is blocked by: ATLAS-102 |
| BEACON-106 | Bug | CSS rendering issue in Safari | Open | Medium | Dev7 | — |

Test Execution Tickets:

| Ticket Key | Type | Summary | Status | Linked To |
|-----------|------|---------|--------|-----------|
| BEACON-201 | Test Execution | Test dashboard layout — cross-browser | Passed | BEACON-101 |
| BEACON-202 | Test Execution | Test mobile responsiveness | Passed | BEACON-102 |
| BEACON-203 | Test Execution | Test dark mode — accessibility | Passed | BEACON-103 |
| BEACON-204 | Test Execution | Test component library migration | Passed | BEACON-104 |

Why: Beacon is mostly done but has a dependency on Atlas (BEACON-105 blocked by ATLAS-102). This tests cross-project dependency display.

**Project Cipher (CIPHER) — Not Ready (Red)**

| Ticket Key | Type | Summary | Status | Priority | Assignee | Linked To |
|-----------|------|---------|--------|----------|----------|-----------|
| CIPHER-101 | Story | Implement WAF rules for API gateway | In Progress | Critical | Dev8 | Test: CIPHER-201 |
| CIPHER-102 | Story | Add mTLS authentication between services | To Do | High | Dev9 | No test linked |
| CIPHER-103 | Story | Implement rate limiting on public endpoints | To Do | High | Dev8 | No test linked |
| CIPHER-104 | Story | Harden API gateway configuration | In Progress | Critical | Dev9 | Blocks: ATLAS-103 |
| CIPHER-105 | Bug | TLS certificate chain validation failing in staging | Open | Blocker | Dev8 | — |
| CIPHER-106 | Bug | Rate limiter incorrectly counting internal traffic | Open | Critical | Dev9 | — |
| CIPHER-107 | Bug | JWT token validation bypass on edge case | Open | Blocker | Dev8 | — |

Test Execution Tickets:

| Ticket Key | Type | Summary | Status | Linked To |
|-----------|------|---------|--------|-----------|
| CIPHER-201 | Test Execution | Test WAF rules — penetration test | Not Started | CIPHER-101 |

Why: Cipher is in bad shape — 2 blockers, 1 critical bug, most stories not done, almost no QA coverage. Dashboard should light up Red across the board. This validates that the dashboard correctly surfaces severe readiness issues.

**Project Delta (DELTA) — Fully Ready (Green)**

| Ticket Key | Type | Summary | Status | Priority | Assignee | Linked To |
|-----------|------|---------|--------|----------|----------|-----------|
| DELTA-101 | Story | Add export-to-PDF for monthly reports | Done | Medium | Dev10 | Test: DELTA-201 |
| DELTA-102 | Story | Implement date range filter on dashboards | Done | Medium | Dev10 | Test: DELTA-202 |
| DELTA-103 | Story | Add chart type selector (bar/line/pie) | Done | Low | Dev11 | Test: DELTA-203 |
| DELTA-104 | Task | Update user documentation | Done | Low | Dev11 | — |

Test Execution Tickets:

| Ticket Key | Type | Summary | Status | Linked To |
|-----------|------|---------|--------|-----------|
| DELTA-201 | Test Execution | Test PDF export — formatting | Passed | DELTA-101 |
| DELTA-202 | Test Execution | Test date filter — edge cases | Passed | DELTA-102 |
| DELTA-203 | Test Execution | Test chart selector — rendering | Passed | DELTA-103 |

Why: Delta is a clean, simple project with everything done and tested. Dashboard should show all Green. This confirms the dashboard correctly represents a healthy project.

**Cross-Project Dependency Summary (for MVP testing):**

```
ATLAS-102 ──blocks──> BEACON-105
CIPHER-104 ──blocks──> ATLAS-103
```

This creates a dependency chain: CIPHER → ATLAS → BEACON.

---

### Confluence Data

**Confluence Space:** Create a space called "Release Management" (key: RM).

**Pages to Create:**

For each project, create the following pages under the RM space. Vary the completeness to test the Confluence MCP server's ability to detect missing/incomplete documentation.

**Project Atlas — Documentation Partially Complete**

| Page Title | Exists? | Content Quality | Last Modified |
|-----------|---------|----------------|--------------|
| ATLAS v3.2 — Release Plan | Yes | Complete — scope summary, key dates, team contacts, environment schedule | 3 days ago |
| ATLAS v3.2 — Deployment Runbook | Yes | Incomplete — has deployment steps but missing rollback steps and verification checks | 2 weeks ago (stale) |
| ATLAS v3.2 — Test Evidence | Yes | Complete — functional test results, integration test results, performance test summary | 1 day ago |
| ATLAS v3.2 — Rollback Procedure | No | Missing entirely | — |
| ATLAS v3.2 — Release Notes | Yes | Draft — incomplete, marked as work-in-progress | 5 days ago |

Sample Content for "ATLAS v3.2 — Release Plan":
```
## Scope Summary
Payment processing microservice upgrade to v3.2 including PCI compliance tokenization, 
schema migration, and gateway API integration update.

## Key Dates
- Code freeze: May 8, 2026
- QA sign-off deadline: May 13, 2026
- CAB submission: May 6, 2026
- Go/No-Go: May 14, 2026
- Deployment: May 16, 2026 (22:00–02:00 UTC)

## Team Contacts
- Engineering Lead: Alice Chen (alice.chen@company.com)
- QA Lead: Bob Martinez (bob.martinez@company.com)
- DevOps: Carol Singh (carol.singh@company.com)

## Artifacts
- atlas-payment-service:3.2.0 (Docker image)
- atlas-db-migration:3.2.0 (SQL scripts)

## Environment Schedule
- Pre-Prod deployment: May 10, 2026
- UAT window: May 11–13, 2026
```

Sample Content for "ATLAS v3.2 — Deployment Runbook" (intentionally incomplete):
```
## Deployment Steps

### Step 1: Database Migration
- Run atlas-db-migration:3.2.0 against payment_transactions database
- Estimated duration: 15 minutes
- Verify: Check migration_log table for successful completion

### Step 2: Deploy Application
- Deploy atlas-payment-service:3.2.0 to production K8s cluster
- Rolling deployment (zero downtime)
- Estimated duration: 10 minutes

### Step 3: Smoke Test
- Hit /health endpoint — expect 200 OK
- Process test transaction — expect success

## Rollback Steps
(TODO — to be completed)

## Verification Checks
(TODO — to be completed)
```

**Project Beacon — Documentation Complete**

| Page Title | Exists? | Content Quality | Last Modified |
|-----------|---------|----------------|--------------|
| BEACON v2.0 — Release Plan | Yes | Complete | 2 days ago |
| BEACON v2.0 — Deployment Runbook | Yes | Complete — all sections filled including rollback and verification | 1 day ago |
| BEACON v2.0 — Test Evidence | Yes | Complete — cross-browser test results, accessibility audit | 1 day ago |
| BEACON v2.0 — Rollback Procedure | Yes | Complete | 3 days ago |
| BEACON v2.0 — Release Notes | Yes | Complete | 2 days ago |

**Project Cipher — Documentation Mostly Missing**

| Page Title | Exists? | Content Quality | Last Modified |
|-----------|---------|----------------|--------------|
| CIPHER v1.5 — Release Plan | Yes | Incomplete — missing key dates and environment schedule | 3 weeks ago (very stale) |
| CIPHER v1.5 — Deployment Runbook | No | Missing entirely | — |
| CIPHER v1.5 — Test Evidence | No | Missing entirely | — |
| CIPHER v1.5 — Rollback Procedure | No | Missing entirely | — |
| CIPHER v1.5 — Release Notes | No | Missing entirely | — |

**Project Delta — Documentation Complete**

| Page Title | Exists? | Content Quality | Last Modified |
|-----------|---------|----------------|--------------|
| DELTA v4.1 — Release Plan | Yes | Complete | 4 days ago |
| DELTA v4.1 — Deployment Runbook | Yes | Complete | 2 days ago |
| DELTA v4.1 — Test Evidence | Yes | Complete | 1 day ago |
| DELTA v4.1 — Rollback Procedure | Yes | Complete | 3 days ago |
| DELTA v4.1 — Release Notes | Yes | Complete | 2 days ago |

**Runbook Template Page:**

Create a page "Release Runbook Template" that defines the expected structure:
```
Required Sections:
1. Deployment Steps (each with: action, owner, duration estimate, verification)
2. Rollback Steps (each with: trigger criteria, action, owner, duration estimate)
3. Verification Checks (post-deployment validation steps)
4. Contacts (deployment team, escalation path, on-call)
5. Prerequisites (infrastructure, certificates, secrets, approvals)
```

This template is what the `validate_page_structure` MCP tool validates against.

---

### ServiceNow Data

**Change Requests to Create:**

| CR Number | Short Description | Project | State | Risk | CAB Decision | Scheduled Start | Scheduled End |
|-----------|------------------|---------|-------|------|-------------|----------------|--------------|
| CHG0001001 | ATLAS v3.2 — Payment service upgrade | Atlas | Assess (New) | High | Pending | 2026-05-16 22:00 | 2026-05-17 02:00 |
| CHG0001002 | BEACON v2.0 — Customer portal redesign | Beacon | Assess (New) | Medium | Pending | 2026-05-16 22:00 | 2026-05-17 00:00 |
| CHG0001003 | CIPHER v1.5 — API gateway hardening | Cipher | Draft | High | Not Submitted | 2026-05-16 23:00 | 2026-05-17 03:00 |
| CHG0001004 | DELTA v4.1 — Reporting dashboard enhancements | Delta | Scheduled (Approved) | Low | Approved | 2026-05-16 22:00 | 2026-05-16 23:00 |

**Change Tasks (child tasks under each CR):**

For CHG0001001 (Atlas):

| Task Number | Short Description | State | Assigned To | Order |
|------------|------------------|-------|-------------|-------|
| CTASK0001001 | Run database migration script | Open | Carol Singh | 1 |
| CTASK0001002 | Deploy atlas-payment-service:3.2.0 | Open | Carol Singh | 2 |
| CTASK0001003 | Execute smoke tests | Open | Bob Martinez | 3 |
| CTASK0001004 | Validate monitoring dashboards | Open | Carol Singh | 4 |

For CHG0001004 (Delta):

| Task Number | Short Description | State | Assigned To | Order |
|------------|------------------|-------|-------------|-------|
| CTASK0001010 | Deploy delta-reporting:4.1.0 | Open | Dev11 | 1 |
| CTASK0001011 | Run regression tests | Open | Dev10 | 2 |

**CMDB Configuration Items:**

| CI Name | CI Class | Environment | Used By Projects |
|---------|---------|-------------|-----------------|
| payment-db-prod | Database | Production | Atlas, Beacon (via Atlas) |
| api-gateway-prod | Application | Production | Atlas, Cipher, Beacon |
| customer-portal-prod | Application | Production | Beacon |
| reporting-server-prod | Server | Production | Delta |
| k8s-cluster-prod | Compute | Production | All |

**Other Changes in Same Window (from other teams, for conflict testing):**

| CR Number | Short Description | State | Scheduled Start | Affected CI |
|-----------|------------------|-------|----------------|------------|
| CHG0001050 | Database platform patching | Scheduled | 2026-05-16 20:00 | payment-db-prod |
| CHG0001051 | Network firewall rule update | Scheduled | 2026-05-16 21:00 | api-gateway-prod |

Why: CHG0001050 patches the same database Atlas uses, and CHG0001051 touches the same API gateway Cipher modifies. These test conflict detection.

---

## Milestone 1 Additional Data — Intake & Eligibility

All MVP data remains. Add the following:

### Jira Additions

**Scope Change Simulation:**

After initial data setup, make the following changes to simulate scope instability (important for testing the `get_scope_change_log` MCP tool):

- Add 2 new stories to ATLAS Fix Version v3.2 after the scope lock date:
  - ATLAS-110: "Add fraud detection webhook" (added late — scope creep)
  - ATLAS-111: "Support multi-currency payments" (added late — scope creep)
- Remove 1 story from CIPHER Fix Version v1.5:
  - CIPHER-103: Moved to next release (descoped)

This creates scope instability data that the eligibility engine should flag.

**Reopened Ticket Simulation:**

- BEACON-101 (previously Done): Change status back to "In Progress" with comment "Reopened — design review feedback requires layout changes"

This tests the alert for reopened tickets.

### ServiceNow Additions

No new CRs needed. The existing CR states (Draft, Assess, Scheduled) already test the range of intake eligibility scenarios.

---

## Milestone 2 Additional Data — RAG Knowledge Base

### Historical Data for RAG Indexing

This is the most important data addition. You need historical records that the RAG system can index and retrieve to generate meaningful AI narratives.

### Confluence — Historical Release Pages (Past 2 Years)

Create pages under a "Release Archive" section in the RM space. You need at least 6–8 historical releases:

**Release Archive — March 2026:**

| Page Title | Key Content |
|-----------|-------------|
| March 2026 Release — Release Plan | 5 projects deployed. Scope: payment improvements, security patches, UI fixes. |
| March 2026 Release — Post-Release Report | Deployment duration: 3.5 hours (planned: 3 hours). 1 rollback (Project Phoenix — DB migration timeout). 0 incidents during hypercare. |
| March 2026 Release — Retrospective | Issues: Phoenix team's runbook was incomplete — missed pre-migration backup step. Action: Mandate runbook review 1 week before deployment. Communication: DevOps not included in Go/No-Go — add to required attendees. |

**Release Archive — February 2026:**

| Page Title | Key Content |
|-----------|-------------|
| February 2026 Release — Release Plan | 4 projects deployed. |
| February 2026 Release — Post-Release Report | Smooth deployment. Duration: 2.5 hours (planned: 3 hours). 0 rollbacks. 1 minor incident during hypercare (latency spike, self-resolved). |
| February 2026 Release — Retrospective | Positive: All runbooks reviewed 1 week prior. Improvement: Deployment communication channel should include business stakeholders. |

**Release Archive — January 2026:**

| Page Title | Key Content |
|-----------|-------------|
| January 2026 Release — Release Plan | 6 projects. Largest release of quarter. |
| January 2026 Release — Post-Release Report | Duration: 5 hours (planned: 4 hours). Delays: Team Alpha's (same team as Atlas) payment service deployment took 90 minutes instead of planned 30 — connection pool sizing issue. 1 incident: Customer-facing error page for 12 minutes during deployment. |
| January 2026 Release — Retrospective | Critical finding: Team Alpha's Pre-Prod did not match Production infrastructure sizing — connection pool set to 50 in Pre-Prod vs 200 in Production. Action: Mandate environment parity checks. Team Alpha has had deployment duration overruns in 3 of last 5 releases. |

**Release Archive — December 2025, November 2025, October 2025, September 2025, August 2025:**

Create similar pages for each month with varying outcomes. Key patterns to embed in the historical data:

- Team Alpha (Atlas's team): History of deployment overruns and environment parity issues. 2 rollbacks in past 12 months. Late documentation in 4 of 8 releases.
- Team Beta (Beacon's team): Clean track record. 0 rollbacks. On-time in 7 of 8 releases.
- Team Gamma (Cipher's team): First time deploying API gateway changes to production. No historical release data (new team). This tests how RAG handles absence of historical context.
- Common patterns: DB migrations take longer than estimated 60% of the time. Releases with >5 projects have 40% higher incident rate.

### ServiceNow — Historical Change Requests

Create closed CRs for past releases that the RAG can index:

| CR Number | Month | Project/Team | Outcome | Duration (Actual vs Planned) | Rollback? | Incidents |
|-----------|-------|-------------|---------|------------------------------|-----------|-----------|
| CHG0000901 | Mar 2026 | Team Alpha — Payment Service | Completed with issues | 90 min vs 45 min planned | No | 0 |
| CHG0000902 | Mar 2026 | Team Phoenix — User Service | Rolled Back | N/A | Yes — DB migration timeout | 1 |
| CHG0000903 | Mar 2026 | Team Beta — Portal Update | Completed successfully | 20 min vs 25 min planned | No | 0 |
| CHG0000801 | Feb 2026 | Team Alpha — Payment Patch | Completed successfully | 30 min vs 30 min planned | No | 0 |
| CHG0000802 | Feb 2026 | Team Beta — Portal Hotfix | Completed successfully | 15 min vs 20 min planned | No | 0 |
| CHG0000701 | Jan 2026 | Team Alpha — Payment Major | Completed with issues | 90 min vs 30 min planned | No | 1 (customer-facing) |
| CHG0000702 | Jan 2026 | Team Beta — Portal Redesign Phase 1 | Completed successfully | 25 min vs 30 min planned | No | 0 |
| CHG0000601 | Dec 2025 | Team Alpha — Payment Year-end | Rolled Back | N/A | Yes — config mismatch | 0 |
| CHG0000501 | Nov 2025 | Team Alpha — Payment Update | Completed with issues | 60 min vs 30 min planned | No | 0 |
| CHG0000401 | Oct 2025 | Team Beta — Portal Accessibility | Completed successfully | 22 min vs 25 min planned | No | 0 |

Why this matters for RAG: When the AI generates a risk narrative for Atlas (Team Alpha), it should retrieve this history and note patterns like "Team Alpha has experienced deployment duration overruns in 4 of last 6 releases" and "Team Alpha had a rollback in December 2025 due to configuration mismatch." This grounds the AI narrative in real evidence.

---

## Milestone 3 Additional Data — Dependencies & CAB

### Jira Additions

**More Cross-Project Links:**

Add richer dependency links to test the Dependency Analysis Agent:

| Source Ticket | Link Type | Target Ticket | Dependency Reason |
|--------------|-----------|--------------|-------------------|
| ATLAS-102 | blocks | BEACON-105 | Beacon's payment integration depends on Atlas's new schema |
| CIPHER-104 | blocks | ATLAS-103 | Atlas's gateway update depends on Cipher's hardening |
| CIPHER-101 | relates to | ATLAS-101 | Both modify API gateway configuration |
| BEACON-104 | depends on | DELTA-102 | Beacon's new component library uses Delta's date filter |

This creates a richer dependency graph: CIPHER → ATLAS → BEACON, plus DELTA → BEACON.

### ServiceNow Additions

**CMDB Shared CI Records:**

Ensure the following Configuration Items show multiple project references:

| CI Name | Modification Planned By |
|---------|------------------------|
| payment-db-prod | Atlas (schema migration), External team CHG0001050 (patching) |
| api-gateway-prod | Cipher (hardening), Atlas (API update), External team CHG0001051 (firewall) |

This tests infrastructure conflict detection — multiple projects and external changes targeting the same CI.

---

## Milestone 4 Additional Data — Deployment & Monitoring

### CI/CD Pipeline Data

If using Jenkins, create pipeline configurations (or mock data) for each project:

| Pipeline Name | Project | Stages | Expected Duration |
|-------------|---------|--------|-------------------|
| atlas-payment-deploy | Atlas | Build → Test → Deploy-PreProd → Approve → Deploy-Prod → Smoke-Test | 45 min total |
| beacon-portal-deploy | Beacon | Build → Test → Deploy-PreProd → Approve → Deploy-Prod → Verify | 25 min total |
| cipher-gateway-deploy | Cipher | Build → Security-Scan → Test → Deploy-PreProd → Approve → Deploy-Prod → Pen-Test | 60 min total |
| delta-reporting-deploy | Delta | Build → Test → Deploy-Prod → Verify | 15 min total |

**Pipeline Event Scenarios to Simulate:**

For testing the Deployment Monitoring Agent, prepare these scenarios:

| Scenario | Pipeline | What Happens | Expected Agent Behavior |
|----------|---------|-------------|------------------------|
| Normal deployment | Delta | All stages complete on time | Dashboard shows green progress |
| Slow stage | Atlas | Deploy-Prod stage takes 30 min instead of 10 min | Agent alerts: "Deployment step exceeding threshold." RAG retrieves: "Team Alpha has history of duration overruns" |
| Failed stage | Cipher | Security-Scan stage fails | Agent alerts: "Pipeline stage failed." Dashboard shows Red for step |
| Incident during deploy | Atlas | ServiceNow Incident INC0001001 raised and linked to CHG0001001 | Agent detects incident, surfaces on dashboard with impact assessment |

### ServiceNow — Incident for Testing

| Incident Number | Short Description | State | Linked CR | Severity |
|----------------|------------------|-------|-----------|----------|
| INC0001001 | Elevated error rate on payment API after deployment start | New | CHG0001001 | Sev-2 |

---

## Milestone 5 Additional Data — Full Platform

### Data for Reporting & Analytics

By M5, you should have accumulated data from running the platform through 2–3 real release cycles. For development purposes, create synthetic historical records covering 6–12 months:

**Release Outcome Summary Table (for metrics dashboard):**

| Month | Total Changes | Deployed Successfully | Rolled Back | Incidents During Deploy | Avg Duration Accuracy | On-Time % |
|-------|-------------|----------------------|------------|------------------------|----------------------|-----------|
| Aug 2025 | 5 | 5 | 0 | 0 | 95% | 100% |
| Sep 2025 | 4 | 4 | 0 | 1 | 88% | 75% |
| Oct 2025 | 6 | 5 | 1 | 0 | 82% | 83% |
| Nov 2025 | 5 | 4 | 1 | 2 | 78% | 80% |
| Dec 2025 | 3 | 2 | 1 | 1 | 70% | 67% |
| Jan 2026 | 6 | 5 | 1 | 1 | 75% | 83% |
| Feb 2026 | 4 | 4 | 0 | 0 | 92% | 100% |
| Mar 2026 | 5 | 4 | 1 | 1 | 85% | 80% |

**Team Performance Summary (for project-level analytics):**

| Team | Releases (12 months) | Rollbacks | Avg Blockers at Go/No-Go | Doc Completeness at Intake | First-Submission Pass Rate |
|------|---------------------|-----------|-------------------------|---------------------------|--------------------------|
| Team Alpha | 8 | 2 | 1.5 | 62% | 50% |
| Team Beta | 8 | 0 | 0.2 | 95% | 88% |
| Team Gamma | 0 | 0 | N/A | N/A | N/A |
| Team Delta | 6 | 0 | 0 | 100% | 100% |

### RBAC Test Users

Create test user accounts for each role:

| Username | Role | What They Should See |
|---------|------|---------------------|
| rm_alice | Release Manager | Full access to everything |
| pl_bob | Project Team Lead (Atlas) | Only Atlas project data, intake submission, Go/No-Go recommendation |
| pl_carol | Project Team Lead (Beacon) | Only Beacon project data |
| cab_dave | CAB Member | Read-only all data, can record CAB decisions |
| devops_eve | DevOps Engineer | Deployment status updates, rollback notifications |
| exec_frank | Executive Viewer | Dashboards and reports only, no operational actions |
| admin_grace | System Administrator | Configuration, integrations, role management |

---

## Data Setup Checklist by Milestone

### MVP Checklist

- [ ] 4 Jira projects created (ATLAS, BEACON, CIPHER, DELTA)
- [ ] Fix Versions created in each project
- [ ] 25+ tickets created across 4 projects with varying statuses
- [ ] Test execution tickets linked to stories (with gaps for testing)
- [ ] Cross-project links: ATLAS-102 blocks BEACON-105, CIPHER-104 blocks ATLAS-103
- [ ] Confluence space "Release Management" created
- [ ] 16 Confluence pages created (4 projects × 4 doc types, with intentional gaps)
- [ ] Runbook template page created
- [ ] 4 ServiceNow Change Requests in different states
- [ ] Change Tasks created for Atlas and Delta CRs
- [ ] 5 CMDB Configuration Items created
- [ ] 2 external Change Requests for conflict testing

### Milestone 1 Additions Checklist

- [ ] 2 late-added stories in Atlas (scope instability)
- [ ] 1 descoped story in Cipher
- [ ] 1 reopened ticket in Beacon

### Milestone 2 Additions Checklist

- [ ] 8 historical release plan pages in Confluence (Aug 2025 — Mar 2026)
- [ ] 8 historical post-release report pages
- [ ] 8 historical retrospective pages
- [ ] Pattern data embedded: Team Alpha overruns, Team Beta reliability, Team Gamma no history
- [ ] 10 historical closed Change Requests in ServiceNow with outcomes
- [ ] Incident history linked to past CRs

### Milestone 3 Additions Checklist

- [ ] Additional cross-project Jira links (4+ dependency relationships)
- [ ] CMDB CI shared references updated for conflict detection

### Milestone 4 Additions Checklist

- [ ] CI/CD pipeline configurations for 4 projects
- [ ] Pipeline event simulation scenarios prepared (normal, slow, failed, incident)
- [ ] ServiceNow Incident INC0001001 for deployment incident testing

### Milestone 5 Additions Checklist

- [ ] 12 months of synthetic release outcome data
- [ ] Team performance summary data
- [ ] 7 test user accounts for RBAC roles

---

*End of Sample Data & Test Environment Setup Guide*
