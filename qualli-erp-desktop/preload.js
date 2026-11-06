// Sichere IPC-Brücke zwischen Oberfläche und Electron-Hauptprozess.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('erp', {
  isDesktop: true,
  getInfo: () => ipcRenderer.invoke('erp:info'),
  getBackendLog: () => ipcRenderer.invoke('erp:backend-log'),
  restartBackend: () => ipcRenderer.invoke('erp:restart-backend'),
});
