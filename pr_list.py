import requests
import json
import os
import logging
from github import Github

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("This is an info message")


# Repository information
kernel_repos_branches = {
    "os.linux.kernel.mainline-tracking-staging": ["mainline-tracking/v6.13", "mainline-tracking/v6.13-rc3"],
    "os.linux.kernel.kernel-lts-staging": ["6.12/linux", "6.6/linux", "6.6/deepin/dev/linux", "6.6/kylin/dev/linux", "6.6/tiber/dev/linux", "6.6/tiber/dev/preempt-rt", "6.6/dovetail-xenomai", "6.1/linux", "5.15/android_u", "5.15/android_t", "4.19/android_s"],
    "os.linux.kernel.kernel-staging": ["iotg-next/v6.13", "iotg-next/v6.13-rc3", "svl/pre-si/linux/v6.12"]
}

config_branches = {
    "mainline-tracking/v6.11": "staging/mainline-tracking/v6.11",
    "mainline-tracking/v6.13": "staging/mainline-tracking/v6.13",
    "6.12/linux": "6.12/config",
    "6.6/linux": "6.6/config",
    "6.6/deepin/dev/linux": "6.6/deepin",
    "6.6/kylin/dev/linux": "6.6/kylin",
    "6.6/tiber/dev/linux": "6.6/tiber",
    "6.6/dovetail-xenomai": "6.6/dovetail-xenomai",
    "6.1/linux": "6.1/config",
    "5.15/android_u": "5.15/config_u",
    "5.15/android_t": "5.15/config_t",
    "4.19/android_s": "4.19/config_s",
    "iotg-next/v6.13": "staging/iotg-next/v6.13",

}

config_repo = "os.linux.kernel.kernel-config"

# HTML file
output_file = "pull_requests.html"

# Start HTML file
html_content = """
<html>
<head>
    <title>Kernel Repo Pull Requests</title>
    <style>
        body {
            font-family: Arial, sans-serif;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #dddddd;
            text-align: left;
            padding: 8px;
        }
        th {
            background-color: #4CAF50;
            color: white;
        }
        tr:nth-child(even) {
            background-color: #f2f2f2;
        }
        tr:hover {
            background-color: #ddd;
        }
    </style>
</head>
<body>
<h1>Kernel Repo Pull Requests</h1>
<table>
<tr><th>Kernel Repo Branch</th><th>Kernel Config Branch</th></tr>
"""

logger.info("##### Function to fetch pull requests for a given repo and branch #####")

def fetch_pull_requests(repo, branch):
    g = Github()
    repo_object = g.get_repo('intel-innersource/' + repo)
    logger.info(repo_object)
    pulls = repo_object.get_pulls(state='open',base=branch)
    logger.info(pulls)

    return ' '.join([f"""<a href="{pr.url.replace('https://api.github.com/repos/', 'https://github.com/').replace('/pulls/', '/pull/')}">{pr.title}</a><br>""" for pr in pulls])


logger.info("##### Loop through each kernel repo and branch #####")
for repo, branches in kernel_repos_branches.items():
    logger.info(repo,branches)
    for branch in branches:
        logger.info(branch)
        kernel_prs = fetch_pull_requests(repo, branch)
        config_branch = config_branches.get(branch, "")
        config_prs = fetch_pull_requests(config_repo, config_branch)
        
        # Add rows to HTML table
        html_content += f"""
        <tr>
        <td><b>{branch}</b><br>{kernel_prs}</td>
        <td><b>{config_branch}</b><br>{config_prs}</td>
        </tr>
        """

# End HTML file
html_content += """
</table>
</body>
</html>
"""

logging.info("##### End HTML file #####")
with open(output_file, 'w') as f:
    f.write(html_content)

logging.info(f"Pull requests have been saved to {output_file}")
