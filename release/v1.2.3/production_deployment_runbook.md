# Production Deployment Runbook — Medburg CRM

## 1. Purpose
This document provides a step-by-step operational checklist for deploying Medburg CRM to production. It is designed for System Administrators to execute a safe deployment, ensuring data integrity is protected and providing clear instructions for rollback at any stage.

---

## 2. Release Information

* **Release Version:** `v1.2.3-rc1`
* **Target Environment:** Production VPS
* **Deployment Type:** In-place Upgrade
* **Risk Level:** Low
* **Reason:** No database migrations. No dependency changes. UI enhancements. Reporting additions. Investment lifecycle redesign already tested.

---

## 3. Pre-Deployment Checklist

- [ ] Notify users of deployment window
- [ ] Confirm production access (VPN/IP Whitelist)
- [ ] Confirm SSH access to the VPS
- [ ] Confirm GitHub repository access from the VPS
- [ ] Verify current Git branch is correct
- [ ] Record current deployed Git commit hash (SHA)
- [ ] Record current deployed tag
- [ ] Verify VPS disk space (`df -h`)
- [ ] Verify PostgreSQL service is running (`systemctl status postgresql`)
- [ ] Verify medburg service is running (`systemctl status medburg`)
- [ ] Verify nginx service is running (`systemctl status nginx`)
- [ ] Verify current application is healthy (load login page successfully)

---

## 4. Backup Checklist

- [ ] Execute PostgreSQL full database backup: 
      `pg_dump medburg_crm > /backup/path/medburg_crm_pre_v1.2.3.sql`
- [ ] Verify backup completed without errors
- [ ] Record backup filename and path
- [ ] Backup `.env.prod` configuration file
- [ ] Record deployment start timestamp
- [ ] Record current Git SHA (pre-deployment)
- [ ] Verify PostgreSQL restore procedure is available and understood

---

## 5. Deployment Steps

Execute the following commands from the project root directory. Pause and evaluate the expected result after each step.

**Step 5.1: Fetch Latest Tags**
```bash
git fetch --tags
```
* **Expected Result:** Tags are successfully fetched from origin.
* **Stop if Failed?** Yes.

**Step 5.2: Checkout Release Candidate**
```bash
git checkout v1.2.3-rc1
```
* **Expected Result:** "HEAD is now at [commit-hash]".
* **Stop if Failed?** Yes.

**Step 5.3: Verify Git Status**
```bash
git status
```
* **Expected Result:** "HEAD detached at v1.2.3-rc1. working tree clean."
* **Stop if Failed?** Yes. (Do not proceed if uncommitted changes exist).

**Step 5.4: Activate Virtual Environment**
```bash
source venv/bin/activate
```
* **Expected Result:** `(venv)` appears in terminal prompt.
* **Stop if Failed?** Yes.

**Step 5.5: Verify Migrations (Dry Run)**
```bash
python manage.py showmigrations --plan
```
* **Expected Result:** Output should display current migration plan. For v1.2.3-rc1, NO NEW migrations should be pending.
* **Stop if Failed?** Yes.

**Step 5.6: Apply Migrations**
```bash
python manage.py migrate
```
* **Expected Result:** "No migrations to apply." (Expected for v1.2.3-rc1).
* **Stop if Failed?** Yes.

**Step 5.7: Collect Static Files**
```bash
python manage.py collectstatic --no-input
```
* **Expected Result:** Files copied to static root.
* **Stop if Failed?** Yes.

**Step 5.8: Restart Application Service**
```bash
sudo systemctl restart medburg
```
* **Expected Result:** Service restarts cleanly with no terminal output.
* **Stop if Failed?** Yes.

**Step 5.9: Reload Nginx**
```bash
sudo systemctl reload nginx
```
* **Expected Result:** Web server reloads configuration smoothly.
* **Stop if Failed?** Yes.

---

## 6. Immediate Verification

Perform these checks immediately after the services restart.

- [ ] Login page loads successfully
- [ ] Login authentication works
- [ ] Admin Dashboard loads
- [ ] Dashboard KPI cards are visible and populated
- [ ] Dashboard charts render without JavaScript errors
- [ ] Sidebar navigation displays correct highlighted states
- [ ] "Prepaid Doctors Report" loads successfully
- [ ] "Postpaid Doctors Report" loads successfully
- [ ] Excel export downloads and opens correctly
- [ ] Investment workflow accessible (verify manual completion state)
- [ ] Campaign workflow accessible
- [ ] Settlement Ledger loads accurately
- [ ] Dashboard tabs (Home, Prepaid, Postpaid) persist when filters are applied

---

## 7. Data Integrity Verification

Run comparison with pre-deployment baseline.

| Metric | Pre-Deployment Count | Post-Deployment Count | Match? (Y/N) |
|---|---|---|---|
| Doctor count | | | |
| Investment count | | | |
| Campaign count | | | |
| Sales count | | | |
| Settlement count | | | |

---

## 8. Smoke Test

Perform the following critical user journeys:

- [ ] Admin Login
- [ ] Representative Login
- [ ] Create Prepaid Sale
- [ ] Create Postpaid Sale
- [ ] Open Reports (Prepaid, Postpaid, Settlement)
- [ ] View Dashboard Home
- [ ] Export Excel from Reports
- [ ] Logout

---

## 9. Log Monitoring

Monitor logs for 15–30 minutes immediately post-deployment.

**Application Logs:**
```bash
sudo journalctl -u medburg -f
```

**Web Server Logs:**
```bash
sudo journalctl -u nginx -f
```

**Monitor for the following anomalies:**
- `500 Internal Server Error`
- Python Tracebacks
- Permission errors (403s on static files)
- Static file routing failures (404s)
- Database connection errors

---

## 10. Rollback Procedure

Execute this procedure immediately if critical failures or data corruption are detected during post-deployment verification.

**When rollback is required:**
- 500 errors preventing core application usage.
- Data integrity anomalies detected during verification.
- JavaScript or CSS failures rendering the UI unusable.
- Immediate client/user complaint of critical workflow breakage.

**Step 1: Stop Application Service**
```bash
sudo systemctl stop medburg
```

**Step 2: Revert to Previous Stable Tag**
```bash
git checkout v1.2.0-stable
```
*(Replace `v1.2.0-stable` with the tag recorded in Section 3).*

**Step 3: Re-collect Static Files (Restore old CSS/JS)**
```bash
python manage.py collectstatic --no-input
```

**Step 4: Restart Application Service**
```bash
sudo systemctl start medburg
```

**Step 5: Reload Web Server**
```bash
sudo systemctl reload nginx
```

**Verification:**
- Log in and verify the old dashboard layout is restored.
- Verify `error.log` is clean.
- Ensure critical workflows function.

---

## 11. Deployment Completion

- [ ] All smoke tests passed
- [ ] Logs are clean (no critical errors)
- [ ] No immediate customer complaints
- [ ] Deployment timestamp recorded
- [ ] Release formally marked as successful

---

## 12. Deployment Record

| Field | Details |
|---|---|
| Date | |
| Version | `v1.2.3-rc1` |
| Git SHA | |
| Operator | |
| Backup File | |
| Deployment Duration | |
| Issues Encountered | |
| Rollback Required | [ ] Yes / [ ] No |
| Notes | |
