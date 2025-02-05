import os
import shutil
import click

def create_sync(url, branch, manifest, target_dir):
    """
    Does the following:
    * Checks if {target_dir} exists. If it doesn't, it creates it.
    * Checks if {target_dir} has been initialized. If it hasn't,
      run repo init -u {url} -b {branch}.
    * Perform repo selfupdate.
    * Perform repo sync.
    * Perform repo abandon baseline.
    * Perform repo start baseline.
    """

    current_dir = os.getcwd()
    abs_target_dir = os.path.abspath(target_dir)

    print("abs_target_dir = {}".format(abs_target_dir))

    if not os.path.isdir(abs_target_dir):
        print("{} does not exist, creating new folder...".format(abs_target_dir))
        os.mkdir(abs_target_dir)

    os.chdir(abs_target_dir)
    print("Changed directory to {}".format(os.getcwd()))
    dot_repo_folder = os.path.join(abs_target_dir, ".repo")

    # If .repo doesn't exist, whether because we've removed it or it didn't
    # exist in the first place, do repo init.

    if not os.path.isdir(dot_repo_folder):
        print("Performing repo init...")
        os.system("repo init -u {} -b {} -m {}".format(url, branch, manifest))

    print("Performing repo selfupdate...")
    os.system("repo selfupdate")

    print("Performing checkout baseline...")
    os.system("repo checkout baseline")

    print("Performing repo abandon baseline...")
    os.system("repo abandon baseline")

    print("Performing reset on all projects...")
    os.system("repo forall -vc \"git reset --hard\"")

    print("Performing repo sync...")
    os.system("repo sync -c -j5 --no-clone-bundle --prune --optimized-fetch")

    print("Performing repo start baseline...")
    os.system("repo start baseline --all")

    os.chdir(current_dir)

@click.command()
@click.option("--url", 
        help="URL of the manifest file to sync from")
@click.option("--branch", 
        help="Branch of the manifest to sync from")
@click.option("--manifest", 
        help="Select manifest within the repository.")
@click.option("--target_dir", 
        help="Target directory where the repo will be stored")
def main(url, branch, manifest, target_dir):
    """
    Simple Python script to create an Android repository in a target directory.
    Is intended to be an efficient way of doing the following:
    mkdir
    repo init -u {url} -b {branch}
    repo sync -c -f -j5
    repo abandon baseline
    repo start baseline

    This creates a "baseline" repository in target_dir, which our Android 
    scripts can then use to build Android.
    """
    create_sync(url, branch, manifest, target_dir)


if __name__ == "__main__":
    main()
