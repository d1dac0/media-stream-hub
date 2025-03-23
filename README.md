# Media Streamer

A secure web-based media streaming platform that allows users to stream both video and audio directly through their browser.

## Features

- **Automatic Media Indexing**: Automatically indexes a specified folder to display available media files for browsing and selection.
- **Playback Resume**: Remembers and resumes playback from the last watched position when a user revisits the site.
- **Responsive UI**: Provides a smooth and responsive user interface for optimal viewing and listening experience.
- **Format Support**: Supports common video formats (MP4, WebM, MKV, AVI, MOV) and audio formats (MP3, WAV, OGG, FLAC, AAC).
- **Media Filtering**: Filter media by type (video/audio) and search by filename.
- **Playback Controls**: Standard media controls including play/pause, previous/next, and volume adjustment.
- **Security Features**: User authentication, CSRF protection, path traversal prevention, rate limiting, and security headers.

## Installation

1. Clone this repository or download the source code.
2. Install the required dependencies:

```
pip install -r requirements.txt
```

## Configuration

The application can be configured using environment variables:

### Required Environment Variables for Production

- `SECRET_KEY`: A strong secret key for session management and CSRF protection
- `APP_USERNAME`: Username for accessing the application
- `APP_PASSWORD`: Password for accessing the application
- `DEBUG_MODE`: Set to 'False' in production

### Optional Environment Variables

- `MEDIA_FOLDER`: Path to your media files (default: 'media' folder in the project directory)

### Setting Environment Variables

#### Windows

```
set SECRET_KEY=your_secret_key_here
set APP_USERNAME=your_username
set APP_PASSWORD=your_secure_password
set DEBUG_MODE=False
set MEDIA_FOLDER=C:\path\to\your\media\folder
```

#### macOS/Linux

```
export SECRET_KEY=your_secret_key_here
export APP_USERNAME=your_username
export APP_PASSWORD=your_secure_password
export DEBUG_MODE=False
export MEDIA_FOLDER=/path/to/your/media/folder
```

## Security Features

This application includes several comprehensive security features:

1. **User Authentication**: 
   - Secure password hashing using bcrypt
   - Protection against brute force attacks with rate limiting
   - Client-side lockout after multiple failed attempts
   - Secure session management with HTTP-only cookies

2. **CSRF Protection**: 
   - Cross-Site Request Forgery protection on all forms and API endpoints
   - CSRF tokens included in all forms and AJAX requests
   - Validation of CSRF tokens on all state-changing operations

3. **Path Traversal Prevention**: 
   - Strict validation of file paths to prevent unauthorized access
   - Normalization of paths to prevent directory traversal attacks
   - Restriction of access to only allowed file types

4. **Rate Limiting**: 
   - Server-side rate limiting on login attempts and API endpoints
   - Client-side rate limiting to prevent UI abuse
   - Graduated response to repeated attacks

5. **Security Headers**: 
   - Content-Security-Policy to prevent XSS attacks
   - X-Content-Type-Options to prevent MIME type sniffing
   - X-Frame-Options to prevent clickjacking
   - Strict-Transport-Security (when HTTPS is enabled)
   - Cache-Control headers to prevent sensitive information disclosure

6. **Input Validation**: 
   - Server-side validation of all user inputs
   - Client-side validation for improved user experience
   - HTML escaping to prevent XSS attacks

7. **Secure File Operations**: 
   - Atomic file operations to prevent data corruption
   - Proper file permissions to prevent unauthorized access
   - Cache-busting for media files to prevent caching attacks

8. **Secure Logging**:
   - Structured logging with rotation to manage log file sizes
   - No sensitive information logged (passwords, tokens, etc.)
   - Detailed error logging for troubleshooting without exposing internals

9. **Clickjacking Protection**:
   - Frame-busting code to prevent the application from being embedded in iframes
   - X-Frame-Options header to enforce browser-level protection

10. **Secure Configuration**:
    - Environment variables for sensitive configurations
    - Random generation of credentials if not provided
    - Warnings for insecure configurations

## Production Deployment Recommendations

For production use, consider the following additional security measures:

1. **Use HTTPS**: Configure a proper SSL/TLS certificate and enable the HSTS header
2. **Reverse Proxy**: Use Nginx or Apache as a reverse proxy with additional security configurations
3. **Stronger Authentication**: Implement multi-factor authentication for additional security
4. **Database Backend**: Store user data and playback state in a proper database with encrypted connections
5. **Regular Updates**: Keep all dependencies updated to patch security vulnerabilities
6. **Security Monitoring**: Implement logging and monitoring for suspicious activities
7. **Backup Strategy**: Regularly backup your data and test restoration procedures
8. **Security Audits**: Conduct regular security audits and penetration testing

## Security Best Practices for Users

1. **Strong Passwords**: Use a strong, unique password for accessing the application
2. **Secure Network**: Only run the application on trusted networks
3. **Keep Updated**: Regularly update the application and its dependencies
4. **Access Control**: Restrict physical and network access to the server
5. **Regular Audits**: Periodically review access logs for suspicious activity

## Network Access

To access the application from other devices on your local network:

1. Run the application on your computer
2. Find your computer's local IP address (use `ipconfig` on Windows or `ifconfig` on macOS/Linux)
3. On other devices, open a web browser and navigate to `http://YOUR_IP_ADDRESS:5000`
4. Enter the username and password you configured

## Usage

1. Start the application:

```
python app.py
```

2. Open your web browser and navigate to:

```
http://localhost:5000
```

3. Log in with your configured username and password.
4. Browse and play your media files directly in the browser.

## Adding Media Files

Simply place your media files in the configured media folder. The application will automatically detect and index them. You can organize your media files into subdirectories, and the application will preserve this structure in the UI.

## Supported File Formats

### Video
- MP4 (.mp4)
- WebM (.webm)
- Matroska (.mkv)
- AVI (.avi)
- QuickTime (.mov)

### Audio
- MP3 (.mp3)
- WAV (.wav)
- Ogg Vorbis (.ogg)
- FLAC (.flac)
- AAC (.aac)

## Browser Compatibility

This application works best with modern browsers that support HTML5 video and audio playback:
- Google Chrome
- Mozilla Firefox
- Microsoft Edge
- Safari

## Troubleshooting

If you encounter issues with media playback, ensure that:
1. Your browser supports the media format you're trying to play.
2. You have the necessary codecs installed for your browser.
3. The media files are not corrupted.

If you're having trouble accessing the application from other devices:
1. Check that your firewall allows connections to port 5000
2. Verify that all devices are on the same network
3. Ensure the application is running with `host='0.0.0.0'` to listen on all interfaces
