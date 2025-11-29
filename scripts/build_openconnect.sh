#!/bin/bash
#
# Simplified OpenConnect build script for Windows
# Based on openconnect-gui approach
#

set -e  # Exit on any error

echo "Building OpenConnect for Windows x64..."

# Check if we're in the right directory
if [ ! -f "configure.ac" ]; then
    echo "Error: This script must be run from the OpenConnect source directory"
    exit 1
fi

# Set install prefix
INSTALL_PREFIX="$(pwd)/install"
echo "Install prefix: $INSTALL_PREFIX"

# Clean previous build
echo "Cleaning previous build..."
make clean 2>/dev/null || true
rm -rf "$INSTALL_PREFIX"
mkdir -p "$INSTALL_PREFIX"


# Generate configure script if needed
if [ ! -f "configure" ]; then
    echo "Generating configure script..."
    autoreconf -fiv
fi

# Configure with minimal options (based on openconnect-gui approach)
echo "Configuring..."
./configure \
    --prefix="$INSTALL_PREFIX" \
    --with-gnutls \
    --without-openssl \
    --without-libpskc \
    --without-libproxy \
    --disable-nls \
    --with-vpnc-script=vpnc-script-win.js

# Build and install
echo "Building..."
make -j$(nproc)

echo "Installing..."
make install

# Create flat directory structure for Windows
echo "Creating flat directory structure..."
FLAT_DIR="$INSTALL_PREFIX/flat"
mkdir -p "$FLAT_DIR"

# Copy the main executable
if [ -f "$INSTALL_PREFIX/sbin/openconnect.exe" ]; then
    cp "$INSTALL_PREFIX/sbin/openconnect.exe" "$FLAT_DIR/"
    echo "Copied openconnect.exe"
elif [ -f "$INSTALL_PREFIX/bin/openconnect.exe" ]; then
    cp "$INSTALL_PREFIX/bin/openconnect.exe" "$FLAT_DIR/"
    echo "Copied openconnect.exe"
else
    echo "Error: openconnect.exe not found!"
    exit 1
fi

# Copy the OpenConnect library
if [ -f "$INSTALL_PREFIX/bin/libopenconnect-5.dll" ]; then
    cp "$INSTALL_PREFIX/bin/libopenconnect-5.dll" "$FLAT_DIR/"
    echo "Copied libopenconnect-5.dll"
fi

# List of required DLLs from MINGW64
REQUIRED_DLLS=(
    "libxml2-16.dll"
    "libgnutls-30.dll"
    "libnettle-8.dll"
    "libhogweed-6.dll"
    "libgmp-10.dll"
    "libtasn1-6.dll"
    "libidn2-0.dll"
    "libunistring-5.dll"
    "zlib1.dll"
    "libintl-8.dll"
    "libiconv-2.dll"
    "libwinpthread-1.dll"
    "libgcc_s_seh-1.dll"
    "libstdc++-6.dll"
    "libp11-kit-0.dll"
    "libffi-8.dll"
    "libbrotlienc.dll"
    "libbrotlidec.dll"
    "libbrotlicommon.dll"
    "liblz4.dll"
    "libzstd.dll"
    "liblzma-5.dll"
)

echo "Copying required DLLs to flat directory..."
for dll in "${REQUIRED_DLLS[@]}"; do
    if [ -f "/mingw64/bin/$dll" ]; then
        cp "/mingw64/bin/$dll" "$FLAT_DIR/"
        echo "Copied $dll"
    else
        echo "Warning: $dll not found in /mingw64/bin/"
    fi
done


echo "Build completed successfully!"
echo "Flat directory created at: $FLAT_DIR"
echo "Contents:"
ls -la "$FLAT_DIR"
