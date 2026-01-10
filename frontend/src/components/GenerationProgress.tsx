import { useEffect, useState, useRef } from 'react';
import type { ProgressEvent } from '../types';
import { streamJobProgress, cancelJob } from '../api/client';
import { formatElapsedTime, PHASES, PHASE_ORDER } from './generationConstants';

interface GenerationProgressProps {
  jobId: string;
  onComplete: () => void;
  onError: (error: string) => void;
  onCancelled?: () => void;
}

export function GenerationProgress({ jobId, onComplete, onError, onCancelled }: GenerationProgressProps) {
  const [currentPhase, setCurrentPhase] = useState<string>('starting');
  const [currentPhaseNum, setCurrentPhaseNum] = useState<number>(0);
  const [totalPhases, setTotalPhases] = useState<number>(6);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [totalSteps, setTotalSteps] = useState<number>(0);
  const [startTime] = useState<Date>(new Date());
  const [elapsed, setElapsed] = useState<number>(0);
  const [isComplete, setIsComplete] = useState<boolean>(false);
  const [isCancelled, setIsCancelled] = useState<boolean>(false);
  const [showCancelModal, setShowCancelModal] = useState<boolean>(false);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [phaseElapsedTimes, setPhaseElapsedTimes] = useState<Record<string, number>>({});
  const phaseStartTimesRef = useRef<Record<string, number>>({});

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
            setCurrentPhase((prevPhase) => {
              // Record start time for new phase
              if (!(phaseName in phaseStartTimesRef.current)) {
                phaseStartTimesRef.current[phaseName] = Date.now();
              }
              
              // When phase changes, record elapsed time for the previous phase
              if (prevPhase !== 'starting' && prevPhase !== phaseName && prevPhase in phaseStartTimesRef.current) {
                const elapsedForPhase = Math.floor((Date.now() - phaseStartTimesRef.current[prevPhase]) / 1000);
                setPhaseElapsedTimes((prev) => ({
                  ...prev,
                  [prevPhase]: elapsedForPhase,
                }));
              }
              return phaseName;
            });
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
        // Record elapsed time for the final phase on completion
        setCurrentPhase((prevPhase) => {
          if (prevPhase !== 'starting' && prevPhase in phaseStartTimesRef.current) {
            const elapsedForPhase = Math.floor((Date.now() - phaseStartTimesRef.current[prevPhase]) / 1000);
            setPhaseElapsedTimes((prev) => ({
              ...prev,
              [prevPhase]: elapsedForPhase,
            }));
          }
          return prevPhase;
        });
        setIsComplete(true);
        onComplete();
      },
      (error: Error) => {
        onError(error.message);
      },
      () => {
        // Handle cancellation
        setIsCancelled(true);
        if (onCancelled) {
          onCancelled();
        }
      }
    );

    return cleanup;
  }, [jobId, onComplete, onError, onCancelled]);

  const handleCancelClick = () => {
    setShowCancelModal(true);
  };

  const handleConfirmCancel = async () => {
    setIsCancelling(true);
    try {
      await cancelJob(jobId);
      // The SSE stream will handle the cancelled event
    } catch {
      // If cancel fails, just close the modal
      setShowCancelModal(false);
      setIsCancelling(false);
    }
  };

  const handleCancelModalClose = () => {
    if (!isCancelling) {
      setShowCancelModal(false);
    }
  };

  const phaseInfo = PHASES[currentPhase] || { name: currentPhase, description: 'Processing...' };
  const progress = totalPhases > 0 ? (currentPhaseNum / totalPhases) * 100 : 0;
  const elapsedStr = elapsed < 60
    ? `${elapsed}s`
    : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s`;

  // Build cancellation message
  const getCancellationMessage = () => {
    const phaseName = PHASES[currentPhase]?.name || currentPhase;
    if (currentPhase === 'files' && totalSteps > 0) {
      return `Generation was stopped during ${phaseName} phase (file ${currentStep} of ${totalSteps}).`;
    }
    if (currentPhase === 'directories' && totalSteps > 0) {
      return `Generation was stopped during ${phaseName} phase (directory ${currentStep} of ${totalSteps}).`;
    }
    return `Generation was stopped during ${phaseName} phase.`;
  };

  // Show cancelled state
  if (isCancelled) {
    return (
      <div className="max-w-xl mx-auto py-8">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-amber-100 dark:bg-amber-900 rounded-full mb-4">
            <svg className="w-8 h-8 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Generation Stopped
          </h2>
          <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
            {getCancellationMessage()}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto py-8">
      {/* Cancel Confirmation Modal */}
      {showCancelModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/50" onClick={handleCancelModalClose} />
          <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-sm mx-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Stop Generation?
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Are you sure you want to stop the wiki generation? Any progress will be lost and you'll need to start over.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={handleCancelModalClose}
                disabled={isCancelling}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md disabled:opacity-50"
              >
                Keep Going
              </button>
              <button
                onClick={handleConfirmCancel}
                disabled={isCancelling}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md disabled:opacity-50"
              >
                {isCancelling ? 'Stopping...' : 'Stop Generation'}
              </button>
            </div>
          </div>
        </div>
      )}
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

        {/* Step progress bar (shown for phases with step tracking) */}
        {totalSteps > 0 && (
          <div className="mt-4">
            <div className="flex justify-between text-xs text-indigo-600 dark:text-indigo-300 mb-1">
              <span>
                {currentPhase === 'directories' ? 'Directory' : 
                 currentPhase === 'files' ? 'File' : 
                 currentPhase === 'analysis' ? 'File' :
                 currentPhase === 'workflows' ? 'Workflow' : 'Step'} {currentStep} of {totalSteps}
              </span>
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
                  {status === 'completed' && phaseElapsedTimes[phase] !== undefined && (
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      {formatElapsedTime(phaseElapsedTimes[phase])}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Stop Generation button */}
      <div className="mt-6 text-center">
        <button
          onClick={handleCancelClick}
          className="px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md transition-colors"
        >
          Stop Generation
        </button>
      </div>
    </div>
  );
}
