#!/usr/bin/env bash
# Installs caselight for the current user and the udev rule (asks for sudo once).
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Installing udev rule (needs sudo)"
[ -f /etc/udev/rules.d/60-caselight.rules ] && cmp -s udev/60-caselight.rules /etc/udev/rules.d/60-caselight.rules && echo "already installed" || { sudo install -m 644 udev/60-caselight.rules /etc/udev/rules.d/60-caselight.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw; }

echo "==> Installing caselight"
if command -v pipx >/dev/null; then
  pipx install --force .
elif python3 -m pip --version >/dev/null 2>&1; then
  python3 -m pip install --user --break-system-packages .
else
  # No pip: caselight has no dependencies, so a launcher pointing at this folder is enough.
  mkdir -p ~/.local/bin
  cat > ~/.local/bin/caselight <<LAUNCHER
#!/bin/sh
PYTHONPATH="$PWD\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m caselight "\$@"
LAUNCHER
  chmod +x ~/.local/bin/caselight
  echo "Installed launcher ~/.local/bin/caselight (keep this folder in place)"
fi

echo "==> Installing systemd user service (not enabled)"
mkdir -p ~/.config/systemd/user
install -m 644 systemd/caselight.service ~/.config/systemd/user/caselight.service
systemctl --user daemon-reload

echo
echo "Done. Try:  caselight info"
echo "Start the UI on login:  systemctl --user enable --now caselight"
