# IrScrutinizer (Flatpak)

This is a Flatpak package for [IrScrutinizer](https://github.com/bengtmartensson/IrScrutinizer),
a powerful program for capturing, generating, analyzing, importing, and
exporting of infrared (IR) signals.
It includes the Java runtime.

## Installation

Pick one the following, from most recommended to least:

1. Add [my Flatpak repository](https://lbschenkel.github.io/flatpaks/).
   That will make RemoteMaster and my other Flatpaks available,
   and you will get updates.

2. Download and open the [.flatpakref](https://github.com/lbschenkel/irscrutinizer-flatpak/raw/refs/heads/main/org.harctoolbox.irscrutinizer.flatpakref).
   It will download from my repo and you will get updates, but only for
   this particular Flatpak.

3. Download the individual Flatpak bundle from
   [releases](https://github.com/lbschenkel/irscrutinizer-flatpak/releases).
   You will not get any updates and need to install any new versions manually.

### Permissions

This Flatpak requests the following minimal permissions:
- filesystem: only `$HOME/Downloads`
- network: disabled
- devices: disabled

If you want to download codes from the Internet, or talk to serial
devices, or read/write anywhere in your `$HOME`, you can use
[Flatseal](https://github.com/tchx84/Flatseal) or:
```
flatpak override --user --network org.harctoolbox.irscrutinizer
flatpak override --user --devices=all org.harctoolbox.irscrutinizer
flatpak override --user --filesystem=home org.harctoolbox.irscrutinizer
```

## Building it yourself

Use the `build.sh` script or something like:
```
flatpak run org.flatpak.Builder \
  --arch=x86_64 \
  --install --install-deps-from=flathub \
  --force-clean build \
  org.harctoolbox.irscrutinizer

flatpak run org.harctoolbox.irscrutinizer
```
