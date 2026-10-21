# SES phase 1: preparation only

**No live-send authorization. No real AWS credential installed. No running workflow or service changed.** The verified Mailpit setup remains the default.

## Prepared artifacts

- `C_ses_single_recipient.disabled.json`: separate inactive manual-only C draft. It is not installed in the running n8n database. The SES node remains disabled. There is no schedule, webhook or SMTP fallback.
- `plan.example.json`: no account, sender, recipient or job values; approval and identity-verification flags are false. It is an example, not evidence of an AWS account check.
- `compose.preparation.yml`: an unstarted, profile-scoped test API service without a host port. It clears AWS credential variables, keeps SES/LLM disabled and points SMTP to a closed loopback port to prevent accidental fallback. Existing API/workers/Mailpit are untouched.
- `iam-policy.template.json`: an unapplied single-recipient policy template derived by narrowing the generated [Autopilot baseline](../../reports/ses-iam-generated-baseline.json). Never apply the broad baseline itself. The template's ACCOUNT_ID, SENDER_EMAIL and CONTROLLED_RECIPIENT fields are unresolved.
- `native-node-offline.cjs`: exercises the actual installed SES node and local credential signing with invented values and blocked network functions. It never reads installed credential contents.
- [Offline validator](../../scripts/validate_ses_preparation.py): checks the draft, profile and policy restrictions without cloud calls, imports or activation.

Candidate region: **Asia Pacific (Mumbai), ap-south-1**, taken from the local configuration/default. The account, sender/recipient identities and regional sandbox status are **UNVERIFIED**. If your identities already exist in another region, stop and use that region consistently after revising and retesting the preparation; do not mix regions.

## AWS Console: steps for you

These are manual instructions, not actions performed by the agent. Creating an email identity causes AWS to send its own verification message; those administrative verification messages are separate from the one future application email. Do not use the SES console's Send test email button.

1. Sign in to your AWS account using your usual operator identity. Open **Amazon SES** and select **Asia Pacific (Mumbai), ap-south-1**. If your verified identities are elsewhere, record that region instead and stop before local configuration changes.
2. Open **Account dashboard**. Record whether the account is in the sandbox and whether sending is enabled. Do not request production access solely for this test: the sandbox permits sending to verified identities. Its regional limits are not a one-message safeguard.
3. Under **Configuration → Identities**, locate the intended sender. If absent, choose **Create identity → Email address**, enter one address you own and can receive mail at, leave the optional default configuration set unset, and create the identity. No purchased domain, dedicated IP or application infrastructure is needed for this email-identity route.
4. Open the AWS verification email in that mailbox and follow its link. Return to SES and confirm **Verified**. The verification link expires after 24 hours. Do not send me the link or your mailbox password.
5. Repeat for the exact controlled recipient in the same region. It can be the same mailbox/address as the sender for a minimal test. If you choose a plus alias, explicitly verify that exact recipient for clarity. No supplied CSV address or example .test/.invalid address may be used as the real recipient.
6. Open the sender identity details and record the identity ARN and region. The planned policy uses the explicit email identity ARN, not a wildcard or a different domain identity. Confirm that the dedicated sender has no default configuration set; if an existing identity has one, stop for review rather than changing its shared settings or broadening permissions. Retain your account ID, sender and recipient privately; they are not credentials and need not be committed to the repo.
7. Stop here and report only the region, sandbox/sending status and whether both identities show Verified. No real access keys, session tokens, passwords or verification URLs should be pasted into chat or committed. Credential installation and the application send still need separate approval.

Official references: [creating and verifying identities](https://docs.aws.amazon.com/ses/latest/dg/creating-identities.html), [regional sandbox requirements](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html).

## IAM review before credential installation

The installed native node uses the SES Query API **SendEmail**, not SMTP, raw email or templated email. Runtime sending needs `ses:SendEmail`. The separate administrator/operator may need additional console permissions to manage identities/IAM; do not attach those administrator permissions to the sending principal.

The IAM template restricts:

- Resource to `arn:aws:ses:ap-south-1:ACCOUNT_ID:identity/SENDER_EMAIL`.
- `ses:FromAddress` to SENDER_EMAIL and `aws:RequestedRegion` to ap-south-1.
- Every `ses:Recipients` value to CONTROLLED_RECIPIENT, with a Null check requiring that recipient context to be present. To/Cc/Bcc are all covered by the recipient condition; the workflow additionally supplies exactly one To and no Cc/Bcc.
- Action to `ses:SendEmail`. It grants no identity creation, IAM administration, template, raw-send, configuration-set or infrastructure permissions.

Use a dedicated restricted principal/session without broader attached policies; another Allow could bypass an allow-only restriction. IAM does not count messages or enforce a one-send quota. The single immutable user/job, unique event, durable state machine, disabled retries and operator approval provide the one-attempt boundary. Manually executing the send node outside the full workflow is forbidden and can bypass application controls.

The action baseline was generated with IAM Policy Autopilot 0.3.0, installed in a temporary environment outside the project's dependencies. The equivalent tool command is:

```powershell
$env:DISABLE_IAM_POLICY_AUTOPILOT_TELEMETRY = 'true'
uvx iam-policy-autopilot@0.3.0 generate-policies "C:\Users\DELL\Desktop\loan-eligibility-engine\backend\app\notifications.py" --region ap-south-1 --service-hints ses --pretty
```

No `--upload-policies` flag was used. The baseline has generic resource ARNs because no account or identity was provided; the deterministic narrowing function in the validator reproduces the restricted template. Offline tests are not an AWS IAM Policy Simulator result. Account SCPs, permission boundaries, actual policies and SES identity status remain unchecked.

[AWS SES permissions and recipient restrictions](https://docs.aws.amazon.com/ses/latest/dg/control-user-access.html).

## Installed n8n credential compatibility

Installed n8n is **2.43.6**, native `awsSes` node version **1**. The selected credential type is `aws` / **AWS (IAM)**. Supported fields inspected from the installed module are region, accessKeyId, secretAccessKey, temporaryCredentials and sessionToken. Prefer short-lived access credentials with the temporary-credentials option and session token where your account supports them. Do not use root keys, SES SMTP passwords, or the application's MinIO keys.

The draft references a separate not-yet-installed credential, `loan-ses-single-test`. A future editor-created credential may receive a different ID; select that dedicated credential in the test draft after approval. Do not replace existing PostgreSQL/header credentials or the production C credential reference.

The credential's built-in connection test calls regional STS GetCallerIdentity. Consequently, even saving/testing real credentials can contact AWS: that is outside phase 1 and needs the credential-installation approval. Local signing tests used only invented keys and made no request.

Native-node parameters were verified: email/send, fromEmail, a one-element toAddresses array, subject, HTML body and empty additionalFields. The acknowledgement shape is SendEmailResponse.SendEmailResult.MessageId. A provider MessageId proves acknowledgement, not inbox receipt.

## Offline checks

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = 'backend;.'
.\.venv\Scripts\python.exe scripts/validate_ses_preparation.py
.\.venv\Scripts\python.exe -m pytest -q backend/tests/test_ses_preparation.py
docker compose exec -T n8n node /workflows/ses-test/native-node-offline.cjs
docker compose -f docker-compose.yml -f n8n/ses-test/compose.preparation.yml --profile ses-preparation config --quiet
```

The final command validates only; do not replace it with up/run in phase 1. The draft import check uses a disposable network-disabled SQLite container, not the running database, credentials or workflow publication.

## Final pre-send checklist: future approval checkpoint

Before requesting installation/send approval, verify all of the following:

1. Backups/checksums and historical fingerprints match. Both existing Mailpit inboxes and all original services remain healthy. Record existing notification IDs/states; never reset SENT, UNKNOWN or SENDING.
2. Region, exact email identity ARN, sender, recipient, regional verification and account sending/sandbox status are confirmed. The restricted policy is instantiated privately and reviewed against the actual principal's effective permissions.
3. A separate installation approval authorizes the dedicated credential, isolated test API and draft workflow. Preserve the existing production C and private Mailpit override. Use no real SES credentials in the backend or .env; only the dedicated n8n credential needs sending access.
4. A separately approved fresh synthetic job contains exactly one fictional user and one eligible user. No historical job or earlier SENT event is reused. Confirm job provenance, accepted=1/rejected=0, B COMPLETED, and at most one event. The draft's API check enforces one completed user; the operator must verify that it is the newly authorized synthetic job.
5. Pause the dispatcher before creating this job; otherwise production C could capture it in Mailpit first. Invoke B explicitly, then use only the manual test C. The test API must use the exact approved sender/recipient and explicit test-mode flags. The verified main API remains in preview mode.
6. Pin that job/sender/recipient/account and confirmed region/sandbox status in the private test plan and embedded draft guard, keeping repo examples disabled. Review the complete message and fictional-data disclaimer before any claim/send.
7. Native SES Retry On Fail=false; reservation Retry On Fail=false. Receipt retries are idempotent. No Cc/Bcc, no attachments, no custom endpoints or automatic workflow retry. The pinned gate, one-user check, SES-transport check and reserved-payload recipient check must all pass.
8. Obtain explicit **one-message send approval** before enabling the test-only SES node and running the whole manual workflow once. No production C activation. Do not run selected sending nodes or rerun a failed/uncertain attempt.
9. Capture execution ID, event ID, attempt count, provider acknowledgement and actual received message/headers. SENT with a MessageId alone does not satisfy received-email evidence. An error or missing acknowledgement is UNKNOWN or stranded SENDING; stop for reconciliation. Do not automatically retry, reset, or create a replacement job to obtain a successful screenshot.

The draft's disabled SES node is a gate, not a dry-run sender: deliberately running past the other guards while leaving it disabled can still reserve an event and yield UNKNOWN. Do not execute this draft in the live environment during phase 1.

## Rollback and preservation

Phase 1 requires no runtime rollback: nothing is installed or started. In a future approved send phase, stop the manual test and isolated test API, disable/unpublish the test copy, and restore normal dispatcher operation only when the test job's audit/outbox state has been reviewed. Retain the test job, events, provider IDs, received-message evidence and isolated Mailpit captures. Do not overwrite original workflow definitions, .env, credentials or database records. Leave the existing Mailpit configuration unchanged.

A successful external send cannot be undone. Uncertain sends must remain available for reconciliation. Deactivating/removing only the newly created test credential or principal is a separate reviewed action; do not rotate or delete existing credentials. Any action requiring historical database restoration or event resets must stop for a new explicit decision.
