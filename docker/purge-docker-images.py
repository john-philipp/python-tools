import argparse
import os
import subprocess

import logging
import docker
import re
import sys

"""
Helps to purge local docker images.
Specify which to branches to keep images from.
"""


client = docker.from_env()
all_images = client.images.list()

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(message)s")


def build_arg_parser():
    parser_ = argparse.ArgumentParser(description="Purge local images.")

    parser_.add_argument(
        "--repo-location",
        help="Specify repository path.",
        required=True)

    parser_.add_argument(
        "--list-images-cmd",
        help="Specify bash command line to run against each branch listing images to keep.",
        required=True)

    parser_.add_argument(
        "--keep-from-branches",
        help="Keep all images from these branches. Delimit using ','.",
        required=True)

    parser_.add_argument(
        "--keep-image-pattern",
        help="Keep any images matching this pattern.",
        required=False)

    parser_.add_argument(
        "--only-image-pattern",
        help="Only operate on images matching this pattern.",
        required=False)

    parser_.add_argument(
        "--always-remove-pattern",
        help="Always remove images matching this pattern. Relative priority: keep > always > only.",
        required=False)

    parser_.add_argument(
        "--remove-dangling",
        help="Remove dangling images.",
        required=False,
        default=True)

    return parser_


class Args:
    def __init__(
            self, repo_location, list_images_cmd, keep_from_branches, keep_image_pattern,
            only_image_pattern, always_remove_pattern, remove_dangling, *args, **kwargs):
        self.repo_location = repo_location
        self.list_images_cmd = list_images_cmd
        self.keep_from_branches = keep_from_branches
        self.keep_image_pattern = keep_image_pattern
        self.only_image_pattern = only_image_pattern
        self.always_remove_pattern = always_remove_pattern
        self.remove_dangling = remove_dangling


def _print_subprocess_lines(process):
    lines = process.stdout.readlines()
    for line in lines:
        logging.error(f"{line.decode()[:-1]}")
    lines = process.stderr.readlines()
    for line in lines:
        logging.error(f"{line.decode()[:-1]}")


def _clean_line(line):
    if isinstance(line, bytes):
        line = line.decode()
    if line[-1] == "\n":
        line = line[:-1]
    return line


def _handle_subprocess(*args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, error=None, **kwargs):
    p = subprocess.Popen(args, stdout=stdout, stderr=stderr, **kwargs)
    p.poll()
    stdout_lines = [_clean_line(l) for l in p.stdout.readlines()]
    stderr_lines = [_clean_line(l) for l in p.stderr.readlines()]

    if p.returncode:
        for i, line in enumerate(stdout_lines):
            logging.error(f"stdout.{i:04}: {line}")
        for i, line in enumerate(stderr_lines):
            logging.error(f"stderr.{i:04}: {line}")
        raise error or ValueError

    return p.returncode, stdout_lines, stderr_lines


def _check_matches_pattern(input, pattern):
    return re.compile(pattern).match(input) is not None


def git_checkout_branch(branch):
    _handle_subprocess("git", "checkout", branch, error=ValueError(f"Failed to checkout branch {branch}!"))


def git_check_dirty():
    _, stdout, stderr = _handle_subprocess("git", "diff", "HEAD", error=ValueError(f"Failed to diff repo!"))
    if stdout or stderr:
        return True
    return False


# Must be supplied with script that gives out all images to keep per branch.
def read_images_to_keep(cmd):
    _, stdout, _ = _handle_subprocess("bash", "-c", cmd)
    images = set()
    for line in stdout:
        images.add(line)
    return images


def filter_images(images_found, images_to_keep, args: Args):

    tags_to_remove = set()
    images_to_remove = set()
    for image in images_found:
        repo_tags = image.attrs["RepoTags"]

        if not repo_tags:
            id = image.attrs["Id"]
            logging.warning(f"Dangling (remove={args.remove_dangling}): {id}")

            if args.remove_dangling:
                tags_to_remove.add(id)
                images_to_remove.add(image)
            continue

        for repo_tag in repo_tags:

            # Keep these images. Keep > always. Explicit keep.
            if args.keep_image_pattern:
                if _check_matches_pattern(repo_tag, args.keep_image_pattern):
                    continue

            # Always remove. Always > only. Explicit removal.
            if args.always_remove_pattern:
                if _check_matches_pattern(repo_tag, args.always_remove_pattern):
                    tags_to_remove.add(repo_tag)
                    images_to_remove.add(image)
                    continue

            # Only operate on these images. Explicit limiter for remainder.
            if args.only_image_pattern:
                if not _check_matches_pattern(repo_tag, args.only_image_pattern):
                    continue

            # Unless an image on one of the specified branches, keep.
            if repo_tag not in images_to_keep:
                tags_to_remove.add(repo_tag)
                images_to_remove.add(image)

    return tags_to_remove, images_to_remove


def estimate_total_size(images):
    total_size_bytes = 0.
    for image in images:
        # Estimate. We're not account for layer overlap, which will be significant.
        total_size_bytes += image.attrs["Size"]
    return total_size_bytes


def remove_images_by_tags(tags_to_remove):
    for tag_to_remove in tags_to_remove:
        try:
            client.images.remove(tag_to_remove)
            logging.info(f"Removed: {tag_to_remove}")
        except Exception as ex:
            logging.error(f"Failed to remove: {tag_to_remove}")


def main(call_args):
    parser = build_arg_parser()
    args_ = parser.parse_args([arg for arg in call_args[1:] if arg])
    args = Args(**args_.__dict__)
    os.chdir(args.repo_location)

    # Ensure git not dirty.
    if git_check_dirty():
        logging.error("Repo is dirty!")
        return 1

    tags_to_keep = set()
    branches = args.keep_from_branches.split(",")
    for branch in branches:
        git_checkout_branch(branch)
        tags_to_keep.update(read_images_to_keep(args.list_images_cmd))

    for tag in sorted(list(tags_to_keep)):
        logging.info(f"Will keep image: {tag}")

    tags_to_remove, images_to_remove = filter_images(all_images, tags_to_keep, args)
    for tag in sorted(list(tags_to_remove)):
        logging.info(f"Will remove image: {tag}")

    size_estimate = estimate_total_size(images_to_remove)
    logging.info(f"Total size is {size_estimate/(1024 ** 3):.02f}GB (including likely layer overlaps).")

    logging.warning("Destructive. Is this what you mean?")
    input("[Enter] to confirm.")

    remove_images_by_tags(tags_to_remove)
    client.images.prune()

    logging.info("Done.")


if __name__ == '__main__':
    exit(main(sys.argv))


