# Eight-minute demonstration script

Target length: 8:00, including the on-screen actions and pauses. Rehearse at a calm speaking pace; end each segment at its time marker. Bracketed directions are not spoken. Keep a completed, explicitly labeled rehearsal job available if the fresh pipeline takes longer. The run is local, fixture based, and uses Mailpit. Do not say the assignment is fully complete.

## 0:00-0:50 | What the system proves

[Show the dashboard DEMO badge and architecture.]

This is a Loan Eligibility Engine for a supplied file of ten thousand users. It validates the upload, preserves a job-specific user snapshot, and uses n8n to orchestrate discovery, matching and notification.

The dashboard uploads CSV bytes directly to S3-compatible storage through a short-lived signed URL. A worker validates and ingests them into PostgreSQL. An outbox then calls n8n B. B runs the candidate query and advanced rules, persists the results, and acknowledges completion before C can begin.

This demonstration uses MinIO, fictional lender fixtures and a controlled Mailpit inbox. It proves the local path. AWS deployment, live lender discovery and actual SES inbox delivery remain separate, unverified steps.

## 0:50-1:40 | Upload the actual CSV

[Connect before exposing any token. Drop users.csv, show preview, click upload, point to progress and job ID.]

I am uploading the supplied users.csv. The browser checks the extension, size and header before requesting a generated object key. The worker independently verifies those values before accepting its contents.

The file goes directly to MinIO. The local completion endpoint marks the job ready for the durable polling adapter. That adapter represents the local queue; I am not claiming this is an actual AWS S3 event.


## 1:40-2:30 | Validate the database evidence

[Show completed ingestion or clearly identify the completed rehearsal job. Show aggregate SQL and independent verification report.]

The completed evidence shows ten thousand accepted rows and zero rejected rows. There are ten thousand distinct external IDs within this job.

The source file has repeated email values. Email is therefore not used as a unique person identifier, and none of those addresses is a delivery destination.

Validation handles invalid encoding, malformed headers and emails, invalid ages and scores, negative income and duplicate IDs. Inserts are batched, and the whole file commits atomically.

## 2:30-3:30 | Workflow A and source honesty

[Click fictional discovery if not already running; open its successful A execution and three fresh crawl records.]

This is Workflow A executing inside n8n. Its authenticated demonstration trigger produces three fixture source items. The HTTP nodes fetch bundled HTML, and the extraction service validates the schema, evidence and bounds before deduplicating and upserting products in PostgreSQL.

These are fictional products, visibly labeled DEMO_FIXTURE.

The daily schedule has a different path: source configuration, permission gate, HTTP fetch, extraction and crawl audit. The three proposed official lender sources remain disabled because the accessibility and usage review is incomplete.

Starting-from rates remain starting-from rates. Missing credit, age or employment criteria remain unknown.

## 3:30-5:00 | Workflow B and the optimization

[Open B execution, SQL node, Code node and final acknowledgement; show matching audit.]

B validates the job and requires completed ingestion. Its Postgres node selects this job's users and active permitted products, then filters known income, score, age and employment constraints in parameterized SQL.

The naive baseline is ten thousand users times three products: thirty thousand pairs. SQL leaves thirteen thousand three hundred and two candidates for advanced evaluation, a fifty-five point six six percent reduction.

The Code node evaluates uncertainty and explicit qualitative requirements. The backend rechecks proposed decisions before bulk persistence, so production makes two SQL passes. The benchmark measures one pass.

The final counts require interpretation. Ten thousand outcomes belong to the incomplete fictional product and are REVIEW_REQUIRED. The complete self-employed fixture yields one thousand one hundred and sixteen possibly eligible outcomes. The complete salaried fixture yields two thousand one hundred and eighty-six. Those employment groups do not overlap here, giving three thousand three hundred and two distinct notification candidates.

Persistence records PERSISTED first. Only B's final acknowledgement marks it complete and creates C's outbox event.

## 5:00-6:10 | Workflow C and the received message

[Show C batches, SENT rows and exact Mailpit message from this job. If still running, state that and switch visibly to rehearsal evidence.]

C checks B's completion and groups newly eligible products by user. It sends at most one notification per user and matching version for this job, in batches of one hundred. Review outcomes do not trigger emails.

All destinations come from the explicitly configured controlled inbox. The notification service cannot select a recipient from a CSV user.

Here is a captured message linked to this job by Message-ID, with a greeting, fictional products, source links and disclaimer in both text and HTML.

This is Mailpit SMTP capture. It is not AWS SES delivery or proof of a real external inbox receipt. The verifier correlates all three thousand three hundred and two SENT events with job-specific Mailpit messages.


## 6:10-7:05 | Measured performance and regression evidence

[Show benchmark samples and medians, then checks.json and JUnit.]

The benchmark uses this data and these products, with one warmup, five measured repetitions, retained samples and pair/status equality checks. Two local measurement batches showed variable timing, including one with a slower optimized median. These are the actual results on this machine; they exclude n8n, persistence and email delivery.

The independent verifier is separate from the shared production matching function.

The latest check report gives the exact test count and confirms linting, types, workflow structure, frontend syntax/build, Compose configuration and migrations. Dependency scanning found seven advisories in the earlier Starlette version. The upgraded runtime requirements now have no known findings in that scan. This is not a container vulnerability audit.

## 7:05-8:00 | AWS readiness and candid limitations

[Show serverless.yml, deployment documentation and final recruiter audit.]

The AWS template defines direct S3 upload, S3-to-SQS ingestion, a DLQ, partial batch failures, bounded Lambda concurrency, private subnet parameters and an outbox dispatcher. RDS, private n8n and the internal application service must be provisioned separately.

Static configuration checks are useful, but they do not establish a successful deployment. The Linux zip passed a local AWS base-container smoke. Serverless resolution, private connectivity, IAM behavior and SES receipt still need an authorized cloud test.

Local limits include fifty thousand candidates per n8n run, basic worker health checks, and a PostgreSQL compatibility warning. The audit prioritizes operational improvements.

The reproducible local pipeline, independent decision checks and controlled email capture are demonstrated. Live sources, cloud integration and submission recording remain explicit next steps.

[Stop at 8:00. Do not append an unsupported completion claim.]
