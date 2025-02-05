import requests,os,shutil,logging,psycopg2,sys,re
from ssh_session import SSHSession

if not "DJANGO_SETTINGS_MODULE" in os.environ:
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.settings")
	import django
	django.setup()

try:
	assert('DATABASE_HOST' in os.environ)
except:
	print("Environment Variable DATABASE_HOST not set", file=sys.stderr)
	sys.exit(1)

from framework.models import Kernel

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s')

HOST = os.environ.get('FILE_SERVER', 'ikt.bj.intel.com')
USER = os.environ.get('FILE_SERVER_USER', 'irda')
FILE_SERVER_PORT =  os.environ.get('FILE_SERVER_PORT', 8010)

REPORT_URL_TEMPLATE = 'http://%s:%d/kernel_test_report/%%s/%%s/%%s'%(HOST,FILE_SERVER_PORT)
REMOTE_PATH_TEMPLATE = '/var/www/html/kernel_test_report/%s/%s'


def upload_file(local_path, remote_path):
    password = os.environ.get('IRDA_CRED_SYS')
    ssh_session = SSHSession(USER,HOST,password)
    logger.debug('Upload csv and txt file.')
    print(f'local: {local_path}, remote: {remote_path}')
    ssh_session.scp_send(local=local_path, remote=remote_path, password=password,recursive=True, timeout=300)


def save(file_list,tag,result,category='banned-words'):
    """upload to IOTG Kernel Testing Dashboard"""
    if "mainline-tracking" in tag:
        kernel_version = "mainline-tracking"
    elif "iotg-next" in tag:
        kernel_version = "iotg-next"
    else:
        match = re.search(r"v(\d+.\d+)", tag)
        if match:
            kernel_version = f"v{match.group(1)}"
        else:
            kernel_version = None

    pwd = os.getcwd()
    tag_path = tag.split('/')[-1]
    local_path = os.path.join(pwd,tag_path)
    if not os.path.exists(local_path):
        os.mkdir(local_path)
        for filename in file_list:
            shutil.copy(filename,local_path)

    reporturl = REPORT_URL_TEMPLATE% (category,kernel_version,tag_path)
    remote_path = REMOTE_PATH_TEMPLATE% (category,kernel_version)

    upload_file(local_path,remote_path)
    shutil.rmtree(local_path)

    '''
    sample:
        #   EXTRA_DATA_REPORT_URL=<url>
        #   EXTRA_DATA_TEST_RESULT=
    '''
    EXTRA_DATA_REPORT_URL='#   EXTRA_DATA_REPORT_URL=%s\n'% reporturl
    EXTRA_DATA_TEST_RESULT='#   EXTRA_DATA_TEST_RESULT=%d\n'%result
    if result != 3:
        print(EXTRA_DATA_REPORT_URL,EXTRA_DATA_TEST_RESULT)

    return reporturl