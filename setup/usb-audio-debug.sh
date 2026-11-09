#!/bin/bash
# Why isn't my USB speaker/mic showing up as a sound card?
# Dumps what every non-hub USB device claims to be, what the kernel did with
# it, and what ALSA ended up with. Run: bash setup/usb-audio-debug.sh

echo "== USB devices and the interface classes they advertise =="
lsusb | grep -v -i "root hub" | while read -r line; do
  id=$(echo "$line" | sed -n 's/.*ID \([0-9a-f:]*\).*/\1/p')
  echo
  echo "--- $line"
  lsusb -v -d "$id" 2>/dev/null | grep -E "iProduct|iManufacturer|bInterfaceClass|bInterfaceSubClass|bDeviceClass" | sed 's/^ */    /'
done

echo
echo "== Kernel log: usb / audio / jieli (last 25 lines) =="
sudo dmesg 2>/dev/null | grep -i -E "usb [0-9]|snd|audio|jieli|4c4a|3654" | tail -25

echo
echo "== Sound cards ALSA knows about =="
cat /proc/asound/cards

echo
echo "== Is the USB audio driver loaded? =="
lsmod | grep -E "^snd_usb_audio" || echo "snd_usb_audio NOT loaded"

echo
echo "== PipeWire/PulseAudio view =="
command -v pactl >/dev/null && pactl list short sinks && pactl list short sources
