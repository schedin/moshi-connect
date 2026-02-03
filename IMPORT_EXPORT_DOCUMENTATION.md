# Settings Import/Export Feature Documentation

## Overview
This feature adds the ability to export and import VPN profiles and application settings via YAML format.

## UI Changes

### Main Window - New Buttons
Two new buttons have been added to the profile management section:
- **Export Settings...** - Opens the export dialog
- **Import Settings...** - Opens the import dialog

These buttons are positioned below the existing profile management buttons (Add/Edit/Delete Profile).

## Export Dialog

### Layout
```
┌─────────────────────────────────────────────────────────┐
│ Export Settings                                    [X]  │
├─────────────────────────────────────────────────────────┤
│ Copy the YAML settings below or save them to a file:   │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐│
│ │profiles:                                            ││
│ │  Company VPN:                                       ││
│ │    name: Company VPN                                ││
│ │    routes:                                          ││
│ │    - 10.0.0.0/8                                     ││
│ │    - 172.16.0.0/12                                  ││
│ │    url: https://vpn.company.com                     ││
│ │  Dev Environment:                                   ││
│ │    name: Dev Environment                            ││
│ │    routes:                                          ││
│ │    - 192.168.100.0/24                               ││
│ │    url: https://dev.vpn.company.com                 ││
│ │settings:                                            ││
│ │  last_selected_profile: Company VPN                 ││
│ └─────────────────────────────────────────────────────┘│
│                                                         │
│  [Copy to Clipboard] [Save to File...]        [Close]  │
└─────────────────────────────────────────────────────────┘
```

### Features
1. **Text Area**: Displays the YAML content in a monospace font (Courier New)
2. **Copy to Clipboard**: Copies the entire YAML content to the clipboard for easy pasting
3. **Save to File**: Opens a file save dialog to save the YAML to disk (defaults to "moshi-connect-settings.yaml")
4. **Close**: Closes the dialog

## Import Dialog

### Layout - Tab 1: From File
```
┌─────────────────────────────────────────────────────────┐
│ Import Settings                                    [X]  │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────┬─────────────────────────────────┐  │
│ │  From File      │ From Text                       │  │
│ └─────────────────┴─────────────────────────────────┘  │
│                                                         │
│ Select a YAML file to import settings:                 │
│                                                         │
│ [Select File...]                                        │
│                                                         │
│ No file selected                                        │
│                                                         │
│                                                         │
│                                                         │
│                                                         │
│  [Import]                                     [Cancel]  │
└─────────────────────────────────────────────────────────┘
```

### Layout - Tab 2: From Text
```
┌─────────────────────────────────────────────────────────┐
│ Import Settings                                    [X]  │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────┬─────────────────────────────────┐  │
│ │  From File      │ From Text                       │  │
│ └─────────────────┴─────────────────────────────────┘  │
│                                                         │
│ Paste YAML settings below:                             │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐│
│ │                                                     ││
│ │ Paste YAML settings here...                        ││
│ │                                                     ││
│ │                                                     ││
│ │                                                     ││
│ │                                                     ││
│ └─────────────────────────────────────────────────────┘│
│                                                         │
│  [Import]                                     [Cancel]  │
└─────────────────────────────────────────────────────────┘
```

### Features
1. **Tab Widget**: Two tabs for different import methods
   - **From File**: Select a YAML file from disk
   - **From Text**: Paste YAML content directly
2. **From File Tab**:
   - Select File button opens a file picker dialog
   - Shows selected file path
3. **From Text Tab**:
   - Large text area for pasting YAML content
   - Monospace font for better readability
4. **Import Button**: Processes the import with confirmation dialog
5. **Cancel Button**: Closes the dialog without importing

### Confirmation Dialog
Before importing, a confirmation dialog appears:
```
┌─────────────────────────────────────────┐
│ Confirm Import                     [X]  │
├─────────────────────────────────────────┤
│ This will replace your current          │
│ settings and profiles. Continue?        │
│                                         │
│               [Yes]      [No]           │
└─────────────────────────────────────────┘
```

## YAML Format

The exported YAML has the following structure:

```yaml
profiles:
  <profile_name>:
    name: <profile_name>
    url: <vpn_url>
    routes:
      - <route_cidr_1>
      - <route_cidr_2>
settings:
  <setting_key>: <setting_value>
```

### Example
```yaml
profiles:
  Company VPN:
    name: Company VPN
    routes:
      - 10.0.0.0/8
      - 172.16.0.0/12
    url: https://vpn.company.com
  Dev Environment:
    name: Dev Environment
    routes:
      - 192.168.100.0/24
    url: https://dev.vpn.company.com
settings:
  last_selected_profile: Company VPN
  window_height: 600
  window_width: 800
```

## Error Handling

The import/export dialogs include comprehensive error handling:

1. **Export Errors**:
   - Failed to load settings → Error dialog shown
   - Failed to copy to clipboard → Error dialog shown
   - Failed to save file → Error dialog shown

2. **Import Errors**:
   - No file selected → Warning dialog
   - No text pasted → Warning dialog
   - Invalid YAML format → Error dialog with details
   - Failed to parse data → Error dialog with details
   - User cancels confirmation → Import cancelled

## Usage Workflow

### Exporting Settings
1. Click "Export Settings..." button
2. Review the YAML content in the dialog
3. Either:
   - Click "Copy to Clipboard" to copy for pasting elsewhere
   - Click "Save to File..." to save to disk
4. Click "Close" when done

### Importing Settings
1. Click "Import Settings..." button
2. Choose import method:
   - **From File**: Click "Select File...", choose a YAML file
   - **From Text**: Switch to "From Text" tab, paste YAML content
3. Click "Import"
4. Confirm the import in the confirmation dialog
5. Settings are imported and the profile list is updated

## Testing

Unit tests have been added in `tests/test_settings_import_export.py` to verify:
- Export data structure is correct
- YAML serialization works properly
- Import from YAML works correctly
- Multiple profiles can be imported
- Empty routes are handled correctly
- Invalid YAML is rejected with proper errors

All tests pass successfully.
