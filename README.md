# Moshi Connect

GUI for OpenConnect VPN connections with SAML/SSO authentication and split tunneling support.

Features:
- GUI for VPN profile management
- Automated SSO authentication via Firefox
- Split tunneling configuration

## Installation

- Optional: install OpenVPN to get the Win TAP driver (typically not needed).
- Run the installer

## Development

```bash
python -m venv .venv
source .venv/bin/activate 
pip install -e .[dev]
```

### Developer start 
To start the GUI and service in the same process:

```bash
python src/main.py --start-service
```

### Developer shortcut
1. Browse to `%AppData%\Microsoft\Windows\Start Menu`
1. Right-click and select New > Shortcut
1. For the location, enter:
    ```
    C:\git\moshi-connect\.venv\Scripts\pythonw.exe src\main.py --start-service
    ```
1. Start in: `C:\git\moshi-connect`
1. Name the shortcut "Moshi Connect"
1. Right-click on the shortcut > Properties > Shortcut > Advanced > Run as administrator
1. Right-click on the shortcut > Properties > Shortcut > Change Icon > Browse > select `images/moshi-connect.ico`
1. Right-click on the shortcut > Pin to Start

