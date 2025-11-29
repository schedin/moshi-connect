#!/bin/bash
#
# Install OpenConnect build dependencies for MSYS2/MINGW64
#
# This script installs all necessary packages to build OpenConnect
# for Windows x64 using the MINGW64 toolchain.
#

set -e  # Exit on any error

echo "Installing OpenConnect build dependencies for MINGW64..."

# Update package database
echo "Updating package database..."
pacman -Sy --noconfirm

# Install base development tools
echo "Installing base development tools..."
pacman -S --noconfirm \
    git \
    mingw-w64-x86_64-gcc \
    mingw-w64-x86_64-pkgconf \
    mingw-w64-x86_64-jq \
    autoconf \
    automake \
    libtool \
    make

# Install OpenConnect dependencies (using GnuTLS)
echo "Installing OpenConnect dependencies..."
pacman -S --noconfirm \
    mingw-w64-x86_64-libxml2 \
    mingw-w64-x86_64-gnutls \
    mingw-w64-x86_64-zlib \
    mingw-w64-x86_64-lz4

echo "All dependencies installed successfully!"
echo "MINGW64 toolchain is ready for building OpenConnect."
