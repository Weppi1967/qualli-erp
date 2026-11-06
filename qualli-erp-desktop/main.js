// Qualli-ERP Desktop – Electron Hauptprozess.
// Startet bei Bedarf das Flask-Backend (python app.py) und beendet es beim Schließen.
const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');
const path = require('path');

const BACKEND_HOST = process.env.ERP_HOST || '127.0.0.1';
const BACKEND_PORT = Number(process.env.ERP_PORT || 5050);
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;
const DEV_URL = process.env.VITE_DEV_SERVER_URL;
const PROJECT_ROOT = path.resolve(__dirname, '..');

let backendProcess = null;
let backendManaged = false;
let backendLog = [];
let mainWindow = null;

function checkHealth(timeoutMs = 1500) {
  return new Promise((resolve) => {
    const req = http.get(`${BACKEND_URL}/api/health`, { timeout: timeoutMs }, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (c) => (body += c));
      res.on('end', () => {
        try {
          resolve(res.statusCode === 200 && JSON.parse(body).app === 'qualli-erp');
        } catch {
          resolve(false);
        }
      });
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

function pythonExecutable() {
  const candidates = [
    path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe'),
    path.join(PROJECT_ROOT, '.venv', 'bin', 'python'),
  ];
  return candidates.find((p) => fs.existsSync(p)) || (process.platform === 'win32' ? 'python' : 'python3');
}

async function startBackend() {
  if (await checkHealth()) {
    backendManaged = false;
    return true;
  }
  const python = pythonExecutable();
  backendLog = [];
  backendProcess = spawn(python, ['app.py'], {
    cwd: PROJECT_ROOT,
    env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
    windowsHide: true,
  });
  backendManaged = true;
  const capture = (chunk) => {
    backendLog.push(...chunk.toString().split(/\r?\n/).filter(Boolean));
    backendLog = backendLog.slice(-200);
  };
  backendProcess.stdout.on('data', capture);
  backendProcess.stderr.on('data', capture);
  backendProcess.on('exit', (code) => {
    backendLog.push(`Backend beendet (Code ${code})`);
    backendProcess = null;
  });

  for (let i = 0; i < 60; i += 1) {
    if (await checkHealth()) return true;
    if (!backendProcess) break;
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

function stopBackend() {
  if (backendProcess && backendManaged) {
    backendProcess.kill();
    backendProcess = null;
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 650,
    title: 'Qualli-ERP – Profilingbüro Glaser',
    backgroundColor: '#f4f6f9',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  const appUrl = DEV_URL || `${BACKEND_URL}/`;
  const allowedOrigins = [new URL(appUrl).origin, new URL(BACKEND_URL).origin];

  // Nur die eigene App im Fenster anzeigen, externe Links im Standard-Browser öffnen.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!allowedOrigins.includes(new URL(url).origin)) {
      event.preventDefault();
      if (/^https?:\/\//.test(url)) shell.openExternal(url);
    }
  });

  mainWindow.loadURL(appUrl);
}

ipcMain.handle('erp:info', async () => ({
  appVersion: app.getVersion(),
  electron: process.versions.electron,
  backendUrl: BACKEND_URL,
  backendManaged,
  backendOnline: await checkHealth(),
  projectRoot: PROJECT_ROOT,
}));

ipcMain.handle('erp:backend-log', () => backendLog.slice(-100));

ipcMain.handle('erp:restart-backend', async () => {
  stopBackend();
  await new Promise((r) => setTimeout(r, 500));
  return startBackend();
});

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    const ok = await startBackend();
    if (!ok) {
      dialog.showErrorBox(
        'Backend konnte nicht gestartet werden',
        `Das Qualli-ERP Backend unter ${BACKEND_URL} antwortet nicht.\n\n` +
          `Bitte setup.cmd im Ordner ${PROJECT_ROOT} ausführen.\n\nLetzte Meldungen:\n` +
          backendLog.slice(-15).join('\n'),
      );
    }
    createWindow();
  });

  app.on('window-all-closed', () => {
    stopBackend();
    app.quit();
  });
  app.on('before-quit', stopBackend);
}
