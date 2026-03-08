# VoxelCraft Desktop Application

Desktop application for 3D model generation from images using AI.

## Features

- **Multiple Authentication Options**
  - Device fingerprint login (hardware-bound)
  - Google OAuth
  - GitHub OAuth

- **Multiple 3D Generation Models**
  - TripoSR (Local inference)
  - Tripo3D (Cloud API)
  - Meshy AI (Cloud API)
  - Neural4D (Cloud API)
  - HItem3D (Cloud API)

- **Output Formats**
  - OBJ
  - STL
  - GLB

- **Modern UI**
  - Dark theme matching the web app
  - Drag & drop image upload
  - Real-time progress tracking
  - Activity log

## Installation

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/VoxelCraft-desktop.git
   cd VoxelCraft-desktop
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/macOS
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment:
   ```bash
   copy .env.example .env
   # Edit .env with your Supabase credentials
   ```

5. Run the application:
   ```bash
   python main.py
   ```

## Building Executable

### Using PyInstaller

```bash
pip install pyinstaller

pyinstaller --onefile --windowed \
  --name "VoxelCraft" \
  --icon "assets/logo/logo.ico" \
  --add-data "ui/styles;ui/styles" \
  --add-data "assets;assets" \
  main.py
```

The executable will be created in the `dist/` directory.

## Configuration

### Supabase Setup

1. Create a Supabase project at https://supabase.com
2. Enable Google and GitHub OAuth in Authentication > Providers
3. Add your redirect URLs:
   - For development: `http://localhost:8000/auth/callback`
   - For desktop: `VoxelCraft://auth/callback`
4. Copy your project URL and anon key to `.env`

### Database Tables

The application expects the following Supabase tables:

- `registered_devices` - Device fingerprint storage
- `user_credits` - Credit balance tracking
- `credit_ledger` - Credit transaction history
- `usage_logs` - Generation history

## Project Structure

```
VoxelCraft_desktop_app/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
├── README.md              # This file
├── core/                  # Core modules
│   ├── __init__.py
│   ├── device_fingerprint.py  # Hardware binding
│   ├── session_manager.py     # Auth session handling
│   └── supabase_client.py     # Database connection
├── ui/                    # User interface
│   ├── __init__.py
│   ├── main_window.py     # Main application window
│   ├── auth_dialog.py     # Login dialog
│   └── styles/
│       └── styles.qss     # Qt stylesheet
└── assets/                # Resources
    └── logo/
        ├── logo.ico       # Windows icon
        └── logo.png       # App logo
```

## Authentication Flow

### Device Fingerprint Login
1. App generates unique hardware fingerprint
2. Sends fingerprint to Supabase for validation
3. If registered, creates session with user's credits
4. If not registered, prompts for registration

### OAuth Login (Google/GitHub)
1. Opens browser to OAuth provider
2. User authenticates with provider
3. Provider redirects to callback URL with tokens
4. App exchanges tokens for session
5. Device fingerprint linked to user account

## Credits System

- Each 3D generation costs 1 credit
- New devices get 1 free trial generation
- Credits can be purchased through the web app
- Credit balance synced with Supabase

## Development

### Running in Development Mode

```bash
python main.py
```

### Debugging

Set environment variable for verbose logging:
```bash
set DEBUG=1
python main.py
```

## License

MIT License - See LICENSE file for details.

## Support

For issues and feature requests, please open an issue on GitHub.