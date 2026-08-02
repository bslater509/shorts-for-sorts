const fs = require('fs')
let content = fs.readFileSync('gui/frontend/src/components/batch/BatchHeader.jsx', 'utf8')

const oldZustand = `  const batch = useAppStore((s) => ({
    layout: s.appState?.batch_layout ?? 'Random',
    voiceId: s.appState?.batch_voice_id ?? 'Random',
    subAnimationStyle: s.appState?.batch_sub_animation_style ?? 'Random',
    wordsPerScreen: s.appState?.batch_words_per_screen ?? 'Default',
    singleWordMode: s.appState?.batch_single_word_mode ?? false,
    bgMusicPath: s.appState?.batch_bg_music_path ?? 'Random',
    scriptTemp: s.appState?.batch_script_temp ?? s.settings?.llm_temp_script ?? 0.7,
    metaTemp: s.appState?.batch_meta_temp ?? s.settings?.llm_temp_metadata ?? 0.7,
    maxWorkers: s.appState?.batch_max_workers ?? s.settings?.max_workers ?? 1,
    llmMaxWorkers: s.appState?.batch_llm_max_workers ?? s.settings?.llm_max_workers ?? 5,
  }))`

const newZustand = `  const batchLayout = useAppStore((s) => s.appState?.batch_layout ?? 'Random')
  const batchVoiceId = useAppStore((s) => s.appState?.batch_voice_id ?? 'Random')
  const batchSubAnimationStyle = useAppStore((s) => s.appState?.batch_sub_animation_style ?? 'Random')
  const batchWordsPerScreen = useAppStore((s) => s.appState?.batch_words_per_screen ?? 'Default')
  const batchSingleWordMode = useAppStore((s) => s.appState?.batch_single_word_mode ?? false)
  const batchBgMusicPath = useAppStore((s) => s.appState?.batch_bg_music_path ?? 'Random')
  const batchScriptTemp = useAppStore((s) => s.appState?.batch_script_temp ?? s.settings?.llm_temp_script ?? 0.7)
  const batchMetaTemp = useAppStore((s) => s.appState?.batch_meta_temp ?? s.settings?.llm_temp_metadata ?? 0.7)
  const batchMaxWorkers = useAppStore((s) => s.appState?.batch_max_workers ?? s.settings?.max_workers ?? 1)
  const batchLlmMaxWorkers = useAppStore((s) => s.appState?.batch_llm_max_workers ?? s.settings?.llm_max_workers ?? 5)

  const batch = {
    layout: batchLayout,
    voiceId: batchVoiceId,
    subAnimationStyle: batchSubAnimationStyle,
    wordsPerScreen: batchWordsPerScreen,
    singleWordMode: batchSingleWordMode,
    bgMusicPath: batchBgMusicPath,
    scriptTemp: batchScriptTemp,
    metaTemp: batchMetaTemp,
    maxWorkers: batchMaxWorkers,
    llmMaxWorkers: batchLlmMaxWorkers,
  }`

content = content.replace(oldZustand, newZustand)
fs.writeFileSync('gui/frontend/src/components/batch/BatchHeader.jsx', content)
console.log('Fixed zustand')
