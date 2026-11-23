# CAP-04 public IPv4 credit coverage — 19 October 2026

**Conclusion: account-specific Elastic IP credit coverage remains unresolved.**
The EC2 entry in this credit's applicable-services list is insufficient to mark
public IPv4 costs covered. No resource, billing probe, inference, subscription,
upgrade or authenticated API call was made for this research.

## Evidence and its limits

Owner screenshots supplied on 19 October show the USD100 credit's expiry as
**7 October 2027, 15:41 UTC**, separately from the Free plan ending **7 April
2027**. EC2, Bedrock, Lambda, DynamoDB, S3, CloudFront and CloudWatch appear in
the credit's applicable-services dialog. Both `Virtual Private Cloud` and `VPC`
searches return no match among 264 services. That observation establishes neither
coverage nor a definitive exclusion of the selected Elastic IP charge.

A subsequent owner screenshot shows the Stockholm VPC dashboard opening with
one VPC, three subnets, one route table, one internet gateway, one network ACL,
one security group, zero NAT gateways and zero Elastic IP addresses. These are
observed inventory counts. They do not establish that the VPC is the default
VPC, that this session created anything, or that this particular credit covers
IPv4 charges.

AWS classifies both `region-PublicIPv4:InUseAddress` and
`region-PublicIPv4:IdleAddress` among **Amazon VPC billing and usage codes**.
An Elastic IP attached to a stopped EC2 resource is treated as idle; stopping
the instance therefore does not remove the retained address's billable usage.
[VPC billing codes](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-billing-usage-reports.html),
[Elastic IP concepts and cost allocation](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-eip-overview.html).

AWS's limited-rollout new-signup service matrix explicitly includes **Amazon
Virtual Private Cloud** in its Free Tier selection. This supports service
availability in that experience and is consistent with the dashboard opening.
It does not resolve the separate credit applicability discrepancy or prove
permission to allocate an address in this owner's project.
[New-signup supported services](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html).

AWS credits apply to eligible service charges; its Billing documentation directs
credit questions to Support. Generic eligibility or pricing documentation cannot
replace the missing account-specific determination.
[Applying AWS credits](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/useconsolidatedbilling-credits.html).

The Free account plan is documented to incur no charges while active and to end
at six months or credit exhaustion, whichever occurs first. That is the account
plan boundary, not evidence that every requested service or usage type is
available or credit-eligible. The later credit expiry does not extend the earlier
Free-plan access deadline. Keep the Free plan and avoid upgrade triggers.
[Account-plan rules](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).

## Smallest useful owner step

Obtain a Billing/Account Support clarification through an available account-help
channel, without upgrading or provisioning. Suggested exact question:

> My active Free-plan project is in eu-north-1. Its Free Tier credit lists Amazon
> Elastic Compute Cloud, but searches for VPC and Virtual Private Cloud show no
> applicable service. Does this specific credit cover both PublicIPv4:InUseAddress
> and PublicIPv4:IdleAddress for one retained AWS Elastic IP, including while its
> EC2 instance is stopped? Can I use this configuration on the current Free plan
> without upgrading or activating advanced features?

Record the response before closing this credit-coverage gate. Keep the existing
gross IPv4 allowance in the cost model; do not deduct an assumed legacy free
allowance or replace this missing evidence with a billable experiment.
