#!/bin/bash
cd /root/shorts-for-sorts/videos || exit 1

for f in *.mp4; do
    if [ ! -f "$f" ]; then continue; fi
    # Get dimensions
    dims=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$f" | head -n 1)
    if [ -z "$dims" ]; then continue; fi
    
    width=$(echo $dims | cut -d'x' -f1)
    height=$(echo $dims | cut -d'x' -f2)
    
    # Check if either dimension is > 720
    if [ "$width" -gt 720 ] && [ "$height" -gt 720 ]; then
        echo "Downscaling $f (${width}x${height}) to 720p..."
        # if width > height, scale height to 720. if height > width, scale width to 720.
        ffmpeg -y -i "$f" -vf "scale='if(gt(iw,ih),-2,720)':'if(gt(iw,ih),720,-2)'" -c:v libx264 -preset fast -crf 23 -c:a copy "tmp_$f" </dev/null
        if [ $? -eq 0 ]; then
            mv "tmp_$f" "$f"
            echo "Successfully downscaled $f"
        else
            echo "Failed to downscale $f"
            rm -f "tmp_$f"
        fi
    fi
done
echo "Downscaling complete."
