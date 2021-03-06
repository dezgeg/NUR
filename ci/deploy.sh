#!/usr/bin/env bash

set -x -eu -o pipefail # Exit with nonzero exit code if anything fails

#if [[ "$TRAVIS_EVENT_TYPE" == "cron" ]] || [[ "$TRAVIS_EVENT_TYPE" == "api" ]]; then
if [[ -n "$encrypted_025d6e877aa4_key=" ]]; then
  keys_dir=$(mktemp -d)
  openssl aes-256-cbc \
    -K $encrypted_025d6e877aa4_key \
    -iv $encrypted_025d6e877aa4_iv \
    -in ci/keys.tar.enc -out ci/keys.tar -d
  tar -C "$keys_dir" -xvf ci/keys.tar

  eval "$(ssh-agent -s)"

  chmod 600 "$keys_dir/"*
  ssh-add "$keys_dir/"*
  rm -rf "$keys_dir"
fi

export encrypted_080f214a372c_key= encrypted_080f214a372c_iv=

./bin/nur format-manifest
if [ -n "$(git diff --exit-code repos.json)" ]; then
  echo "repos.json was not formatted before committing repos.json:" >&2
  git diff --exit-code repos.json
  echo "Please run ./nur/format-manifest.py and updates repos.json accordingly!" >&2
  exit 1
fi

./bin/nur update
nix-build

# Pull requests and commits to other branches shouldn't try to deploy, just build to verify
if [[ "$TRAVIS_EVENT_TYPE" != "cron" ]] && [[ "$TRAVIS_EVENT_TYPE" != "api" ]]; then
  echo "Skipping deploy; just doing a build."
  exit 0
fi

git config --global user.name "Travis CI"
git config --global user.email "travis@travis.org"

#git clone git@github.com:nix-community/nur-channel

#old_channel_rev=$(git rev-parse HEAD)
#./bin/nur build-channel nur-channel
#new_channel_rev=$(git rev-parse HEAD)

if [[ -z "$(git diff --exit-code)" ]]; then
  echo "No changes to the output on this push; exiting."
else
  git add --all repos.json*

  git commit -m "automatic update"
  git push git@github.com:nix-community/NUR HEAD:master
fi

#if [[ $old_channel_rev != $new_channel_rev ]]; then
#  (cd nur-channel && git push origin master)
#fi
