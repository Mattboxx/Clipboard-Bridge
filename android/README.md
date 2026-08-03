# Clipboard Bridge for Android

The native Android client connects Android phones and tablets to the same Clipboard
Bridge server used by Windows, iPhone Shortcuts and the web interface.

**Current public build:** `1.0.0-beta.10`<br>
**Minimum Android version:** Android 10 (API 29)

[Download the signed universal APK](https://github.com/Mattboxx/Clipboard-Bridge/releases/download/2.0.6/Clipboard.Bridge.Android.universal.V1.0.0-beta.10.apk)

## Features

- Send and receive Unicode text.
- Send and receive images, PDFs and files of any type.
- Save received files under `Downloads/Clipboard Bridge`.
- Put received text and files into the Android clipboard.
- Live server history with up to 200 items.
- Restore a specific item from server history.
- Delete an individual server-history item after confirmation.
- Appear as a universal Android Share target for text and every file MIME type.
- Upload one or several files selected in another application.
- Keep files selected together as one server-history item and restore the complete group
  to the Android clipboard.
- **Send clipboard** and **Receive clipboard** Quick Settings tiles.
- Optional foreground monitoring for new server items.
- Configurable text, file and upload notifications.
- Shared API token and isolated account authentication.
- English and Italian interface.

## Install

1. Download `Clipboard.Bridge.Android.universal.V1.0.0-beta.10.apk`.
2. Open the APK from Android's browser or file manager.
3. If Android asks, allow that application to install unknown apps.
4. Select **Install**.
5. Open Clipboard Bridge.

The public APK is signed. Future APKs signed with the same project key can update the app
without deleting its configuration.

## Configure a server

Open the gear button and enter the server base URL:

```text
http://192.168.1.20:5088
```

Do not append `/clipboard` to the Android server address.

Token and account authentication are both optional. Select **Shared space** and leave
the token empty for an open general clipboard. In account mode Android places `user`
and `password` in plain text in every request URL; token-based Shortcut URLs similarly
expose `token`. Plain HTTP does not encrypt URL credentials, so use a trusted LAN,
private VPN or HTTPS reverse proxy.

### Shared space

Select **Shared space**. Leave the token empty when the server has no
`CLIPBOARD_TOKEN`; otherwise enter the configured token.

### Isolated account

Select **Account** only when the server administrator has configured that username in
`CLIPBOARD_ACCOUNTS` or `CLIPBOARD_ACCOUNTS_FILE`. Enter its username and password.
The app appends the credentials to every API URL as
`?user=USERNAME&password=PASSWORD`, which selects that account's isolated history.
It also sends the equivalent authentication headers for compatibility with newer
server deployments.

Use **Test connection**, save, and confirm that the status strip shows
**Connected - @USERNAME**. If it only shows **Connected**, the app is using the shared
space instead of an account.

## Server history

Android does not keep a separate history list. The screen retrieves live data from:

```text
GET http://SERVER_IP:5088/clipboard/history
```

The list refreshes every five seconds while the app is visible and is cleared when the
server is unavailable or the screen is left. If the Android list differs from the web
page, verify that both are using the same shared space or account.

For example, an account history request has this form:

```text
GET http://SERVER_IP:5088/clipboard/history?limit=200&user=alice&password=secret
```

Windows local history is private to the Windows app. Windows items become visible to
Android only after Windows uploads them through manual send or automatic synchronization.

## Send and receive

- **Send clipboard:** uploads the current clipboard to `POST /clipboard`.
- **Receive latest:** downloads `GET /clipboard/latest/raw`.
- **Send file:** selects a document with Android's system picker.
- **History row:** downloads that exact server item.
- **Trash button:** permanently deletes that item from the current server space after
  confirmation. Account credentials are applied to the delete request as well.
- **Share menu:** accepts text, images, documents and arbitrary file types shared from
  another Android application. `ACTION_SEND_MULTIPLE` selections are uploaded in order;
  each file remains available in server history and the last upload becomes the latest
  clipboard item.

The Share target uses a transparent upload activity. Clipboard Bridge reports the result
and closes immediately instead of opening and leaving the main application on screen.

The latest item is determined only by arrival order. Text, images and files have equal
priority.

## Quick Settings tiles

1. Pull down Quick Settings twice.
2. Open **Edit**.
3. Find **Send clipboard** and **Receive clipboard**.
4. Drag both into the active tile area.

Android requires a focused application for reliable clipboard reads and writes. The
tiles therefore use a transparent helper activity. It closes immediately after the
operation and does not open the main Clipboard Bridge interface.

## Automatic behavior and Android restrictions

Android 10 and newer block continuous background clipboard reads by ordinary apps.
Clipboard Bridge does not request Accessibility access or install a custom keyboard.

- Incoming monitoring uses a user-enabled foreground service.
- The service checks the server at the configured interval and shows notifications.
- The Receive tile provides reliable clipboard placement at any time.
- Outgoing automatic detection works while Clipboard Bridge is visible.
- The Share menu and Send tile are the reliable ways to send from other apps.

Some manufacturers stop foreground services aggressively. If monitoring stops:

1. allow Clipboard Bridge notifications;
2. disable battery optimization for Clipboard Bridge;
3. allow background activity in the manufacturer's battery settings;
4. open Clipboard Bridge again to restart monitoring.

## Files and photos

Received files are written through Android MediaStore to:

```text
Downloads/Clipboard Bridge
```

Clipboard Bridge stores a content URI in the Android clipboard. Applications that accept
file clipboard content can paste it directly; other applications may require the Android
Share menu or file picker.

## Build from source

Requirements:

- Android Studio with Android SDK 35;
- Java 17.

Open the `android` directory as an Android Studio project, or run:

```powershell
cd android
.\gradlew.bat test lint assembleDebug
```

The debug APK is generated under:

```text
app/build/outputs/apk/debug/
```

## Release signing

Copy the example:

```powershell
Copy-Item keystore.properties.example keystore.properties
```

Configure a private keystore, then run:

```powershell
.\gradlew.bat test lint assembleRelease
```

`keystore.properties`, `.jks`, `.keystore`, Gradle output and local SDK configuration are
ignored by Git. Never commit the release key or its passwords. Losing the key prevents
future APKs from updating existing installations.
