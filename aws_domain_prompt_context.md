# Prompt-Safe AWS CloudTrail Domain Context

This compact context is derived from `aws_cloudtrail_domain_context_by_perplexity.md`, whose sources are official AWS documentation URLs under `docs.aws.amazon.com`. It contains CloudTrail field and service-mapping facts only. It does not contain dataset rows, expected results, expected counts, or outcome identifiers.

## Always Include

- CloudTrail records AWS API activity with `eventName` as the requested API action and `eventSource` as the service endpoint, usually `service.amazonaws.com`.
- Use both `eventSource` and `eventName` when a service/action mapping is known; this avoids matching the same action name in the wrong AWS service.
- Query the flat DuckDB table `cloudtrail`. The dataset column names flatten nested CloudTrail fields, for example `userIdentity.type` appears as `userIdentitytype`.
- When returning raw CloudTrail events, preserve original dataset column names and prefer the full raw event column set when broad context is useful: `eventID`, `eventTime`, `sourceIPAddress`, `userAgent`, `eventName`, `eventSource`, `awsRegion`, `eventVersion`, `userIdentitytype`, `eventType`, `requestID`, `userIdentityaccountId`, `userIdentityprincipalId`, `userIdentityarn`, `userIdentityaccessKeyId`, `userIdentityuserName`, `errorCode`, `errorMessage`, `requestParametersinstanceType`.
- `sourceIPAddress` is the end-user IP for console actions. AWS-internal calls may show an AWS service DNS name or `AWS Internal`.
- `userAgent` is a free-form HTTP User-Agent value, capped by CloudTrail at 1 KB and truncated if it exceeds that size. AWS docs do not define any userAgent string as inherently malicious.
- CloudTrail management events cover control-plane API calls by default. Some data events require explicit trail configuration, but the listed management operations are usable from the provided CloudTrail records.

## Identity And Error Fields

- `userIdentitytype = 'Root'` means AWS account root credentials. Root `userIdentityuserName` is absent unless the account has an alias, so root detection should use `userIdentitytype`.
- `userIdentitytype = 'IAMUser'` means long-lived IAM user credentials. This is different from role-based temporary credentials.
- `userIdentitytype = 'AssumedRole'` means temporary role credentials from AWS STS. Assumed-role ARNs include `assumed-role/RoleName/SessionName`.
- `errorCode` is present when the AWS service call failed. `AccessDenied` and `UnauthorizedOperation` are primary authorization-failure values.
- `errorMessage` provides human-readable failure detail and can be null even when other fields identify the failure pattern.
- `requestParameters` is service/API-specific and can be omitted if it exceeds the CloudTrail size limit. In this flat dataset, EC2 instance type is available as `requestParametersinstanceType`.

## H1 - Failed Console Login

- AWS console sign-in events use `eventSource = 'signin.amazonaws.com'` and `eventName = 'ConsoleLogin'`.
- Failed console authentication is represented by `errorCode = 'Failed authentication'` in CloudTrail console sign-in records.
- Some flattened datasets may carry failure detail in `errorMessage`; when hunting failed authentication, include `errorCode = 'Failed authentication'` and also include ConsoleLogin rows where `errorCode IS NOT NULL` or `errorMessage IS NOT NULL` so sparse failure fields are not missed.
- Useful columns: `eventTime`, `sourceIPAddress`, `userIdentityuserName`, `errorCode`, `errorMessage`, `awsRegion`.
- Return the matching failed login events with original column names unless the user explicitly asks for aggregation, a time window, or a numeric threshold. Do not invent a threshold such as `HAVING count(*) > 5`.

## H2 - Root User Console Login

- Root console sign-in is a `ConsoleLogin` event with `eventSource = 'signin.amazonaws.com'` and `userIdentitytype = 'Root'`.
- Do not rely on `userIdentityuserName` for root because it may be absent unless an account alias exists.
- Any root console sign-in is high-signal, but AWS docs still treat it as a normal CloudTrail sign-in event rather than a pre-labeled threat.
- Return raw CloudTrail event rows with original dataset column names for root sign-ins. Include `eventID` when available so each event can be identified.

## H3 - CloudTrail Logging Disruption

- CloudTrail logging changes use `eventSource = 'cloudtrail.amazonaws.com'`.
- Relevant event names for disabling, deleting, or weakening trails include `StopLogging`, `DeleteTrail`, and `UpdateTrail`.
- Return both successful calls and denied attempts; the denial can be visible through `errorCode`.
- Return raw event rows for these management events, including `userIdentityarn` and the original event columns needed for triage.

## H4 - Unauthorized API Calls

- Authorization failures can occur across AWS services, so `eventSource` should usually remain broad.
- Use `errorCode IN ('AccessDenied', 'UnauthorizedOperation')` as the core filter.
- Match those `errorCode` values exactly. Do not use substring matching such as `LIKE '%AccessDenied%'` for this hypothesis, because CloudTrail error codes are categorical values.
- For a compact authorization-failure hunt, group by `eventName` and `userIdentityarn` with `count(*) AS count`. Avoid adding extra grouping fields unless the user explicitly asks for source-IP or service-level breakdowns, because they fragment the count.

## H5 - STS GetCallerIdentity Reconnaissance

- AWS STS identity checks use `eventSource = 'sts.amazonaws.com'` and `eventName = 'GetCallerIdentity'`.
- AWS docs state `GetCallerIdentity` cannot be denied by IAM policy and returns the account, user ID, and ARN for the calling identity.
- This call is a reconnaissance-style "whoami" signal, but it is also common in legitimate SDK, CLI, and CI/CD startup checks.
- For hunt output, aggregate by caller and origin as `userIdentityarn`, `sourceIPAddress`, and `userAgent` with `count(*) AS count` unless the user explicitly asks for raw event rows. Do not add a `HAVING` threshold unless the user gives one.

## H6 - Secrets Manager GetSecretValue

- Secrets Manager secret retrieval uses `eventSource = 'secretsmanager.amazonaws.com'` and `eventName = 'GetSecretValue'`.
- Useful triage fields include `userIdentityarn`, `userIdentitytype`, `sourceIPAddress`, and `errorCode`.
- Secrets Manager logs these API calls to CloudTrail as management events.
- Return raw event rows with the full original CloudTrail column set so investigators can inspect caller identity, userAgent, region, request IDs, and error fields.

## H7 - Large EC2 RunInstances

- EC2 instance launches use `eventSource = 'ec2.amazonaws.com'` and `eventName = 'RunInstances'`.
- The requested instance size is in `requestParametersinstanceType` in this flat dataset.
- `10xlarge or larger` is not an AWS-defined threat category. Treat it as an assignment heuristic requiring string parsing. Use DuckDB `regexp_matches(coalesce(requestParametersinstanceType, ''), '[0-9]{2,}xlarge')`; do not use PostgreSQL regex operators such as `~*`.
- For the hunt output, aggregate by instance type: select `requestParametersinstanceType AS instanceType` and `count(*) AS count`, then group by `requestParametersinstanceType`.

## H8 - S3 GetBucketAcl Probing

- S3 bucket ACL checks use `eventSource = 's3.amazonaws.com'` and `eventName = 'GetBucketAcl'`.
- Repeated `GetBucketAcl` calls, especially denied calls or calls across many buckets from one actor/source, can indicate bucket-name or permission enumeration.
- Useful grouping fields include `sourceIPAddress`, `userIdentityarn`, `userAgent`, and `errorCode`.
- Access failures are the core probing signal for bucket brute force; filter to `errorCode IN ('AccessDenied', 'NoSuchBucket')` when looking for bucket brute force or bucket-name probing.
- For the hunt output, group by `userIdentityarn`, `sourceIPAddress`, `userAgent`, and `errorCode` with `count(*) AS count`. Keep `eventSource = 's3.amazonaws.com'` and `eventName = 'GetBucketAcl'` in the filter. Do not add a `HAVING` threshold unless the user gives one.

## H9a - UserAgent Heuristics For Kali Parrot Powershell

- `userAgent` is free-form client metadata captured from the request.
- AWS documentation does not classify `kali`, `parrot`, or `powershell` as suspicious values.
- Treat `LOWER(userAgent) LIKE '%kali%'`, `'%parrot%'`, or `'%powershell%'` as a heuristic only, and document uncertainty in assumptions.
- For the hunt output, use this exact aggregate shape: select `userIdentityarn`, `userAgent`, and `count(*) AS count`, grouped by `userIdentityarn` and `userAgent`, to show clustered tool usage by identity.

## H9b - UserAgent Heuristic For Command Prefix

- AWS documentation does not define `command/*` as a standard CloudTrail threat indicator.
- Treat `LOWER(userAgent) LIKE 'command/%'` or an equivalent prefix/substring check as dataset-specific heuristic matching, not an AWS-defined malicious category.
- Prefer `LOWER(userAgent) LIKE '%command/%'` so command-style strings are found even when embedded in a longer userAgent.
- For the hunt output, aggregate the matching command-style userAgent token with `count(*) AS count`. If the field contains extra text, use a DuckDB expression such as `regexp_extract(userAgent, 'command/[^ ]+', 0) AS userAgent` and repeat that same `regexp_extract(...)` expression in the `GROUP BY`; do not group by the `userAgent` alias.

## H10 - IAM CreateAccessKey By IAM Users

- IAM access-key creation uses `eventSource = 'iam.amazonaws.com'` and `eventName = 'CreateAccessKey'`.
- To identify long-lived credential creation by IAM users rather than roles, filter `userIdentitytype = 'IAMUser'`.
- Useful fields include `sourceIPAddress`, `userIdentityarn`, `userIdentityuserName`, `errorCode`, and `errorMessage`.
