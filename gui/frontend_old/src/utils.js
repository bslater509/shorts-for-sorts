export function debounce(fn, delay = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

export function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

export function getBaseName(path) {
  if (!path) return '';
  if (path === 'random') return 'Random Selection';
  return path.split(/[\\/]/).pop();
}

export function countWords(text) {
  const trimmed = (text || '').trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

export function parseAnsiColors(text) {
  if (!text) return '';
  
  let clean = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
      
  const rawAnsiMap = [
      { regex: /\u001b\[31m/g, style: 'color: #ff5f56; font-weight: bold;' },
      { regex: /\u001b\[32m/g, style: 'color: #27c93f; font-weight: bold;' },
      { regex: /\u001b\[33m/g, style: 'color: #ffbd2e; font-weight: bold;' },
      { regex: /\u001b\[34m/g, style: 'color: #54a3ff; font-weight: bold;' },
      { regex: /\u001b\[35m/g, style: 'color: #ff007f; font-weight: bold;' },
      { regex: /\u001b\[36m/g, style: 'color: #3B82F6; font-weight: bold;' },
      { regex: /\u001b\[1m/g, style: 'font-weight: bold;' },
      { regex: /\u001b\[0m/g, style: 'reset' },
      
      { regex: /\[31m/g, style: 'color: #ff5f56; font-weight: bold;' },
      { regex: /\[32m/g, style: 'color: #27c93f; font-weight: bold;' },
      { regex: /\[33m/g, style: 'color: #ffbd2e; font-weight: bold;' },
      { regex: /\[34m/g, style: 'color: #54a3ff; font-weight: bold;' },
      { regex: /\[35m/g, style: 'color: #ff007f; font-weight: bold;' },
      { regex: /\[36m/g, style: 'color: #3B82F6; font-weight: bold;' },
      { regex: /\[1m/g, style: 'font-weight: bold;' },
      { regex: /\[0m/g, style: 'reset' }
  ];
  
  let html = clean;
  let openSpansCount = 0;
  
  rawAnsiMap.forEach(item => {
      html = html.replace(item.regex, () => {
          if (item.style === 'reset') {
              let res = '';
              while (openSpansCount > 0) {
                  res += '</span>';
                  openSpansCount--;
              }
              return res;
          } else {
              openSpansCount++;
              return `<span style="${item.style}">`;
          }
      });
  });
  
  while (openSpansCount > 0) {
      html += '</span>';
      openSpansCount--;
  }
  
  return html;
}
