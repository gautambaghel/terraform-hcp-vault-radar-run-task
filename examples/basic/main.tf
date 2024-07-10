data "aws_region" "current" {}

data "tfe_organization" "hcp_tf_org" {
  name = var.hcp_tf_org
}

module "hcp_tf_run_task" {
  source                     = "../../"
  aws_region                 = data.aws_region.current.name
  hcp_tf_org                 = data.tfe_organization.hcp_tf_org.name
  run_task_fulfillment_image = var.tf_run_task_logic_image     # set your custom image
  run_task_iam_roles         = var.tf_run_task_logic_iam_roles # set your custom IAM roles
  deploy_waf                 = true
}

resource "tfe_organization_run_task" "aws_iam_analyzer" {
  organization = data.tfe_organization.hcp_tf_org.name
  url          = module.hcp_tf_run_task.runtask_url
  hmac_key     = module.hcp_tf_run_task.runtask_hmac
  name         = "custom-aws-runtask"
  enabled      = true
  description  = "Custom AWS run task integration"
}
