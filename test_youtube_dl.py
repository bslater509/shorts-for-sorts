import subprocess

cmd = ["yt-dlp", "--newline", "ytsearch1:test", "-o", "temp/test_yt.mp4"]
process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
for line in process.stdout:
    print("LOG:", line.strip())
process.wait()
