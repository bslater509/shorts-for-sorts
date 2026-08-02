const fs = require('fs')
let content = fs.readFileSync('gui/frontend/src/components/batch/BatchHeader.jsx', 'utf8')

content = content.replace('const EmojiSettingsContent = () => (', 'const renderEmojiSettings = () => (')
content = content.replace(/<EmojiSettingsContent \/>/g, '{renderEmojiSettings()}')

fs.writeFileSync('gui/frontend/src/components/batch/BatchHeader.jsx', content)
console.log('Fixed emoji!')
