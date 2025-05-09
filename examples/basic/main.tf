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
  hcp_project_id             = var.hcp_project_id
  hcp_client_id              = var.hcp_client_id
  hcp_client_secret          = var.hcp_client_secret
}

resource "tfe_organization_run_task" "aws_iam_analyzer" {
  organization = data.tfe_organization.hcp_tf_org.name
  url          = module.hcp_tf_run_task.runtask_url
  hmac_key     = module.hcp_tf_run_task.runtask_hmac
  name         = "hcp-vault-radar-runtask"
  enabled      = true
  description  = "HCP Vault Radar run task"
}
