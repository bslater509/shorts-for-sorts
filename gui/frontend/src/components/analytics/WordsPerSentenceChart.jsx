import { useMemo } from 'react'
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'

const VOICE_COLORS = [
  '#8b5cf6', '#06b6d4', '#f59e0b', '#10b981',
  '#ef4444', '#ec4899', '#f97316', '#14b8a6',
  '#6366f1', '#d946ef',
]

const VOICE_NAMES = {
  '21m00Tcm4TlvDq8ikWAM': 'Rachel',
  'AZnzlk1XvdvUeBnXmlld': 'Domi',
  'EXAVITQu4vrCxn2k5eS': 'Bella',
  'ErXwobaYiN019PkySvj': 'Antoni',
  'MF3mGyEYCl7XYWbV9V6w': 'Elli',
  'TxGEqnHWrfWFTfGW9Xj': 'Josh',
  'VR6AewLTigWG4xSOGB': 'Arnold',
  'W7Kpb6O9M2Zq3Gx7Pz': 'Emily',
  'XU6kD4G6lVX7zQg9sF': 'Liam',
  'ZQe5CZ4zR8r0Gk6yLm': 'Olivia',
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const entry = payload[0]
  const data = entry.payload
  return (
    <div className="bg-card/90 backdrop-blur-md border border-border/60 rounded-lg px-3.5 py-2.5 shadow-xl text-sm min-w-[160px]">
      <p className="font-semibold text-foreground mb-1.5 text-xs uppercase tracking-wide">Sentence Details</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-xs text-muted-foreground">Word Count</span>
          <span className="text-xs font-medium text-foreground">{data.wordCount}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-xs text-muted-foreground">Sentence Count</span>
          <span className="text-xs font-medium text-foreground">{data.sentenceCount}</span>
        </div>
        {data.wordCount > 0 && data.sentenceCount > 0 && (
          <div className="flex justify-between gap-4">
            <span className="text-xs text-muted-foreground">Words/Sentence</span>
            <span className="text-xs font-medium text-foreground">{(data.wordCount / data.sentenceCount).toFixed(1)}</span>
          </div>
        )}
        <div className="flex justify-between gap-4">
          <span className="text-xs text-muted-foreground">Voice</span>
          <span className="text-xs font-medium text-foreground font-mono">{data.voiceName || data.voice || '—'}</span>
        </div>
      </div>
    </div>
  )
}

const WordsPerSentenceChart = ({ perJobStats = [] }) => {
  const scatterData = useMemo(() => {
    const uniqueVoices = []
    const seen = new Set()

    return perJobStats
      .filter(job => (job.word_count || 0) > 0 && (job.sentence_count || 0) > 0)
      .map((job) => {
        const voice = job.voice_id || 'Unknown'

        if (!seen.has(voice)) {
          seen.add(voice)
          uniqueVoices.push(voice)
        }

        return {
          wordCount: job.word_count || 0,
          sentenceCount: job.sentence_count || 0,
          voice,
          voiceName: VOICE_NAMES[voice] || voice,
          voiceColorIdx: uniqueVoices.indexOf(voice),
        }
      })
  }, [perJobStats])

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-2">Words vs Sentences</h2>
      <p className="text-xs text-muted-foreground mb-4">
        How word count relates to sentence count — tighter clusters mean more consistent sentence length
      </p>
      {scatterData.length > 0 ? (
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart
              margin={{ top: 10, right: 20, left: 10, bottom: 20 }}
            >
              <defs>
                {VOICE_COLORS.map((color, idx) => (
                  <radialGradient key={idx} id={`wsGlow${idx}`} cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor={color} stopOpacity={0.4} />
                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                  </radialGradient>
                ))}
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                opacity={0.25}
              />
              <XAxis
                dataKey="wordCount"
                name="Word Count"
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                label={{
                  value: 'Word Count',
                  position: 'insideBottom',
                  offset: -10,
                  style: { fontSize: 11, fill: 'hsl(var(--muted-foreground))' },
                }}
                axisLine={{ stroke: 'hsl(var(--border))', opacity: 0.3 }}
                tickLine={false}
              />
              <YAxis
                dataKey="sentenceCount"
                name="Sentence Count"
                tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                label={{
                  value: 'Sentence Count',
                  angle: -90,
                  position: 'insideLeft',
                  style: { fontSize: 11, fill: 'hsl(var(--muted-foreground))' },
                }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{
                  stroke: 'hsl(var(--muted-foreground))',
                  strokeDasharray: '3 3',
                  strokeOpacity: 0.3,
                }}
              />
              <Scatter
                data={scatterData}
                shape={(props) => {
                  const { cx, cy, payload } = props
                  const color = VOICE_COLORS[payload.voiceColorIdx % VOICE_COLORS.length]
                  return (
                    <g>
                      {/* Glow ring */}
                      <circle
                        cx={cx}
                        cy={cy}
                        r={10}
                        fill={`url(#wsGlow${payload.voiceColorIdx % VOICE_COLORS.length})`}
                        style={{ pointerEvents: 'none' }}
                      />
                      {/* Dot */}
                      <circle
                        cx={cx}
                        cy={cy}
                        r={6}
                        fill={color}
                        stroke="hsl(var(--background))"
                        strokeWidth={1.5}
                        style={{
                          filter: 'drop-shadow(0 0 4px rgba(139, 92, 246, 0.25))',
                          transition: 'all 0.2s ease-out',
                          cursor: 'pointer',
                        }}
                        onMouseEnter={(e) => {
                          e.target.setAttribute('r', '9')
                          e.target.style.filter = `drop-shadow(0 0 8px ${color}66)`
                        }}
                        onMouseLeave={(e) => {
                          e.target.setAttribute('r', '6')
                          e.target.style.filter = 'drop-shadow(0 0 4px rgba(139, 92, 246, 0.25))'
                        }}
                      />
                    </g>
                  )
                }}
              />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-80 flex items-center justify-center text-sm text-muted-foreground">
          <div className="text-center space-y-2">
            <p>Not enough data to analyze words vs sentences.</p>
            <p className="text-xs opacity-60">Run jobs with text content to populate this chart.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default WordsPerSentenceChart
