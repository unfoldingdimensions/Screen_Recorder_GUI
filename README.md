# Screen Recorder Application

A modern 1080P screen recording application with PyQt6 GUI, supporting full screen, window, and region recording with dual audio (system + microphone).

## Features

- **Recording Modes**: Full screen, window selection, or custom region
- **Audio Recording**: System audio and microphone with mixing
- **Video Quality**: Adjustable quality presets, 30/60 FPS, 1080P support
- **Controls**: Start/Stop, Pause/Resume, Timer with countdown
- **Output**: MP4 format with H.264 video and AAC audio

## Installation

### Prerequisites

1. **Python 3.10+** - Download from [python.org](https://www.python.org/downloads/)

2. **FFmpeg** - Required for video encoding
   - Download static build from [ffmpeg.org](https://ffmpeg.org/download.html)
   - Extract and add `ffmpeg.exe` to your PATH, or place it in the project directory
   - For Windows: Download from [www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/) or use chocolatey: `choco install ffmpeg`
   - **Important**: FFmpeg must be accessible from command line. Test with: `ffmpeg -version`

3. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   **Note**: `pyaudio` may require additional setup on Windows:
   - If installation fails, download the wheel from [here](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio)
   - Or use: `pip install pipwin && pipwin install pyaudio`

## Usage

### Running from Source

```bash
python main.py
```

### Building Executable

1. Ensure FFmpeg is accessible (in PATH or project directory)
2. Build with PyInstaller:
   ```bash
   pyinstaller build.spec
   ```
3. The executable will be in the `dist/` directory

## Configuration

Settings are saved automatically and include:
- Recording mode preference
- Quality settings (resolution, FPS, bitrate)
- Audio source selection
- Output directory

## System Requirements

- Windows 10/11
- Python 3.10+
- FFmpeg (bundled in .exe or system PATH)
- Audio drivers supporting WASAPI loopback (for system audio capture)

## Troubleshooting

### System Audio Not Capturing
- Ensure you're using Windows 10/11 with WASAPI support
- Some audio drivers may require elevated permissions
- System audio capture requires WASAPI loopback support
- Alternative: Use virtual audio cable software (e.g., VB-Audio Cable, OBS Virtual Audio Cable)
- Note: Audio encoding is currently simplified - full audio support may require additional FFmpeg configuration

### FFmpeg Not Found
- Ensure FFmpeg is in your system PATH, or
- Place `ffmpeg.exe` in the same directory as the application

### Performance Issues
- Lower FPS or quality settings
- Close unnecessary applications
- Use hardware acceleration if available (NVENC/QuickSync)

