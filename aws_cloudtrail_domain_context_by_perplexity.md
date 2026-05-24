# AWS CloudTrail Domain Context for AI Strike

---

## 1. Source List

- **CloudTrail Record Contents** — Field definitions for all CloudTrail log record elements.
  https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html

- **CloudTrail userIdentity Element** — Identity type values and fields in the userIdentity block.
  https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-user-identity.html

- **Logging IAM and AWS STS API Calls with CloudTrail** — STS API event shapes.
  https://docs.aws.amazon.com/IAM/latest/UserGuide/cloudtrail-integration.html

- **CloudTrail Supported Event Sources** — Maps service operations to eventSource values.
  https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-aws-service-specific-topics.html

- **AWS CloudTrail Concepts** — What CloudTrail logs and management events vs. data events.
  https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-concepts.html

- **AWS STS GetCallerIdentity** — API reference.
  https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html

- **AWS Secrets Manager CloudTrail Logging** — Secrets Manager event shapes.
  https://docs.aws.amazon.com/secretsmanager/latest/userguide/monitoring_cloudtrail.html

- **Amazon EC2 RunInstances API Reference** — RunInstances parameters including instanceType.
  https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_RunInstances.html

- **Amazon S3 CloudTrail Logging** — S3 data event shapes including GetBucketAcl.
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/logging-with-cloudtrail.html

- **IAM CreateAccessKey API Reference** — IAM key creation event parameters.
  https://docs.aws.amazon.com/IAM/latest/APIReference/API_CreateAccessKey.html

- **AWS CloudTrail Stopping/Deleting Trails** — StopLogging, DeleteTrail, UpdateTrail events.
  https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-delete-trails-console.html

- **AWS Console Sign-In Events** — ConsoleLogin event shape and additionalEventData.MFAUsed field.
  https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-aws-console-sign-in-events.html

---

## 2. CloudTrail Record Fields

| CloudTrail Field | Meaning (paraphrased from AWS docs) | Why it matters for threat hunting | Dataset Column | Source URL |
|---|---|---|---|---|
| `eventName` | The API action requested, matching the service's API names. | Identifies exactly what operation was attempted — the primary filter for every detection rule. | `eventName` | https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html |
| `eventSource` | The service endpoint the request was sent to, in the form `service.amazonaws.com`. | Namespaces events by AWS service; used with eventName to avoid false matching (e.g., two services with the same action name). | `eventSource` | https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html |
| `eventTime` | UTC timestamp when the request completed, sourced from the NTP-synced host serving the API endpoint. | Enables time-window analysis, spike detection, and off-hours access detection. | `eventTime` | https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html |
| `sourceIPAddress` | IP from which the request originated. For console actions this reflects the end-user IP; for AWS-internal service calls it shows a DNS name or "AWS Internal". | Pivot point for geolocation, known-bad IP, and internal-vs-external origin checks. | `sourceIPAddress` | https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html |
| `userAgent` | The client or SDK that made the request (max 1 KB, truncated if exceeded). Examples include `aws-cli`, `aws-sdk-java`, or console browser strings. | Non-standard or custom agent strings may indicate attacker tooling or automation not typical of normal operations. | `userAgent` | https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html |
| `userIdentity.type` | The class of identity making the request: `Root`, `IAMUser`, `AssumedRole`, `AWSService`, etc. | Determines the privilege tier and expected behavior pattern of the actor. Root and unexpected AssumedRole activity are high-signal. | `userIdentitytype` | https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-user-identity.html |
| `userIdentity.arn` | The ARN of the principal. For AssumedRole, the ARN includes the session name. | Identifies the exact entity; allows filtering by role, user path, or account ID embedded in the ARN. | `userIdentityarn` | https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-user-identity.html |
| `errorCode` | The AWS service error code if the request failed, e.g. `AccessDenied`, `UnauthorizedOperation`. Present only on failed requests. | A burst of errorCode values from one principal or IP is a primary indicator of probing, misconfigured automation, or brute force. | `errorCode` | https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html |
| `errorMessage` | Human-readable description of the error. Some services place error detail here; others place it in `responseElements`. | Provides context to distinguish permission errors from quota errors; may include the resource ARN that was denied. | `errorMessage` | https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html |
| `requestParameters` | The parameters sent with the request, documented per-service in each API reference. Max 100 KB; omitted if exceeded. | Contains service-specific attack indicators, e.g. `instanceType` in RunInstances, `secretId` in GetSecretValue, target resource names. | `requestParametersinstanceType` (partial) | https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html |

---

## 3. Identity Types

### Root

- **What it means:** The `type` value `Root` indicates the request was made using the AWS account's root credentials — the all-powerful email/password or root access key. AWS docs describe this as "your AWS account credentials." If an account alias is set, the `userName` field shows the alias; otherwise userName is absent.
- **Why it matters for detection:** Root usage for routine operations is a security anti-pattern per AWS best practices. Any `Root` login or API call — especially outside of the rare legitimate use cases (billing, support, initial setup) — is a high-severity signal. Console sign-in by root is captured as `ConsoleLogin` with `userIdentitytype = Root`.
- **Source:** https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-user-identity.html

### IAMUser

- **What it means:** The `type` value `IAMUser` indicates the request was made using long-lived IAM user credentials (password or static access key). The `userName` field contains the IAM username.
- **Why it matters for detection:** IAM users with static access keys are a common lateral movement target. `CreateAccessKey` events where the actor is an IAMUser (not a role) indicate a user expanding their own access or creating credentials for exfiltration. Failed console logins by IAM users map to `ConsoleLogin` with `errorCode = Failed authentication`.
- **Source:** https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-user-identity.html

### AssumedRole

- **What it means:** The `type` value `AssumedRole` indicates temporary credentials obtained via `AssumeRole` (STS). The ARN includes the role name and session name, e.g. `arn:aws:sts::123456789012:assumed-role/RoleName/SessionName`. The `sessionContext.sessionIssuer` block identifies the source role.
- **Why it matters for detection:** Roles are the expected pattern for workloads, but unusual session names, cross-account assumptions, or an AssumedRole identity calling sensitive APIs (CreateAccessKey, StopLogging) may indicate credential abuse. Role ARN parsing distinguishes roles from users in queries.
- **Source:** https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-user-identity.html

---

## 4. Hypothesis-to-AWS Mapping

### H1 — Failed Console Login / Brute Force

- **Detection intent:** Find repeated authentication failures to the AWS console from the same IP or for the same user.
- **Relevant AWS service:** AWS Sign-In (IAM / Console authentication)
- **Expected eventSource:** `signin.amazonaws.com`
- **Expected eventName:** `ConsoleLogin`
- **Relevant dataset columns:** `eventName`, `eventSource`, `errorCode`, `sourceIPAddress`, `userIdentityuserName`, `eventTime`
- **SQL filter logic:** Filter where eventSource = 'signin.amazonaws.com' AND eventName = 'ConsoleLogin' AND errorCode = 'Failed authentication'; group by sourceIPAddress or userIdentityuserName; flag if count exceeds threshold within a time window.
- **Security rationale:** AWS logs every console login attempt, success or failure, as a `ConsoleLogin` event. Failed authentication is surfaced in `errorCode`. High-frequency failures from one IP or against one account indicate a brute-force or credential-stuffing attempt.
- **Caveats / false positives:** Legitimate users who forget passwords, corporate SSO misconfigurations, or automated health-check scripts can produce bursts of failures.
- **Sources:**
  - https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-aws-console-sign-in-events.html
  - https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html

---

### H2 — Root User Console Login

- **Detection intent:** Detect any console sign-in by the root account identity.
- **Relevant AWS service:** AWS Sign-In
- **Expected eventSource:** `signin.amazonaws.com`
- **Expected eventName:** `ConsoleLogin`
- **Relevant dataset columns:** `eventName`, `eventSource`, `userIdentitytype`, `sourceIPAddress`, `eventTime`
- **SQL filter logic:** Filter where eventSource = 'signin.amazonaws.com' AND eventName = 'ConsoleLogin' AND userIdentitytype = 'Root'. Any result is an alert-worthy finding.
- **Security rationale:** AWS Identity best practices recommend not using the root account for day-to-day operations. Root sign-in events are rare and high-risk regardless of success or failure.
- **Caveats / false positives:** Legitimate root logins do occur for very specific account management tasks (e.g., changing account email, activating certain services). Low false positive rate but near-zero expected baseline.
- **Sources:**
  - https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-aws-console-sign-in-events.html
  - https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-user-identity.html

---

### H3 — CloudTrail Logging Disruption

- **Detection intent:** Identify attempts to disable, delete, or weaken CloudTrail logging to evade detection.
- **Relevant AWS service:** AWS CloudTrail
- **Expected eventSource:** `cloudtrail.amazonaws.com`
- **Expected eventNames:** `StopLogging`, `DeleteTrail`, `UpdateTrail`
- **Relevant dataset columns:** `eventName`, `eventSource`, `userIdentitytype`, `userIdentityarn`, `sourceIPAddress`, `errorCode`
- **SQL filter logic:** Filter where eventSource = 'cloudtrail.amazonaws.com' AND eventName IN ('StopLogging', 'DeleteTrail', 'UpdateTrail'). Surface both successful calls and AccessDenied attempts.
- **Security rationale:** Disabling CloudTrail is a well-known attacker technique to prevent audit trail generation before carrying out further compromise. These are low-volume management events that should be extremely rare in normal operations.
- **Caveats / false positives:** Legitimate infrastructure-as-code deployments (Terraform, CloudFormation) may call `UpdateTrail` during configuration changes. Check for infrastructure automation userAgents or known deployment roles before escalating.
- **Sources:**
  - https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-delete-trails-console.html
  - https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html

---

### H4 — Unauthorized API Calls (AccessDenied / UnauthorizedOperation)

- **Detection intent:** Surface principals repeatedly hitting permission walls, suggesting probing or misconfigured stolen credentials.
- **Relevant AWS service:** All AWS services (cross-service pattern)
- **Expected eventSource:** Any `*.amazonaws.com`
- **Expected eventNames:** Any API call (errorCode is the signal, not eventName)
- **Relevant dataset columns:** `errorCode`, `userIdentityarn`, `userIdentityprincipalId`, `sourceIPAddress`, `eventName`, `eventSource`, `eventTime`
- **SQL filter logic:** Filter where errorCode IN ('AccessDenied', 'UnauthorizedOperation'); group by userIdentityarn or sourceIPAddress; flag high-count clusters, especially across multiple eventSource values (breadth scanning).
- **Security rationale:** AWS returns `AccessDenied` or `UnauthorizedOperation` when an identity lacks permission for an action. A single actor hitting many different services with denials suggests enumeration using stolen credentials without knowledge of the exact permissions granted.
- **Caveats / false positives:** Misconfigured IAM policies in CI/CD pipelines or applications can produce sustained AccessDenied noise. Compare actor against known service accounts before escalating.
- **Sources:**
  - https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html

---

### H5 — STS GetCallerIdentity Reconnaissance

- **Detection intent:** Detect use of GetCallerIdentity as a "whoami" call to enumerate the current identity without triggering resource-specific permissions.
- **Relevant AWS service:** AWS Security Token Service (STS)
- **Expected eventSource:** `sts.amazonaws.com`
- **Expected eventName:** `GetCallerIdentity`
- **Relevant dataset columns:** `eventName`, `eventSource`, `userIdentityarn`, `userIdentityaccountId`, `sourceIPAddress`, `userAgent`
- **SQL filter logic:** Filter where eventSource = 'sts.amazonaws.com' AND eventName = 'GetCallerIdentity'. Cross-correlate with sourceIPAddress and userAgent to identify anomalous callers, especially immediately preceding other sensitive API calls.
- **Security rationale:** `GetCallerIdentity` succeeds regardless of IAM policy — it cannot be denied. AWS docs confirm this API returns the account, user ID, and ARN of the calling entity. It is a no-side-effect reconnaissance call that attackers use to validate credentials and orient themselves.
- **Caveats / false positives:** Many legitimate SDKs, CI/CD pipelines, and AWS-integrated tools call GetCallerIdentity at startup to validate configuration. High baseline volume is normal; focus on novel sourceIPAddress or userAgent values.
- **Sources:**
  - https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html
  - https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html

---

### H6 — Secrets Manager GetSecretValue Access

- **Detection intent:** Detect access to secrets, which may indicate credential harvesting after initial compromise.
- **Relevant AWS service:** AWS Secrets Manager
- **Expected eventSource:** `secretsmanager.amazonaws.com`
- **Expected eventName:** `GetSecretValue`
- **Relevant dataset columns:** `eventName`, `eventSource`, `userIdentityarn`, `userIdentitytype`, `sourceIPAddress`, `errorCode`
- **SQL filter logic:** Filter where eventSource = 'secretsmanager.amazonaws.com' AND eventName = 'GetSecretValue'. Triage by userIdentityarn — flag callers outside known application roles, especially IAMUsers or Root. Also surface AccessDenied attempts as probing.
- **Security rationale:** AWS Secrets Manager logs all GetSecretValue API calls via CloudTrail. Legitimate secret access is typically limited to specific application roles. Access by interactive users, unknown roles, or from unexpected IPs is a high-fidelity indicator.
- **Caveats / false positives:** Developers testing locally, automated deployment scripts rotating credentials, or Lambda functions may legitimately access secrets. Baseline the expected callers before alerting.
- **Sources:**
  - https://docs.aws.amazon.com/secretsmanager/latest/userguide/monitoring_cloudtrail.html

---

### H7 — Large EC2 RunInstances (10xlarge or Larger)

- **Detection intent:** Detect provisioning of very large EC2 instances, which may indicate cryptomining or abuse of compute resources.
- **Relevant AWS service:** Amazon EC2
- **Expected eventSource:** `ec2.amazonaws.com`
- **Expected eventName:** `RunInstances`
- **Relevant dataset columns:** `eventName`, `eventSource`, `requestParametersinstanceType`, `userIdentityarn`, `awsRegion`, `errorCode`
- **SQL filter logic:** Filter where eventSource = 'ec2.amazonaws.com' AND eventName = 'RunInstances' AND requestParametersinstanceType LIKE '%10xlarge%' OR requestParametersinstanceType LIKE '%12xlarge%' OR requestParametersinstanceType LIKE '%16xlarge%' OR requestParametersinstanceType LIKE '%24xlarge%' OR requestParametersinstanceType LIKE '%48xlarge%' or similar large-size suffixes. The `instanceType` value is a string in the requestParameters.
- **Security rationale:** AWS EC2 `RunInstances` records the requested `instanceType` in `requestParameters`. Large instance families (p4, p3, x1e, inf, trn, etc.) are expensive and are a common target for cryptomining attackers who gain unauthorized account access.
- **Caveats / false positives:** Legitimate ML training, HPC, and large-scale data processing workloads routinely use 10xlarge+ instances. Correlate with known project principals and regions before escalating.
- **Sources:**
  - https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_RunInstances.html

---

### H8 — S3 GetBucketAcl Bucket Probing

- **Detection intent:** Detect bucket permission enumeration, often a precursor to identifying misconfigured publicly-accessible buckets.
- **Relevant AWS service:** Amazon S3
- **Expected eventSource:** `s3.amazonaws.com`
- **Expected eventName:** `GetBucketAcl`
- **Relevant dataset columns:** `eventName`, `eventSource`, `sourceIPAddress`, `userIdentityarn`, `errorCode`, `eventTime`
- **SQL filter logic:** Filter where eventSource = 's3.amazonaws.com' AND eventName = 'GetBucketAcl'. Flag high-frequency calls from a single sourceIPAddress across many distinct buckets within a short window. Also surface AccessDenied responses as probing.
- **Security rationale:** `GetBucketAcl` returns the access control list for a bucket. Rapidly iterating this across many buckets is a classical enumeration pattern to find misconfigured S3 resources. AWS logs S3 management-plane events (including ACL reads) as management events in CloudTrail by default.
- **Caveats / false positives:** Compliance scanners, security audit tools, and multi-bucket administration scripts produce legitimate high-volume GetBucketAcl activity. Source identity and user agent can help distinguish known tooling.
- **Sources:**
  - https://docs.aws.amazon.com/AmazonS3/latest/userguide/logging-with-cloudtrail.html

---

### H9a — Suspicious User Agents: kali, parrot, powershell

- **Detection intent:** Identify requests made from tooling associated with offensive security or potentially anomalous scripting environments.
- **Relevant AWS service:** All services (cross-service pattern)
- **Expected eventSource:** Any
- **Expected eventNames:** Any
- **Relevant dataset columns:** `userAgent`, `sourceIPAddress`, `userIdentityarn`, `eventName`, `eventSource`
- **SQL filter logic:** Filter where LOWER(userAgent) LIKE '%kali%' OR LOWER(userAgent) LIKE '%parrot%' OR LOWER(userAgent) LIKE '%powershell%'. Combine with other signals (errorCode, sensitive eventNames) for higher fidelity.
- **Security rationale:** The `userAgent` field reflects the HTTP User-Agent string sent by the calling client. AWS docs confirm this field captures the agent used (CLI, SDK, console, etc.). Offensive Linux distributions (Kali, Parrot OS) embed OS identifiers in user-agent strings; PowerShell-based AWS modules may indicate Windows automation outside expected IAM entities.
- **Caveats / false positives:** See Section 6 — AWS docs do not classify these strings as officially suspicious. PowerShell is widely used in legitimate Windows environments. This rule has a high false-positive rate without additional context.
- **Sources:**
  - https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html

---

### H9b — Suspicious User Agents: command/*

- **Detection intent:** Detect HTTP-based request tools (curl-style command-line clients) that may indicate direct API scripting by attackers.
- **Relevant AWS service:** All services (cross-service pattern)
- **Expected eventSource:** Any
- **Expected eventNames:** Any
- **Relevant dataset columns:** `userAgent`, `sourceIPAddress`, `userIdentityarn`, `eventName`
- **SQL filter logic:** Filter where LOWER(userAgent) LIKE 'command/%'. Combine with errorCode or sensitive API names for fidelity.
- **Security rationale:** The `userAgent` AWS field is a free-form string from the HTTP header. A prefix of `command/` is not a standard AWS SDK or CLI format and may indicate a custom tool or renamed utility used to obscure the caller's tooling identity.
- **Caveats / false positives:** See Section 6 — `command/*` is not defined as a suspicious indicator in AWS documentation. This pattern may be dataset-specific or tool-specific rather than a generic AWS-defined signal.
- **Sources:**
  - https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-record-contents.html

---

### H10 — IAM CreateAccessKey from IAM Users (Not Roles)

- **Detection intent:** Detect IAM users creating new access keys, potentially for persistence or lateral movement.
- **Relevant AWS service:** AWS IAM
- **Expected eventSource:** `iam.amazonaws.com`
- **Expected eventName:** `CreateAccessKey`
- **Relevant dataset columns:** `eventName`, `eventSource`, `userIdentitytype`, `userIdentityarn`, `userIdentityuserName`, `errorCode`
- **SQL filter logic:** Filter where eventSource = 'iam.amazonaws.com' AND eventName = 'CreateAccessKey' AND userIdentitytype = 'IAMUser'. This isolates human IAM users creating keys as opposed to automation or role-based key creation.
- **Security rationale:** AWS IAM `CreateAccessKey` logs appear in CloudTrail with the requesting identity in `userIdentity`. An IAM user creating a new access key — especially for another user — is a persistence or privilege escalation indicator. Roles (AssumedRole) performing key creation may also be suspicious but require different context.
- **Caveats / false positives:** Legitimate onboarding flows managed by admins, automated IAM provisioning pipelines, or developers rotating their own keys can trigger this. Check if the target userName in requestParameters differs from the caller's identity (self-key vs. other-user-key creation).
- **Sources:**
  - https://docs.aws.amazon.com/IAM/latest/APIReference/API_CreateAccessKey.html
  - https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-event-reference-user-identity.html

---

## 5. Prompt-Safe Domain Snippets

- CloudTrail records every AWS API call with `eventName` (the action) and `eventSource` (the service endpoint, e.g. `s3.amazonaws.com`).
- The `userIdentity.type` field classifies the caller: `Root`, `IAMUser`, `AssumedRole`, `AWSService`, or `FederatedUser`.
- `errorCode` is only present on failed API calls; `AccessDenied` and `UnauthorizedOperation` are the two primary IAM authorization failure codes.
- `sourceIPAddress` reflects the end-user IP for console events and the internal DNS name for AWS-to-AWS calls.
- `userAgent` is a free-form HTTP User-Agent string capped at 1 KB; AWS CLI, SDKs, and the console each produce distinct prefixes.
- `GetCallerIdentity` (STS) cannot be denied by IAM policy — it always succeeds regardless of the caller's permissions.
- CloudTrail `ConsoleLogin` events use `signin.amazonaws.com` as the eventSource, not an IAM service endpoint.
- Root identity (`userIdentity.type = Root`) does not populate `userName` unless an account alias is configured.
- `requestParameters` structure varies per service and API; for EC2 `RunInstances` it includes `instanceType` as a string.
- CloudTrail logs management events (control plane) by default; data events (S3 object-level, Lambda invocations) require explicit enablement on each trail.
- `AssumedRole` ARNs include the session name as a suffix: `assumed-role/RoleName/SessionName`, which can be used to identify the originating workload.
- `StopLogging`, `DeleteTrail`, and `UpdateTrail` are CloudTrail management events logged with `eventSource = cloudtrail.amazonaws.com`.
- Secrets Manager logs `GetSecretValue` as a management event visible in CloudTrail without enabling data events.
- `eventType = AwsConsoleSignIn` distinguishes interactive console sign-in events from programmatic API calls (`AwsApiCall`).

---

## 6. Things Not Found Or Uncertain

- **`kali` / `parrot` userAgent substrings as AWS-defined suspicious indicators:** AWS official documentation does **not** define any userAgent substring as an officially suspicious or threat-indicative value. The `userAgent` field is documented as a free-form string reflecting the HTTP client header. The classification of `kali` or `parrot` as suspicious is a security community convention, not an AWS-defined standard.

- **`powershell` in userAgent:** AWS docs list `aws-sdk-ruby`, `aws-cli`, and `lambda.amazonaws.com` as example userAgent values. PowerShell-based AWS modules produce identifiable strings but AWS does not label them suspicious. Whether PowerShell is anomalous is fully context-dependent (Windows environments are normal callers).

- **`command/*` userAgent prefix:** AWS documentation does not define or mention a `command/*` userAgent pattern. This appears to be dataset-specific or tool-specific. It is not derivable from any official AWS CloudTrail or SDK documentation and should be treated as a heuristic of uncertain origin rather than an AWS-sanctioned indicator.

- **"10xlarge or larger" as an AWS-defined risk threshold:** AWS EC2 documentation lists instance type names (e.g., `p4d.24xlarge`, `x1e.32xlarge`, `trn1.32xlarge`) but does not define any instance size tier as a threat indicator. The "10xlarge-or-larger" boundary for this dataset is a custom heuristic requiring string suffix parsing (e.g., checking if the instanceType value contains `10xlarge`, `12xlarge`, `16xlarge`, `24xlarge`, `32xlarge`, `48xlarge`, or `metal`). There is no AWS-published mapping from instance size to risk level.

- **`additionalEventData.MFAUsed` field:** AWS docs confirm this field exists for console sign-in events and contains `Yes` or `No`. However, it is a nested JSON field inside `additionalEventData` and **not** a top-level column in the given dataset schema. MFA enforcement detection may not be directly queryable from the provided flat CSV columns without JSON parsing.

