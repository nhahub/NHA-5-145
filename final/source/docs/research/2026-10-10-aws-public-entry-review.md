# CAP-04 public HTTPS entry review

Reviewed 10 October 2026. Documentation-only assessment; no AWS account access,
resource creation, subscription, upgrade, inference or deployment. This refines
[the credit-only plan](../cap04-credit-only-plan.md), not account entitlement or an
all-in price. The current checkpoint makes CAP-04 the next gate; the referenced
`docs/graduation-scope.md` was absent in this worktree.

## Decision

Domain-free trusted browser HTTPS is technically possible with generated
CloudFront hostnames. The leading candidate is **two standard pay-as-you-go
CloudFront distributions in front of one EC2 host**, preserving distinct Panel
and Controlled Storefront browser origins. This does not require two EC2 hosts or
a managed database. It is a candidate to qualify, not a deployment-ready design.

AWS provides the default `*.cloudfront.net` viewer certificate. Two generated
distribution hostnames provide distinct browser origins; different paths on one
hostname would not. [AWS distribution settings](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesGeneral.html).

**Do not select CloudFront's flat-rate Free plan:** AWS explicitly says Free Tier
accounts must upgrade to a paid account before activating any flat-rate plan,
including the $0 tier. That conflicts with the owner's no-upgrade constraint.
[AWS Flat-Rate Plans guide, account requirements and FAQ](https://docs.aws.amazon.com/PricingPlanManager/latest/UserGuide/pricingplanmanager-ug.pdf).

Pay-as-you-go CloudFront has a separate monthly allowance of 1 TB transfer and
10 million requests across the account; overages use standard pricing. This
service pricing mode is distinct from the AWS **Paid account plan**. Actual access,
verification restrictions, quotas and credit applicability remain unverified;
do not promise this account can create the required distributions or VPC origins.
[CloudFront FAQ](https://aws.amazon.com/cloudfront/faqs/),
[AWS account plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).

## Concrete blockers

1. **Secure origin connectivity.** Browser HTTPS terminates at CloudFront; it does
   not establish HTTPS to EC2. A public custom HTTPS origin needs a trusted,
   matching certificate; self-signed certificates are rejected. Thus merely
   choosing the EC2 public DNS name does not solve certificate provisioning.
   Public HTTP plus restricted ingress is still an unencrypted origin hop and
   should not be presented as end-to-end TLS.
   [AWS origin TLS requirements](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-https-cloudfront-to-custom-origin.html).

2. **Private-origin networking and outbound access.** CloudFront VPC origins can
   connect directly to EC2 in a private subnet over AWS's private connection,
   avoiding a public origin endpoint and a load balancer. AWS requires a VPC
   internet gateway, available private IPv4 address and origin security-group
   configuration; the internet gateway is not the incoming origin route. This
   is a candidate for a protected origin hop, not evidence of application-layer
   TLS. Model calls, installation and maintenance still require a separate
   outbound design. Bedrock supports private interface endpoints; alternatively,
   IPv6 outbound routing needs compatible destinations. Price and verify the
   chosen route before assuming the original small-host estimate covers it.
   [CloudFront VPC origins](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html),
   [Bedrock private endpoints](https://docs.aws.amazon.com/bedrock/latest/userguide/vpc-interface-endpoints.html),
   [VPC outbound routing](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html).

3. **Cross-site iframe identity.** `cloudfront.net` is a public suffix, so two
   generated hosts are cross-site as well as cross-origin. Strict/Lax cookies
   cannot simply be relied on inside the cross-site Storefront iframe.
   `SameSite=None; Secure` permits cross-site use but does not override browser
   blocking; partitioned cookies are a candidate with different top-level and
   embedded storage semantics. Verify the actual identity/linking flow in target
   browsers, including blocked third-party cookies, refresh and separate shoppers.
   Do not weaken CSRF, ownership, Confirmation or replay guards to make it work.
   [Public Suffix List](https://publicsuffix.org/list/public_suffix_list.dat),
   [Mozilla third-party cookie guidance](https://developer.mozilla.org/en-US/docs/Web/Privacy/Guides/Third-party_cookies).

## SSE and cache acceptance

CloudFront documents forwarding chunked responses as they arrive, so SSE is a
feasible candidate, not inherently blocked. Its default origin response timeout
is 30 seconds and applies between response packets. A separately configured
response-completion timeout bounds the entire stream; if omitted, CloudFront
does not enforce that maximum. Test timely initial events, heartbeat delivery,
slow inference, disconnection/reconnect and absence of application/proxy buffering.
[AWS response behavior](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/RequestAndResponseBehaviorCustomOrigin.html),
[AWS origin timeouts](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesOrigin.html).

Use `CachingDisabled` for shopper/session/API/SSE responses and an explicit origin
request policy forwarding required cookies, authorization, CSRF/origin headers,
query parameters and SSE resume headers. Disabling caching does not itself
configure forwarding. Positive minimum TTL can override `private`/`no-store`, so
those response headers alone are insufficient. Verify no shopper response or
`Set-Cookie` is reused across browsers, correct mutation methods, and unchanged
refresh recovery without replaying uncertain Actions.
[AWS managed cache policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-cache-policies.html),
[AWS request forwarding behavior](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/RequestAndResponseBehaviorCustomOrigin.html).

Proceed with a local cross-site identity/proxy rehearsal and a concrete private
origin plus outbound-access design. Keep AWS provisioning pending until account
access, browser acceptance and the complete credit envelope are verified. SQLite
on the existing host remains consistent with this candidate; a separate RDS
instance is not required merely to provide two HTTPS entry points.
