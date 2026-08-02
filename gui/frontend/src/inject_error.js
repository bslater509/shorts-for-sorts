window.addEventListener('error', function(event) {
  fetch('http://localhost:8888', { method: 'POST', body: event.error ? event.error.stack : event.message });
});
window.addEventListener('unhandledrejection', function(event) {
  fetch('http://localhost:8888', { method: 'POST', body: event.reason ? event.reason.stack : event.reason });
});
