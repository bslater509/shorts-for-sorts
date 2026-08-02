const WORKER_OPTIONS = [1, 2, 3, 4, 6, 8]
const current = 1
const ensureOption = (current, options) => {
    const str = String(current)
    return options.includes(str) ? options : [str, ...options]
}
console.log(ensureOption(current, WORKER_OPTIONS))
