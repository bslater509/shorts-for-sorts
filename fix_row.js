const fs = require('fs')
let content = fs.readFileSync('gui/frontend/src/components/batch/BatchHeader.jsx', 'utf8')

content = content.replace(/const Row = \({ label, hint, children }\) => \(/g, 'const renderRow = (label, hint, children) => (')

// Replace all usages of <Row label="XXX" hint="YYY">...</Row> with {renderRow("XXX", "YYY", ...)}
// This requires a bit of regex logic, or I can just do it using manual replace.
// Actually, it's easier to just move Row outside of BatchHeader!
