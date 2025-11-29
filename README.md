# Moshi Connect

Windows GUI for OpenConnect VPN connections with SAML/SSO authentication and split tunneling support.

## How to install

- Optional: install OpenVPN to get the Win TAP driver
- Run the installer

## Setup shortcut
1. Browse to %AppData%\Microsoft\Windows\Start Menu
1. Right-click and select New > Shortcut
1. For the location, enter:
    ```
    C:\git\openconnect-sso-gui\.venv\Scripts\pythonw.exe src\main.py --start-service
    ```
1. Start in: `C:\git\openconnect-sso-gui`
1. Name the shortcut "Moshi Connect"
1. Right-click on the shortcut > Properties > Shortcut > Advanced > Run as administrator
1. Right-click on the shortcut > Properties > Shortcut > Change Icon > Browse > select `images/moshi-connect.ico`
1. Right-click on the shortcut > Pin to Start

## Installation

```bash
python -m venv .venv
source .venv/bin/activate 
pip install -e .[dev]
```

## Usage

```bash
python src/main.py
```

Features:
- GUI for VPN profile management
- Automated SSO authentication via Firefox
- Split tunneling configuration
- System tray integration

## Development

Run tests:
```bash
pytest
```

Run typ checks:
```bash
mypy src
```

Code formatting:
```bash
black src/ tests/
```