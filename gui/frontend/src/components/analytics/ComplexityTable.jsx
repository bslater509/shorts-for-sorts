function formatDuration(seconds) {
  if (seconds == null || isNaN(seconds)) return '—'
  const totalSec = Math.round(seconds)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

const ComplexityTable = ({ complexityData }) => {
  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4">Content Complexity</h2>
      {complexityData.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">#</th>
                <th className="text-left py-2 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Word Count</th>
                <th className="text-left py-2 px-3 text-muted-foreground font-medium text-xs uppercase tracking-wider">Total Duration</th>
              </tr>
            </thead>
            <tbody>
              {complexityData.map((row) => (
                <tr key={row.index} className="border-b border-border/40 last:border-b-0 hover:bg-secondary/30 transition-colors">
                  <td className="py-2 px-3 font-mono text-xs">{row.index}</td>
                  <td className="py-2 px-3">{row.wordCount}</td>
                  <td className="py-2 px-3 font-mono">{formatDuration(row.totalDuration)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-32 flex items-center justify-center text-sm text-muted-foreground">
          No complexity data available.
        </div>
      )}
    </div>
  )
}

export default ComplexityTable
