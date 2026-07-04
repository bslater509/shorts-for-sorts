import { useState } from 'react'
import { CheckCircle2, ChevronRight, ChevronLeft, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

import ScriptGenerator from '@/components/studio/ScriptGenerator'
import BackgroundMedia from '@/components/studio/BackgroundMedia'
import SubtitlesPresets from '@/components/studio/SubtitlesPresets'
import Compiler from '@/components/studio/Compiler'

const STEPS = [
  { id: 1, title: 'Script' },
  { id: 2, title: 'Media' },
  { id: 3, title: 'Presets' },
  { id: 4, title: 'Compile' },
]

export default function Studio() {
  const [currentStep, setCurrentStep] = useState(1)

  const nextStep = () => setCurrentStep(p => Math.min(p + 1, STEPS.length))
  const prevStep = () => setCurrentStep(p => Math.max(p - 1, 1))

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-5xl mx-auto flex flex-col md:h-[calc(100vh-6rem)] min-h-[calc(100vh-6rem)]">
      <header className="shrink-0">
        <h1 className="text-3xl font-bold tracking-tight">Content Studio</h1>
        <p className="text-muted-foreground mt-1">Generate scripts, select templates, and compile your TikTok Short</p>
      </header>

      {/* Stepper */}
      <div className="flex items-center justify-between relative shrink-0 py-4">
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-full h-0.5 bg-border -z-10" />
        <div 
          className="absolute left-0 top-1/2 -translate-y-1/2 h-0.5 bg-blue-500 -z-10 transition-all duration-500 ease-in-out" 
          style={{ width: `${((currentStep - 1) / (STEPS.length - 1)) * 100}%` }}
        />
        
        {STEPS.map((step) => (
          <div key={step.id} className="flex flex-col items-center gap-2">
            <div className={cn(
              "w-10 h-10 rounded-full flex items-center justify-center font-semibold transition-all duration-300",
              step.id < currentStep ? "bg-blue-500 text-white" : 
              step.id === currentStep ? "bg-blue-500 ring-4 ring-blue-500/20 text-white" : 
              "bg-secondary text-muted-foreground border-2 border-border"
            )}>
              {step.id < currentStep ? <CheckCircle2 size={20} /> : step.id}
            </div>
            <span className={cn(
              "text-xs font-medium uppercase tracking-wider hidden sm:block",
              step.id <= currentStep ? "text-foreground" : "text-muted-foreground"
            )}>{step.title}</span>
          </div>
        ))}
      </div>

      {/* Main Card Content */}
      <div className="bg-card border border-border rounded-xl shadow-sm flex-1 flex flex-col overflow-hidden">
        <div className="p-6 flex-1 overflow-y-auto">
          {currentStep === 1 && <ScriptGenerator />}
          {currentStep === 2 && <BackgroundMedia />}
          {currentStep === 3 && <SubtitlesPresets />}
          {currentStep === 4 && <Compiler />}
        </div>
        
        {/* Footer Actions */}
        <div className="p-4 border-t border-border flex items-center justify-between shrink-0 bg-muted/30">
          <button 
            onClick={prevStep}
            disabled={currentStep === 1}
            className="flex items-center gap-2 px-4 py-2 rounded-md font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed hover:bg-secondary text-foreground"
          >
            <ChevronLeft size={16} />
            Back
          </button>
          
          {currentStep < STEPS.length ? (
            <button 
              onClick={nextStep}
              className="flex items-center gap-2 px-6 py-2 rounded-md font-medium text-sm transition-all bg-blue-500 hover:bg-blue-600 text-white shadow-md shadow-blue-500/20"
            >
              Next Step
              <ChevronRight size={16} />
            </button>
          ) : (
            <button 
              onClick={() => { /* Handled in compile step */ }}
              className="flex items-center gap-2 px-6 py-2 rounded-md font-medium text-sm transition-all bg-emerald-500 hover:bg-emerald-600 text-white shadow-md shadow-emerald-500/20"
            >
              <Sparkles size={16} />
              Compile Ready
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
