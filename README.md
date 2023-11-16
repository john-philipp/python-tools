# python-tools
Some tools written in Python.

# Prerequisites

 - python3
 - `pip3 install -r requirements.txt`

# purge-docker-images.py

```
python3 purge-docker-images.py --help
usage: purge-docker-images.py [-h] --repo-location REPO_LOCATION --list-images-cmd LIST_IMAGES_CMD --keep-from-branches KEEP_FROM_BRANCHES [--keep-image-pattern KEEP_IMAGE_PATTERN]
                              [--only-image-pattern ONLY_IMAGE_PATTERN] [--always-remove-pattern ALWAYS_REMOVE_PATTERN] [--remove-dangling REMOVE_DANGLING]

Purge local images.

options:
  -h, --help            show this help message and exit
  --repo-location REPO_LOCATION
                        Specify repository path.
  --list-images-cmd LIST_IMAGES_CMD
                        Specify bash command line to run against each branch listing images to keep.
  --keep-from-branches KEEP_FROM_BRANCHES
                        Keep all images from these branches. Delimit using ','.
  --keep-image-pattern KEEP_IMAGE_PATTERN
                        Keep any images matching this pattern.
  --only-image-pattern ONLY_IMAGE_PATTERN
                        Only operate on images matching this pattern.
  --always-remove-pattern ALWAYS_REMOVE_PATTERN
                        Always remove images matching this pattern. Relative priority: keep > always > only.
  --remove-dangling REMOVE_DANGLING
                        Remove dangling images.
```
For when you have a large number of images, some of which you'd like to keep based on a git repo and a selection of branches and there's a way to determine which images those are on a per-branch basis. That is each branch specified, there is the same command line, that outputs all image tags to keep (including versions) that you'd like to keep, one per line.

A simple example could be:
```
> list-docker-images.sh # Executable.
echo ubuntu:${VERSION_USED_IN_BRANCH}
```

This script defines which images to keep. Well keep the Ubuntu image for whichever set of constants are defined across the branches we specify at invocation.

Suppose we'd like to keep images from `branch1` and `branch2` in repo `$HOME/projects/repo`. Our invocation can look like:
```
python purge-docker-images.py \
    --repo-location=$HOME/projects/repo \
    --list-images-cmd="list-docker-images.sh" \
    --keep-from-branches branch1,branch2 \
    --keep-image-pattern=".*docker.*" \
    --only-image-pattern=".*ubuntu.*" \
    --always-remove-pattern=".*dev.*" \
    --remove-dangling=true
```

This does the following:
 - Go to repo `$HOME/projects/repo`,
 - keeping all images returned by `list-docker-images.sh` on `branch1` and `branch2`, respectively,
 - keeping all images containing `docker`,
 - operating only on images containing `ubuntu`,
 - always removing any image containing `dev`,
 - removing any dangling images,
 - remove docker images. 