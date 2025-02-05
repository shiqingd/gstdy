import os

# Coverity host and server url
IT_PROD_HOST = "coverity002.sc.devtools.intel.com"
IT_PORT = ':8443'
IT_TRIAGE_STORE = 'IKT'
IT_COV_HTTPS_PORT=8443

ENTERPRISE_HOST="coverityent.devtools.intel.com"
#ENTERPRISE_PORT = '/prod3'
ENTERPRISE_PORT = '/prod7'
ENTERPRISE_TRIAGE_STORE = 'TS-NEX_kernel'
#ENTERPRISE_TRIAGE_STORE = 'IKT'
ENTERPRISE_COV_HTTPS_PORT=443

AWS_HOST="coverity.devtools.intel.com"

HOST = AWS_HOST
PORT = ENTERPRISE_PORT
TRIAGE_STORE = ENTERPRISE_TRIAGE_STORE
HTTPS_PORT = ENTERPRISE_COV_HTTPS_PORT

COV_URL = "https://"+HOST+PORT

# User credentials
USERNAME = 'sys_oak'
PASSWORD = os.environ['SYS_OAK_CRED_COVERITY_API']

# Temporary folders
BASE_BUILD_DIR = os.path.join(".", "build")
BUILD_DIR = BASE_BUILD_DIR

BASE_CONFIG_DIR = os.path.join(".", "cov_config")
CONFIG_FILE = os.path.join(BASE_CONFIG_DIR, "coverity_config.xml")

BASE_COV_IDIR = os.path.join(".", "cov_idir")
COV_IDIR = BASE_COV_IDIR

BASELINE_IDIR = "/coverity/cov_idir_baselines"

WORKSPACE = os.environ["WORKSPACE"]

if "EXECUTOR_NUMBER" in os.environ:
	REPO_BASE = os.path.join(WORKSPACE,'executor', os.environ["EXECUTOR_NUMBER"])
	os.makedirs(REPO_BASE, exist_ok=True)
else:
	REPO_BASE = WORKSPACE

# COMMIT_URL="commit://"+HOST+":9090"
COMMIT_URL = COV_URL

COV_PATH_TEMPLATE = os.environ["HOME"]+'/bin/cov-analysis-linux64-{}/bin'

