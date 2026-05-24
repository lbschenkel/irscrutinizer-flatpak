#!/bin/bash
set -euo pipefail

APP_NAME=IrScrutinizer
APP_ID=org.harctoolbox.irscrutinizer
ARCH=x86_64
BRANCH=stable

REPO_URL=https://lbschenkel.github.io/flatpaks/repo/
REPO_KEY=FE37AF86681F953BBBFDEE920776E3BC6B5F8E4C

if [ -f "$REPO_KEY.asc" ] && gpg --list-secret-keys "$REPO_KEY" > /dev/null 2>&1;
then
  echo Signing with GPG key: $REPO_KEY
  SIGN_ARGS="--gpg-sign=$REPO_KEY"
  VERIFY_ARGS="--gpg-file=$REPO_KEY.asc"
else
  echo Building without signing
  SIGN_ARGS=""
  VERIFY_ARGS=""
fi
echo

# Build the app
flatpak run org.flatpak.Builder \
  --arch=$ARCH \
  --install-deps-from=flathub \
  --force-clean build \
  $APP_ID.yml

# Export repo, then generate bundle (.flatpak)
flatpak build-export $SIGN_ARGS repo build $BRANCH
flatpak build-bundle $SIGN_ARGS \
  --repo-url=$REPO_URL \
  --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
  repo build/$APP_NAME.$ARCH.flatpak $APP_ID $BRANCH

# Reinstall
flatpak uninstall --noninteractive -y $APP_ID || true
flatpak install $VERIFY_ARGS \
  --user --or-update --noninteractive -y \
  build/$APP_NAME.$ARCH.flatpak

# Run
flatpak run $APP_ID
