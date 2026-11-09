#!/bin/bash
# Let you manage the wall from your laptop instead of its keyboard: turns on SSH
# (remote terminal) and prints exactly what to type on the other computer.
#   cd ~/familyhub && bash setup/enable-remote.sh
set -e
echo "== installing the SSH server (needs your password) =="
sudo apt-get install -y -qq openssh-server
sudo systemctl enable --now ssh
sudo ufw allow ssh >/dev/null 2>&1 || true

IP=$(hostname -I | awk '{print $1}')
echo
echo "SSH is on. From your laptop (Windows PowerShell, or Mac/Linux Terminal) type:"
echo
echo "    ssh $USER@$(hostname).local"
echo
echo "  (if .local doesn't resolve use the IP:  ssh $USER@$IP )"
echo "Password = this computer's login password. Then you're 'at' the wall:"
echo "    cd ~/familyhub && git pull        # update"
echo "    nano ~/familyhub/.env             # edit keys (Ctrl+O Enter, Ctrl+X)"
echo "    sudo systemctl restart familyhub  # apply"
echo "    sudo reboot                       # if the kiosk needs relaunching"
echo
echo "Tip: paste into PowerShell with a right-click; into Terminal with Ctrl+Shift+V."
