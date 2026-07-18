import React, { useState } from 'react';
import { useAppStore } from '../store/useAppStore';
import { previewAnimation } from '../lib/api';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { Slider } from '../components/ui/slider';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Input } from '../components/ui/input';
import { Play, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';
import { Switch } from '../components/ui/switch';

export default function Playground() {
  const { settings, updateSettings } = useAppStore();
  const [videoUrl, setVideoUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [testWord, setTestWord] = useState('Awesome');
  const [testEmoji, setTestEmoji] = useState('🚀');

  const handleGenerate = async () => {
    setIsLoading(true);
    try {
      const url = await previewAnimation(settings, testWord, testEmoji);
      setVideoUrl(url);
    } catch (e) {
      alert(e.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col md:flex-row h-full animate-in fade-in slide-in-from-bottom-4 duration-500 overflow-hidden">
      <div className="w-full md:w-96 border-b md:border-b-0 md:border-r bg-card/50 backdrop-blur-sm p-6 overflow-y-auto shrink-0">
        <h2 className="text-xl font-bold mb-6 text-primary flex items-center gap-2">
          <Play className="w-5 h-5" /> Animation Playground
        </h2>

        <div className="space-y-6">
          <div className="space-y-2">
            <Label>Test Word</Label>
            <Input value={testWord} onChange={e => setTestWord(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>Test Emoji</Label>
            <Input value={testEmoji} onChange={e => setTestEmoji(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label>Subtitle Animation Style</Label>
            <Select 
              value={settings.sub_animation_style || "tiktok_pop"} 
              onValueChange={v => updateSettings({ sub_animation_style: v })}
            >
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="tiktok_pop">TikTok Pop</SelectItem>
                <SelectItem value="karaoke_sweep">Karaoke Sweep</SelectItem>
                <SelectItem value="bouncy_bounce">Bouncy Bounce</SelectItem>
                <SelectItem value="cinematic_zoom">Cinematic Zoom</SelectItem>
                <SelectItem value="glow_shake">Glow Shake</SelectItem>
                <SelectItem value="neon_flicker">Neon Flicker</SelectItem>
                <SelectItem value="pulse_grow">Pulse Grow</SelectItem>
                <SelectItem value="fade_in_slide">Fade-in Slide</SelectItem>
                <SelectItem value="typewriter_swipe">Typewriter Swipe</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Enable Emoji Animation</Label>
              <Switch 
                checked={settings.enable_emoji_animation ?? true}
                onCheckedChange={v => updateSettings({ enable_emoji_animation: v })}
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between">
              <Label>Throw Speed Multiplier</Label>
              <span className="text-xs text-muted-foreground">{settings.emoji_throw_speed_multiplier?.toFixed(1) || "1.0"}x</span>
            </div>
            <Slider
              min={0.1} max={3.0} step={0.1}
              value={[settings.emoji_throw_speed_multiplier ?? 1.0]}
              onValueChange={([v]) => updateSettings({ emoji_throw_speed_multiplier: v })}
            />
          </div>

          <div className="space-y-2">
            <div className="flex justify-between">
              <Label>Throw Arc Height</Label>
              <span className="text-xs text-muted-foreground">{settings.emoji_throw_arc_height?.toFixed(1) || "25.0"}</span>
            </div>
            <Slider
              min={0} max={200} step={5}
              value={[settings.emoji_throw_arc_height ?? 25.0]}
              onValueChange={([v]) => updateSettings({ emoji_throw_arc_height: v })}
            />
          </div>

          <div className="space-y-2">
            <div className="flex justify-between">
              <Label>Throw Fall Distance</Label>
              <span className="text-xs text-muted-foreground">{settings.emoji_throw_fall_distance?.toFixed(1) || "150.0"}</span>
            </div>
            <Slider
              min={0} max={500} step={10}
              value={[settings.emoji_throw_fall_distance ?? 153.6]}
              onValueChange={([v]) => updateSettings({ emoji_throw_fall_distance: v })}
            />
          </div>

          <div className="space-y-2">
            <div className="flex justify-between">
              <Label>Spin Speed</Label>
              <span className="text-xs text-muted-foreground">{settings.emoji_spin_speed?.toFixed(1) || "45.0"}°/s</span>
            </div>
            <Slider
              min={0} max={360} step={5}
              value={[settings.emoji_spin_speed ?? 45.0]}
              onValueChange={([v]) => updateSettings({ emoji_spin_speed: v })}
            />
          </div>

          <Button onClick={handleGenerate} disabled={isLoading} className="w-full relative overflow-hidden group">
            <div className="absolute inset-0 bg-gradient-to-r from-primary/20 to-primary/0 translate-x-[-100%] group-hover:translate-x-[100%] transition-transform duration-1000" />
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Play className="w-4 h-4 mr-2" />}
            Render Preview
          </Button>
        </div>
      </div>

      <div className="flex-1 p-8 flex flex-col items-center justify-center bg-zinc-950/50">
        <div className="w-[360px] h-[640px] bg-black rounded-2xl shadow-2xl border border-zinc-800 overflow-hidden flex items-center justify-center relative shadow-primary/10">
          {videoUrl ? (
            <video 
              src={videoUrl} 
              autoPlay 
              loop 
              controls 
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="text-zinc-600 flex flex-col items-center gap-4">
              <Play className="w-12 h-12 opacity-50" />
              <p>Click "Render Preview" to test</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
