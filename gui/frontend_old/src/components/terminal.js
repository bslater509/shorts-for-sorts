import { parseAnsiColors } from '../utils.js';

export function appendConsoleLog(text, className = '') {
  const consoleBody = document.getElementById('compiler-console');
  if (!consoleBody) return;
  
  const formatted = parseAnsiColors(text);
  
  if (className === 'system') {
    const line = document.createElement('div');
    line.className = 'terminal-line system-line';
    line.innerHTML = formatted;
    consoleBody.appendChild(line);
  } else {
    const span = document.createElement('span');
    span.innerHTML = formatted;
    consoleBody.appendChild(span);
  }
  
  consoleBody.scrollTop = consoleBody.scrollHeight;
}

export function clearConsole() {
  const consoleBody = document.getElementById('compiler-console');
  if (consoleBody) {
    consoleBody.innerHTML = '';
  }
}

window.clearConsole = clearConsole;
