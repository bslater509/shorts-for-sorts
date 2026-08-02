const http = require('http');
http.createServer((req, res) => {
  if (req.method === 'POST') {
    let body = '';
    req.on('data', chunk => body += chunk.toString());
    req.on('end', () => {
      console.log('CLIENT ERROR:', body);
      res.end('OK');
    });
  } else {
    res.end('OK');
  }
}).listen(8888, () => console.log('Error server listening on 8888'));
