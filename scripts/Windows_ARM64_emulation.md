# Windows ARM64 Emulation with QEMU

## 1. Installing QEMU

Inside a MSYS2 MinGW-w64 x86_64 shell:

```bash
pacman -S mingw-w64-x86_64-qemu 
```

## 2. Check ARM64 UEFI Firmware
QEMU needs UEFI firmware for ARM64. Check if firmware exists in MSYS2
```bash
ls /mingw64/share/qemu/edk2-aarch64-code.fd
```
## 3. Choose directory for VM files
```bash
mkdir -p /c/qemu/win-arm64
cd /c/qemu/win-arm64
```

## 3. Create Virtual Disk

```bash
qemu-img create -f qcow2 win-arm64.qcow2 64G
```

## 4. Download Windows 11 ARM64 ISO
Download from https://www.microsoft.com/en-us/software-download/windows11arm64

## 5. Start QEMU - First Boot (Installation)

```bash
qemu-system-aarch64 \
  -M virt \
  -cpu max,pauth-impdef=on \
  -smp 6 \
  -m 8G \
  -bios /mingw64/share/qemu/edk2-aarch64-code.fd \
  -accel tcg,thread=multi \
  -device ramfb \
  -device qemu-xhci \
  -device usb-kbd \
  -device usb-tablet \
  -netdev user,id=n0,hostfwd=tcp::3390-:3389 \
  -device virtio-net-pci,netdev=n0 \
  -drive if=none,id=usbdisk,file=$(pwd)/win-arm64.qcow2,format=qcow2 \
  -device usb-storage,drive=usbdisk \
  -drive if=none,id=usbiso,file=$(pwd)/Win11_25H2_English_Arm64.iso,media=cdrom \
  -device usb-storage,drive=usbiso \
  -display gtk
```



## 6. Start QEMU - Normal Boot (After Installation)

After Windows is installed, boot without the ISO:

