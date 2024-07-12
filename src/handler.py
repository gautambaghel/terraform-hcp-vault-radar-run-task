import os
import sys
import pty
import json
import time
import logging
import requests
import subprocess

import utils

log_level       = os.environ.get("log_level", logging.INFO)
log_group_name  = os.environ.get("CW_LOG_GROUP_NAME", False)
dev_mode        = os.environ.get("DEV_MODE", "true")

# Set the environment variables --> HCP_CLIENT_ID, HCP_CLIENT_SECRET, HCP_PROJECT_ID
env_vars = os.environ.copy()

logger = logging.getLogger()
logger.setLevel(log_level)

# THIS IS THE MAIN FUNCTION TO IMPLEMENT BUSINESS LOGIC
# TO PROCESS THE TERRFORM PLAN FILE or TERRAFORM CONFIG (.tar.gz)
# SCHEMA - https://developer.hashicorp.com/terraform/cloud-docs/api-docs/run-tasks/run-tasks-integration#severity-and-status-tags
def process_run_task(type: str, run_id: str, data: str):
    issues_count = 0
    results      = []
    status       = "passed"
    url          = "https://vault-radar-portal.cloud.hashicorp.com"
    message      = "HCP Vault Radar message!"

    if type == "pre_plan":

        with open(data, "wb") as file:
            file.write(response.content)

        with tarfile.open(data, "r:gz") as tar:
            tar.extractall(path="pre_plan")

        # Run HashiCorp Vault Radar
        scan_folder = f"/tmp/pre_plan/{run_id}"
        radar_output = f"{scan_folder}/vault-radar-output.csv"
        cmd = [
            "vault-radar",
            "scan",
            "folder",
            "--outfile",
            radar_output,
            "--path",
            scan_folder
        ]

        try:
            popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            popen.wait()
        except Exception as e:
            logger.error(f"Error: {e}")

        logger.info(popen.stdout.read())
        url, status, message, results = utils.process_radar_output(result_path=radar_output)

    elif type == "post_plan":

        # Save the plan JSON to a file
        plan_file = os.path.join("/tmp", "post_plan", run_id, "plan.json")
        os.makedirs(os.path.dirname(plan_file), exist_ok=True)
        with open(plan_file, "w") as file:
            file.write(json.dumps(data, indent=4))

        # Run HashiCorp Vault Radar
        radar_output = f"/tmp/post_plan/{run_id}/vault-radar-output.csv"
        cmd = [
            "vault-radar",
            "scan",
            "folder",
            "--outfile",
            radar_output,
            "--path",
            plan_file
        ]

        try:
            p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            stdout, stderr = p.communicate()
            logger.info(stdout.decode("utf-8"))
        except Exception as e:
            logger.error(f"Error: {e}")

        logger.info(popen.stdout.read())
        url, status, message, results = utils.process_radar_output(result_path=radar_output)

    return url, status, message, results


# <-- PLEASE DO NOT USE THIS FUNCTION IN PRODUCTION -->
# <-- This function is only for testing the callback in local dev environment -->
def test_callback(callback_url, access_token, status, message, results, url):
    # Format the payload for the callback
    # Schema Documentation - https://www.terraform.io/cloud-docs/api-docs/run-tasks-integration#request-body-1
    data = json.dumps(
        {
            "data": {
                "type": "task-results",
                "attributes": {
                    "status": status,
                    "message": message,
                    "url": url,
                },
                "relationships": {
                    "outcomes": {
                        "data": results,
                    }
                },
            }
        },
        separators=(",", ":"),
        indent=4,
    )

    options = {
        "method": "PATCH",
        "headers": {
            "Content-Type": "application/vnd.api+json",
            "Authorization": "Bearer " + access_token,
        },
        "data": data,
    }

    logger.debug(data)
    response = requests.patch(
        callback_url, headers=options["headers"], data=options["data"]
    ).json()
    logger.debug(json.dumps(response, separators=(",", ":"), indent=4))


# Main handler for the Lambda function
def lambda_handler(event, context):

    logger.debug(json.dumps(event, indent=4))

    # Initialize the response object
    runtask_response = {
        "url": "",
        "status": "failed",
        "message": "Successful!",
        "results": []
    }

    if dev_mode.lower() == "true":
        ev = {
            "payload": {
                "detail": event
            }
        }
        event = ev

    try:

        # When a user adds a new run task to their HCP Terraform organization, HCP Terraform will
        # validate the run task address and HMAC by sending a payload with dummy data.
        if event["payload"]["detail"]["access_token"] != "test-token":

            access_token             = event["payload"]["detail"]["access_token"]
            organization_name        = event["payload"]["detail"]["organization_name"]
            workspace_id             = event["payload"]["detail"]["workspace_id"]
            run_id                   = event["payload"]["detail"]["run_id"]
            task_result_callback_url = event["payload"]["detail"]["task_result_callback_url"]

            # Segment run tasks based on stage
            if event["payload"]["detail"]["stage"] == "pre_plan":

                # Download the config files locally
                # Docs - https://www.terraform.io/cloud-docs/api-docs/configuration-versions#download-configuration-files
                configuration_version_download_url = event["payload"]["detail"][
                    "configuration_version_download_url"
                ]

                # Download the config to a folder
                config_file = utils.download_config(
                    configuration_version_download_url, access_token
                )
                logger.debug(
                    f"Config downloaded for Workspace: {organization_name}/{workspace_name}, Run: {run_id}\n downloaded at {os.getcwd()}/config"
                )

                # Run the implemented business logic here
                url, status, message, results = process_run_task(type="pre_plan", run_id=run_id, path=config_file)

            elif event["payload"]["detail"]["stage"] == "post_plan":

                # Do some processing on the run task event
                # Docs - https://www.terraform.io/cloud-docs/api-docs/run-tasks-integration#request-json
                plan_json_api_url        = event["payload"]["detail"]["plan_json_api_url"]

                # Get the plan JSON
                plan_json, error         = utils.get_plan(plan_json_api_url, access_token)
                if plan_json:
                    logger.debug(f"Received plan: {organization_name}/{workspace_id}, Run: {run_id}\n")

                    # Run the implemented business logic here
                    url, status, message, results = process_run_task(type="post_plan", run_id=run_id, data=plan_json)

                if error:
                    logger.debug(f"{error}")
                    message = error

            runtask_response = {
                "url"    : url,
                "status" : status,
                "message": message,
                "results": results
            }

            # This is only used for testing the callback in local dev environment
            if dev_mode:
                test_callback(
                    callback_url=task_result_callback_url,
                    access_token=access_token,
                    status=status,
                    message=message,
                    results=results,
                    url="https://vault-radar-portal.cloud.hashicorp.com",
                )
                return None

            return runtask_response

        else:
            return runtask_response

    except Exception as e:
        logger.error(f"Error: {e}")
        runtask_response["message"] = "HCP Terraform run task failed, please look into the service logs for more details."

        # This is only used for testing the callback in local dev environment
        if dev_mode.lower() == "true":
            test_callback(
                callback_url=task_result_callback_url,
                access_token=access_token,
                status="failed",
                message=runtask_response["message"],
                results=[]
            )
            return None

        return runtask_response
