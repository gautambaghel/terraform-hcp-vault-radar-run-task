import os
import re
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

session = boto3.Session()
ec2_client = session.client(service_name="ec2", region_name=aws_region)

hcp_tf_host_name = os.environ.get("HCP_TF_HOST_NAME", "app.terraform.io")

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
