import requests
import re
from bs4 import BeautifulSoup
import sys

def get_all_links(url, username, password):
    """Obtains all links contained in the HTML returned from url."""
    r = requests.get(url, verify=False, 
                          auth=requests.auth.HTTPBasicAuth(username, password))
    if r.status_code != 200:
        raise RuntimeError(
            f"Unable to get a response from {url}: status code {r.status_code}"
        )
    soup = BeautifulSoup(r.text)
    return [link for link in soup.findAll("a")]

def get_latest_link(url, username, password):
    links = get_all_links(url, username, password)
    filter_re = re.compile(r"\d{8}_\d{1,2}/")
    filtered = [link for link in links 
                    if filter_re.fullmatch(link.attrs["href"])]
    return max(filtered, key=lambda link : link.attrs["href"])

def get_flashfiles_link(url, username, password):
    links = get_all_links(url, username, password)
    filter_re = re.compile("gordon_peak_acrn-flashfiles-.*\.zip")
    return [link for link in links 
            if filter_re.fullmatch(link.attrs["href"])][0]

def get_download_page(base_url, username, password):
    latest = get_latest_link(base_url, username, password)
    dirname = latest.attrs["href"]
    return f"{base_url}{dirname}gordon_peak_acrn/userdebug/"

def construct_download_link(base_url, username, password):
    download_page = get_download_page(base_url, username, password)
    link = get_flashfiles_link(download_page, username, password)
    filename = link.attrs["href"]
    return f"{download_page}{filename}"

def main():
    base_url = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    print(construct_download_link(base_url, username, password), end="")

if __name__ == "__main__":
    main()
