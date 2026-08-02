const fs = require('fs')
let content = fs.readFileSync('gui/frontend/src/components/batch/BatchHeader.jsx', 'utf8')

// Replace `const AdvancedSettingsContent = () => {` with `const renderAdvancedSettings = () => {`
content = content.replace('const AdvancedSettingsContent = () => {', 'const renderAdvancedSettings = () => {')

// Replace the `<AdvancedSettingsContent />` usages with `{renderAdvancedSettings()}`
content = content.replace(/<AdvancedSettingsContent \/>/g, '{renderAdvancedSettings()}')

// Safe cast for values
content = content.replace(
  /<Select value={batch\.layout}/g,
  '<Select value={String(batch.layout)}'
)
content = content.replace(
  /<Select value={batch\.voiceId}/g,
  '<Select value={String(batch.voiceId)}'
)
content = content.replace(
  /<Select value={batch\.subAnimationStyle}/g,
  '<Select value={String(batch.subAnimationStyle)}'
)
content = content.replace(
  /<Select value={batch\.wordsPerScreen}/g,
  '<Select value={String(batch.wordsPerScreen)}'
)
content = content.replace(
  /<Select value={currentMusicValue}/g,
  '<Select value={String(currentMusicValue)}'
)

// Safe replace for bgMusicPath
content = content.replace(
  /batch\.bgMusicPath\.replace\(\/\^music\\\/\\\/, ''\)/g,
  "String(batch.bgMusicPath).replace(/^music\\//, '')"
)

// For the hint, it also uses replace
content = content.replace(
  /batch\.bgMusicPath\.replace\(\/\^music\\\/\\\/, ''\)/g,
  "String(batch.bgMusicPath).replace(/^music\\//, '')"
)

// Also fix the prompt selector to just be a function
content = content.replace('const PromptSelectorContent = () => (', 'const renderPromptSelector = () => (')
content = content.replace(/<PromptSelectorContent \/>/g, '{renderPromptSelector()}')

fs.writeFileSync('gui/frontend/src/components/batch/BatchHeader.jsx', content)
console.log('Fixed!')
