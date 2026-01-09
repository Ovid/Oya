import { useEffect, useState } from 'react';
import type { ProgressEvent } from '../types';
import { streamJobProgress } from '../api/client';

interface GenerationProgressProps {
  jobId: string;
  onComplete: () => void;
  onError: (error: string) => void;
}

interface PhaseInfo {
  name: string;
  description: string;
}

const PHASES: Record<string, PhaseInfo> = {
  'starting': { name: 'Starting', description: 'Initializing generation...' },
  'analysis': { name: 'Analysis', description: 'Scanning repository and parsing code...' },
  'overview': { name: 'Overview', description: 'Generating project overview page...' },
  'architecture': { name: 'Architecture', description: 'Analyzing and documenting architecture...' },
  'workflows': { name: 'Workflows', description: 'Discovering and documenting workflows...' },
  'directories': { name: 'Directories', description: 'Generating directory documentation...' },
  'files': { name: 'Files', description: 'Generating file-level documentation...' },
};

// Ordered list of phases for progress display
// Note: Files runs before directories to compute content hashes for incremental regen
const PHASE_ORDER = ['analysis', 'overview', 'architecture', 'workflows', 'files', 'directories'];

export function GenerationProgress({ jobId, onComplete, onError }: GenerationProgressProps) {
  const [currentPhase, setCurrentPhase] = useState<string>('starting');
  const [currentPhaseNum, setCurrentPhaseNum] = useState<number>(0);
  const [totalPhases, setTotalPhases] = useState<number>(6);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [totalSteps, setTotalSteps] = useState<number>(0);
  const [startTime] = useState<Date>(new Date());
  const [elapsed, setElapsed] = useState<number>(0);
  const [isComplete, setIsComplete] = useState<boolean>(false);

  // Update elapsed time every second
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime.getTime()) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [startTime]);

  useEffect(() => {
    const cleanup = streamJobProgress(
      jobId,
      (event: ProgressEvent) => {
        // Parse phase info (format: "1:analysis")
        if (event.phase) {
          const [numStr, phaseName] = event.phase.split(':');
          const phaseNum = parseInt(numStr, 10);

          if (phaseName) {
            setCurrentPhase(phaseName);
            setCurrentPhaseNum(phaseNum);
          }
        }

        // Update step tracking
        if (event.current_step !== null && event.current_step !== undefined) {
          setCurrentStep(event.current_step);
        }
        if (event.total_steps !== null && event.total_steps !== undefined) {
          setTotalSteps(event.total_steps);
        }

        if (event.total_phases) {
          setTotalPhases(event.total_phases);
        }
      },
      () => {
        setIsComplete(true);
        onComplete();
      },
      (error: Error) => {
        onError(error.message);
      }
    );

    return cleanup;
  }, [jobId, onComplete, onError]);

  const phaseInfo = PHASES[currentPhase] || { name: currentPhase, description: 'Processing...' };
  const progress = totalPhases > 0 ? (currentPhaseNum / totalPhases) * 100 : 0;
  const elapsedStr = elapsed < 60
    ? `${elapsed}s`
    : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`;

  return (
    <div className="max-w-xl mx-auto py-8">
      {/* Header */}
      <div className="text-center mb-6">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-indigo-100 dark:bg-indigo-900 rounded-full mb-4">
          <svg className="w-8 h-8 text-indigo-600 dark:text-indigo-400 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          Generating Documentation
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Elapsed: {elapsedStr}
        </p>
      </div>

      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400 mb-2">
          <span>Step {currentPhaseNum} of {totalPhases}</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-indigo-600 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Current phase */}
      <div className="bg-indigo-50 dark:bg-indigo-900/20 rounded-lg p-4 mb-6">
        <div className="flex items-center">
          <div className="flex-shrink-0">
            <svg className="w-5 h-5 text-indigo-600 dark:text-indigo-400 animate-pulse" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3 flex-grow">
            <h3 className="text-sm font-medium text-indigo-800 dark:text-indigo-200">
              {phaseInfo.name}
            </h3>
            <p className="text-sm text-indigo-600 dark:text-indigo-300">
              {phaseInfo.description}
            </p>
          </div>
        </div>

        {/* Step progress bar (shown for directories and files phases) */}
        {totalSteps > 0 && (currentPhase === 'directories' || currentPhase === 'files') && (
          <div className="mt-4">
            <div className="flex justify-between text-xs text-indigo-600 dark:text-indigo-300 mb-1">
              <span>{currentPhase === 'directories' ? 'Directory' : 'File'} {currentStep} of {totalSteps}</span>
              <span>{totalSteps > 0 ? Math.round((currentStep / totalSteps) * 100) : 0}%</span>
            </div>
            <div className="h-1.5 bg-indigo-200 dark:bg-indigo-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 dark:bg-indigo-400 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${totalSteps > 0 ? (currentStep / totalSteps) * 100 : 0}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Phase log - shows all phases with their status based on current phase number */}
      {currentPhaseNum > 0 && (
        <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
          <div className="bg-gray-50 dark:bg-gray-800 px-4 py-2 border-b border-gray-200 dark:border-gray-700">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Progress Log</h4>
          </div>
          <ul className="divide-y divide-gray-200 dark:divide-gray-700">
            {PHASE_ORDER.map((phase, index) => {
              const phaseNum = index + 1; // Phases are 1-indexed
              const info = PHASES[phase] || { name: phase };

              // Determine status: completed if phase number < current, in_progress if equal, pending if greater
              let status: 'completed' | 'in_progress' | 'pending';
              if (isComplete || phaseNum < currentPhaseNum) {
                status = 'completed';
              } else if (phaseNum === currentPhaseNum) {
                status = 'in_progress';
              } else {
                status = 'pending';
              }

              // Only show phases that have started or completed
              if (status === 'pending') return null;

              return (
                <li key={phase} className="px-4 py-3 flex items-center justify-between">
                  <div className="flex items-center">
                    {status === 'completed' ? (
                      <svg className="w-4 h-4 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4 text-indigo-500 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                    )}
                    <span className={`text-sm ${status === 'completed' ? 'text-gray-600 dark:text-gray-400' : 'text-gray-900 dark:text-white font-medium'}`}>
                      {info.name}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
