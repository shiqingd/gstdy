import click
import subprocess
import os
import sys
import re
from lib.utils import cmd_pipe

class FatalError(RuntimeError):
    pass

def run_cmd(cmd_list, target_dir=None):
    """Runs a subprocess. If it succeeds, does nothing. If it fails,
    prints stdout and stderr before raising a RuntimeError.
    If target_dir is provided, changes to the target_dir before running.
    """
    olddir = os.getcwd()
    if target_dir:
        os.chdir(target_dir)
    print("Current directory = {}".format(os.getcwd()))
    print("Running the following command:\n{}".format(
        " ".join(cmd_list)))
    proc = subprocess.run(cmd_list, 
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if(proc.returncode == 0):
        print("Command ran successfully.")
        os.chdir(olddir)
        return 0
    else:
        print("Command failed.\n\nSTDOUT:\n{}\n\nSTDERR:\n{}".format(
            proc.stdout.decode(), proc.stderr.decode()))
        raise RuntimeError("STDOUT:\n{}\x1fSTDERR:\n{}".format(
            proc.stdout.decode(), proc.stderr.decode()))


def apply_patches(kernel_dir, branch, patches_dir, platform, version,
                  series_location=None):
    """Runs git quilt-import to apply patches to the kernel_dir on branch.
    series_location defaults to patches_dir/series, but can be set
    to something else.
    Throws a RuntimeError if git quilt-import fails.
    """
    if not series_location:
        series_location = os.path.join(patches_dir, platform, "patches", 
                                       "series")

    kernel_checkout_cmd = [
        "git",
        "checkout",
        branch
    ]

    cve_checkout_cmd = [
        "git",
        "checkout",
        version
    ]

    patch_cmd = [
        "git", 
        "quiltimport", 
        "--patches", 
        os.path.abspath(os.path.join(patches_dir, platform, "patches")),
        "--series", 
        os.path.abspath(series_location)
    ]

    try:
        run_cmd(kernel_checkout_cmd, kernel_dir)
        run_cmd(cve_checkout_cmd, patches_dir)
        run_cmd(patch_cmd, kernel_dir)
    except RuntimeError as e:
        raise FatalError(str(e))

def git_push_branch(target_name, repo_dir, **kwargs):
    """Simple function to push the current branch to its origin.
    Resolves to 

    pushd repo_dir
    git push origin target_name
    popd

    If dry_run=True is passed, it won't actually push it and instead will
    just print the command.

    """

    olddir = os.getcwd()
    os.chdir(repo_dir)

    create_branch_cmd = [
        "git",
        "checkout",
        "-b",
        target_name
    ]

    push_cmd = [
        "git",
        "push",
        "origin",
        target_name
    ]

    run_cmd(create_branch_cmd, repo_dir)

    if not kwargs.get("dry_run", False):
        run_cmd(push_cmd, repo_dir)
    else:
        print("Dry run: {}".format(" ".join(push_cmd)))
    os.chdir(olddir)

def git_clone(remote_name, target_dir):
    """Git clones remote_name to target_dir."""
    clone_cmd = [
        "git",
        "clone",
        remote_name,
        target_dir
    ]
    run_cmd(clone_cmd)

def git_clone_config(remote_name, branch, target_dir):
    """Git clones remote_name to target_dir."""
    clone_cmd = [
        "git",
        "clone",
        remote_name,
        "-b",
        branch,
        target_dir
    ]
    run_cmd(clone_cmd)

def git_cve_tag(tag_to_push, repo_dir, **kwargs):
    """Git create cve tag and push to remote."""

    olddir = os.getcwd()
    os.chdir(repo_dir)
    msg = "CVE: Creating cve tag for " + tag_to_push

    create_tag_cmd = [
            "git",
            "tag",
            "-a",
            tag_to_push,
            "HEAD",
            "-m",
            msg
        ]

    push_cmd = [
            "git",
            "push",
            "origin",
            tag_to_push
        ]

    run_cmd(create_tag_cmd, repo_dir)

    if not kwargs.get("dry_run", False):
        run_cmd(push_cmd, repo_dir)
    else:
        print("Dry run: {}".format(" ".join(push_cmd)))

    os.chdir(olddir)

def get_upstream_tag(repo_dir):
    """Get kernel upstream version."""

    olddir = os.getcwd()
    os.chdir(repo_dir)

    get_upstream_tag_cmd = "make kernelversion"
    (rc, a, err) = cmd_pipe(get_upstream_tag_cmd)
    upstream_kernel_version = "v" + a
    os.chdir(olddir)

    return upstream_kernel_version

def write_prop(d, target):
    """Given a dictionary, writes a .prop file to target."""
    with open(target, "w") as f:
        for key, value in d.items():
            print(f"{key}={value}", file=f)

def patch_and_push(branch, platform, version, series_location, dry_run):
    resolved_patch_dir = os.path.join("patch_repo", platform, "patches")
    print("Applying patches...")
    apply_patches("kernel_repo", branch, "patch_repo", platform, version, 
                  series_location)

    if "yocto" in branch:
        platform = "yocto"
    cve_branch = re.sub(platform, f"{platform}-cve", branch)
    
    print(f"Pushing patched branch to {cve_branch}...")
    git_push_branch(cve_branch, os.path.abspath("kernel_repo"), dry_run=dry_run)
    return cve_branch

def apply_config_patches(config_dir, branch, patches_dir, version,
                  series_location=None):
    """In the future, we might need to modify the kernel-config as well as the
    kernel. This means that we'll need to push a cve-kernel-config branch as
    well as a cve-kernel branch. 
    
    Right now, this does nothing but checkout the kernel-config branch because
    no patches are currently needed for the kernel-config repo."""

    config_checkout_cmd = [
        "git",
        "checkout",
        branch
    ]

    olddir = os.getcwd()
    os.chdir(config_dir)

    run_cmd(config_checkout_cmd)
    # Patch command here! Currently a placeholder.
    os.chdir(olddir)

def patch_and_push_configs(android_branch, version, series_location, dry_run):
    """Run the patches, and then push the branch. Right now, no patching
    is taking place, so we're just creating a new branch that contains
    the same content as the existing branch but contains an extra cve
    prefix before the timestamp.

    staging/4.19/lts-190408T084325Z becomes
    staging/4.19/lts-cve-190408T084325Z
    """
    if version == "4.19":
        resolved_config_branch = re.sub(r"/android", "", android_branch) 
        new_branch = re.sub(r"lts-", r"lts-cve-", resolved_config_branch)
    else:
        resolved_config_branch = re.sub("android-", "", android_branch)
        new_branch = re.sub(f"{version}/", f"{version}/cve-", resolved_config_branch)
    apply_config_patches("config_repo", resolved_config_branch, "patch_repo", 
            version, series_location)

    git_push_branch(new_branch, os.path.abspath("config_repo"), dry_run=dry_run)
    return new_branch

    

@click.command()
@click.option("--patch_repo", 
    help="Remote location of patch repo")
@click.option("--kernel_repo", 
    help="Remote location of kernel repo")
@click.option("--config_repo", 
    help="Remote location of kernel-config repo")
@click.option("--android_branch",
    help="Android branch to be patched")
@click.option("--base_branch",
    help="Base branch to be patched")
@click.option("--yocto_branch", default=None,
    help="Yocto branch to be patched")
@click.option("--android/--no_android", default=False,
    help="Patch Android?")
@click.option("--yocto/--no_yocto", default=False,
    help="Patch Yocto?")
@click.option("--version", 
    help="Kernel version number (4.19, 4.14, etc)")
@click.option("--series_location", default=None, 
    help="Location of series file. Defaults to be inside patch repo folder.")
@click.option("--dry_run", default=False, type=bool,
    help="Determines whether the program will actually push the CVE branch.")
@click.option("--upstream_kernel_version", default=None,
    help="Upstream version of kernel being built")
def main(patch_repo, kernel_repo, config_repo, android_branch, base_branch, yocto_branch, android, yocto, version, 
         series_location, dry_run, upstream_kernel_version):
    """Program that applies patches from patch_dir to kernel_dir."""
    if not all([patch_repo, kernel_repo, config_repo,
        base_branch, version, upstream_kernel_version]):
        print("Not all parameters were provided! Exiting.")
        sys.exit(1)

    if not yocto_branch:
        yocto_branch = re.sub("base", "yocto", base_branch)

    print("Cloning patch repo...")
    git_clone(patch_repo, "patch_repo")

    print("Cloning kernel repo...")
    git_clone(kernel_repo, "kernel_repo")

    print("Cloning kernel-config repo...")
    git_clone_config(config_repo, "4.14/config", "config_repo")

    mydir = os.getcwd()

    if android:
        try:
            new_android_branch = patch_and_push(
                android_branch, "android", version, series_location, dry_run)
        except FatalError as e:
            print("Unable to patch! Failing!")
            last_stdout_line = str(e).split("\x1f")[0].split("\n")[-1].strip()
            if last_stdout_line.endswith(".patch"):
                print("It's likely that the following patch failed: {}".format(
                    last_stdout_line))
            else:
                print("Check error logs above for STDOUT and STDERR of failed command.")
            sys.exit(1)
        except:
            print("Probably already pushed?")
            new_android_branch = re.sub("android", "android-cve", android_branch)
            os.chdir(mydir)
    if yocto:
        try:
            new_yocto_branch = patch_and_push(
                yocto_branch, "base", version, series_location, dry_run)
        except FatalError as e:
            print("Unable to patch! Failing!")
            last_stdout_line = str(e).split("\x1f")[0].split("\n")[-1].strip()
            if last_stdout_line.endswith(".patch"):
                print("It's likely that the following patch failed: {}".format(
                    last_stdout_line))
            else:
                print("Check error logs above for STDOUT and STDERR of failed command.")
            sys.exit(1)
        except:
            print("Probably already pushed?")
            new_yocto_branch = re.sub("yocto", "yocto-cve", android_branch)
            os.chdir(mydir)
    try:
        new_base_branch = patch_and_push(
            base_branch, "base", version, series_location, dry_run)
    except FatalError:
        print("Unable to patch! Failing!")
        sys.exit(1)
    except:
        print("Probably already pushed?")
        new_base_branch = re.sub("base", "base-cve", base_branch)
        os.chdir(mydir)

    if version in ["4.14"]:
        new_config_branch = re.sub("base", "cve", base_branch)
        try:
            git_push_branch(new_config_branch, os.path.abspath("config_repo"), dry_run=dry_run)
        except:
            print("Probably already pushed?")
            os.chdir(mydir)

        try:
            timestamp = base_branch.split('-')[-1]
            upstream_kernel_version = get_upstream_tag(os.path.abspath("kernel_repo"))
            tag_to_push = "lts-" + upstream_kernel_version + "-cve-" + timestamp
            git_cve_tag(tag_to_push, os.path.abspath("patch_repo"), dry_run=dry_run)
        except:
            print("Failed to apply cve tag!")
            sys.exit(1)

    #try:
    #    new_config_branch = patch_and_push_configs(
    #        android_branch, version, series_location, dry_run)
    #except FatalError as e:
    #    print("Unable to patch! Failing!")
    #    last_stdout_line = str(e).split("\x1f")[0].split("\n")[-1].strip()
    #    if last_stdout_line.endswith(".patch"):
    #        print("It's likely that the following patch failed: {}".format(
    #            last_stdout_line))
    #    else:
    #        print("Check error logs above for STDOUT and STDERR of failed command.")
    #    sys.exit(1)
    #except:
    #    print("Probably already pushed?")
    #    os.chdir(mydir)

    # Currently only 4.19, but could include more if we're writing more prop files.
    if version in ["4.19"]:
        print("Writing prop file containing CVE branches...")
        write_prop(
                {
                    "ABB":new_base_branch,
                    "UPSTREAM_KERNEL_VERSION":upstream_kernel_version
                }, "branch.prop")

if __name__ == "__main__":
    main()
