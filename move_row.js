const fs = require('fs')
let content = fs.readFileSync('gui/frontend/src/components/batch/BatchHeader.jsx', 'utf8')

// Remove Row from inside renderAdvancedSettings
const rowRegex = /    const Row = \({ label, hint, children }\) => \(\s*<div className="flex items-center justify-between gap-2">\s*<div className="min-w-0">\s*<Label className="text-xs md:text-\[10px\] font-medium text-muted-foreground leading-tight">{label}<\/Label>\s*{hint && <p className="text-\[9px\] md:text-\[8px\] text-muted-foreground\/50 mt-0.5">{hint}<\/p>}\s*<\/div>\s*{children}\s*<\/div>\s*\)\n/
content = content.replace(rowRegex, '')

// Add Row outside BatchHeader
const rowDefinition = `const Row = ({ label, hint, children }) => (
  <div className="flex items-center justify-between gap-2">
    <div className="min-w-0">
      <Label className="text-xs md:text-[10px] font-medium text-muted-foreground leading-tight">{label}</Label>
      {hint && <p className="text-[9px] md:text-[8px] text-muted-foreground/50 mt-0.5">{hint}</p>}
    </div>
    {children}
  </div>
)

const BatchHeader = ({`
content = content.replace('const BatchHeader = ({', rowDefinition)

fs.writeFileSync('gui/frontend/src/components/batch/BatchHeader.jsx', content)
console.log('Moved Row outside')
