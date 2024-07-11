import os
import re
import csv
import time
import json
import hmac
import boto3
import tarfile
import logging
import requests

from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

logging.basicConfig(format="%(levelname)s: %(message)s")
logger = logging.getLogger()

session    = boto3.Session()
aws_region = os.environ.get("AWS_REGION", "us-east-1")
ec2_client = session.client(service_name="ec2", region_name=aws_region)

hcp_tf_host_name = os.environ.get("HCP_TF_HOST_NAME", "app.terraform.io")

def process_radar_output(result_path):
    results      = []
    url          = "https://vault-radar-portal.cloud.hashicorp.com"
    status       = "passed"
    issues_count = 0
    message      = "HashiCorp Vault Radar scan complete, no secrets found!"

    with open(result_path, "r") as file:
        radar_output = csv.reader(file)

        for row in radar_output:
            # Skip the header row
            if issues_count == 0:
                issues_count += 1
                continue

            issues_count += 1
            message = (
                f"HashiCorp Vault Radar scan complete, {issues_count} secrets found!"
            )
            error_level = get_error_level(row[4])
            tags = []
            for tag in row[12].split(" "):
                tags.append({"label": tag})
            result = json.dumps(
                {
                    "type": "task-result-outcomes",
                    "attributes": {
                        "outcome-id": f"vault-radar-{row[8]}",
                        "description": f"{row[1]} type secret found",
                        "tags": {
                            "status": [
                                {"label": f"{row[11]}", "level": error_level["level"]}
                            ],
                            "severity": [
                                {
                                    "label": error_level["label"],
                                    "level": error_level["level"],
                                }
                            ],
                            "tags": tags,
                        },
                        "body": f"""{row[1]} type secret found in `{row[7]}` with severity **{row[4]}**\n\n## Details\n\n* **Category**: {row[0]}\n* **Description**: {row[1]}\n* **Created at**: {row[2]}\n* **Author**: {row[3]}\n* **Severity**: {row[4]}\n* **Deep Link**: {row[6]}\n* **Path**: {row[7]}\n* **Value hash**: `{row[8]}`\n* **Fingerprint**: `{row[9]}`\n* **Textual Context**: `{row[10]}`\n* **Activeness**: {row[11]}\n* **Tags**: {row[12]}""",
                        "url": "https://vault-radar-portal.cloud.hashicorp.com",
                    },
                },
                separators=(",", ":"),
            )
            results.append(json.loads(result))

            if row[4] == "info" or row[4] == "medium" or row[4] == "high" or row[4] == "critical":
                status = "failed"

        return url, status, message, results


def get_error_level(severity):
    severity = severity.lower()
    if severity == "low":
        return {"label": "Low", "level": "info"}
    elif severity == "medium":
        return {"label": "Medium", "level": "warning"}
    elif severity == "high":
        return {"label": "High", "level": "error"}
    elif severity == "critical":
        return {"label": "Critical", "level": "error"}
    else:
        return {"label": severity, "level": "none"}


def download_config(configuration_version_download_url, access_token):
    headers = {
        "Content-Type": "application/vnd.api+json",
        "Authorization": "Bearer " + access_token,
    }
    response = requests.get(configuration_version_download_url, headers=headers)

    config_file = os.path.join(os.getcwd(), "pre_plan", "config.tar.gz")
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    with open(config_file, "wb") as file:
        file.write(response.content)

    with tarfile.open(config_file, "r:gz") as tar:
        tar.extractall(path="pre_plan")

    return config_file


def get_plan(url, access_token) -> str:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-type": "application/vnd.api+json",
    }

    request = Request(url, headers=headers, method="GET")
    try:
        if validate_endpoint(url):
            with urlopen(request, timeout=10) as response:
                response_raw = response
                response_read = response.read()
                json_response = json.loads(response_read.decode("utf-8"))

            logger.debug(f"Headers: {response_raw.headers}")
            logger.debug(f"JSON Response: {json.dumps(json_response, indent=4)}")
            return json_response, None
        else:
            return None, f"Error: Invalid endpoint URL, expected host is {hcp_tf_host_name}"
    except HTTPError as error:
        logger.error(str(f"HTTP error: status {error.status} - {error.reason}"))
        return None, f"HTTP Error: {str(error)}"
    except URLError as error:
        logger.error(str(f"URL error: {error.reason}"))
        return None, f"URL Error: {str(error)}"
    except TimeoutError:
        logger.error(f"Timeout error: {str(error)}")
        return None, f"Timeout Error: {str(error)}"
    except Exception as error:
        logger.error(str(error))
        return None, f"Exception: {str(error)}"


def validate_endpoint(endpoint):
    # validate that the endpoint hostname is valid
    pattern = r"^https://" + str(hcp_tf_host_name).replace(".", r"\.") + r"/.*"
    result = re.match(pattern, endpoint)
    return result
