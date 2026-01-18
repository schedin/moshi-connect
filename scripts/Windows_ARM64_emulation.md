# Windows ARM64 Emulation with QEMU

## 1. Installing QEMU on Windows in MSYS2

Inside a MSYS2 MinGW-w64 x86_64 shell:

```bash
pacman -S mingw-w64-x86_64-qemu 
```

## 2. Check ARM64 UEFI Firmware
QEMU needs UEFI firmware for ARM64. Check if firmware exists in MSYS2
```bash
ls /mingw64/share/qemu/edk2-aarch64-code.fd
```

## 3. Download Windows 11 ARM64 ISO
Download from https://www.microsoft.com/en-us/software-download/windows11arm64

Go to https://schneegans.de/windows/unattend-generator/ and generate an autounattend.xml wrappen in a ISO file named `unattend.iso`.
Make sure to select *Windows on Arm64* and check the checkbox *Bypass Windows 11 requirements check (TPM, Secure Boot, etc.)*

## 4. Choose directory for VM files
```bash
mkdir -p /c/qemu/win-arm64
cd /c/qemu/win-arm64
```

## 5. Create Virtual Disk

```bash
qemu-img create -f qcow2 win-arm64.qcow2 64G
```

## 6. Create VARS file for secure boot

```bash
cp /mingw64/share/qemu/edk2-arm-vars.fd ./edk2-arm-vars.fd
```

## 7. Start QEMU - First Boot (Installation)

```bash
qemu-system-aarch64 \
  -M virt \
  -cpu max,pauth-impdef=on \
  -smp 6 \
  -m 8G \
  -drive if=pflash,format=raw,readonly=on,file=/mingw64/share/qemu/edk2-aarch64-code.fd \
  -drive if=pflash,format=raw,file=$(pwd)/edk2-arm-vars.fd \
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
  -drive if=none,id=unattend,file=$(pwd)/unattend.iso,media=cdrom \
  -device usb-storage,drive=unattend \
  -display gtk
```



## 8. Start QEMU - Normal Boot (After Installation)

After Windows is installed, boot without the ISO:

