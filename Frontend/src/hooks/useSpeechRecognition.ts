import { useCallback, useEffect, useRef, useState } from 'react';

// Browser Web Speech API type definitions
interface ISpeechRecognitionEvent extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}

interface ISpeechRecognitionErrorEvent extends Event {
  error: string;
  message?: string;
}

interface ISpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: ((this: ISpeechRecognition, ev: Event) => void) | null;
  onend: ((this: ISpeechRecognition, ev: Event) => void) | null;
  onerror: ((this: ISpeechRecognition, ev: ISpeechRecognitionErrorEvent) => void) | null;
  onresult: ((this: ISpeechRecognition, ev: ISpeechRecognitionEvent) => void) | null;
}

interface ISpeechRecognitionConstructor {
  new (): ISpeechRecognition;
}

declare global {
  interface Window {
    SpeechRecognition?: ISpeechRecognitionConstructor;
    webkitSpeechRecognition?: ISpeechRecognitionConstructor;
  }
}

export interface TranscriptDetail {
  finalTranscript: string;
  interimTranscript: string;
  fullTranscript: string;
}

export interface UseSpeechRecognitionOptions {
  lang?: string;
  continuous?: boolean;
  interimResults?: boolean;
  onTranscriptChange?: (detail: TranscriptDetail) => void;
  onError?: (error: string) => void;
  onEnd?: (finalSessionTranscript: string) => void;
}

export function useSpeechRecognition({
  lang = 'vi-VN',
  continuous = true,
  interimResults = true,
  onTranscriptChange,
  onError,
  onEnd,
}: UseSpeechRecognitionOptions = {}) {
  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [finalTranscript, setFinalTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');

  const recognitionRef = useRef<ISpeechRecognition | null>(null);
  const isManuallyStoppedRef = useRef(false);
  const sessionTranscriptRef = useRef<TranscriptDetail>({
    finalTranscript: '',
    interimTranscript: '',
    fullTranscript: '',
  });

  // Keep latest callbacks in refs to prevent stale closures
  const onTranscriptChangeRef = useRef(onTranscriptChange);
  const onErrorRef = useRef(onError);
  const onEndRef = useRef(onEnd);

  useEffect(() => {
    onTranscriptChangeRef.current = onTranscriptChange;
    onErrorRef.current = onError;
    onEndRef.current = onEnd;
  }, [onTranscriptChange, onError, onEnd]);

  useEffect(() => {
    const SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionClass) {
      setIsSupported(false);
      return;
    }

    try {
      const recognition = new SpeechRecognitionClass();
      recognition.continuous = continuous;
      recognition.interimResults = interimResults;
      recognition.lang = lang;

      recognition.onstart = () => {
        setIsListening(true);
        setErrorMessage(null);
        setFinalTranscript('');
        setInterimTranscript('');
        sessionTranscriptRef.current = {
          finalTranscript: '',
          interimTranscript: '',
          fullTranscript: '',
        };
      };

      recognition.onresult = (event: ISpeechRecognitionEvent) => {
        // If recording was stopped or cancelled by user, ignore trailing results
        if (isManuallyStoppedRef.current) {
          return;
        }

        let finalAccumulator = '';
        let interimAccumulator = '';

        // Iterate through all results in the current session
        for (let i = 0; i < event.results.length; i++) {
          const result = event.results[i];
          const text = result[0]?.transcript?.trim() || '';
          if (!text) continue;

          if (result.isFinal) {
            finalAccumulator = finalAccumulator ? `${finalAccumulator} ${text}` : text;
          } else {
            interimAccumulator = interimAccumulator ? `${interimAccumulator} ${text}` : text;
          }
        }

        const full = [finalAccumulator, interimAccumulator].filter(Boolean).join(' ').trim();

        setFinalTranscript(finalAccumulator);
        setInterimTranscript(interimAccumulator);

        const detail: TranscriptDetail = {
          finalTranscript: finalAccumulator,
          interimTranscript: interimAccumulator,
          fullTranscript: full,
        };

        sessionTranscriptRef.current = detail;

        if (onTranscriptChangeRef.current) {
          onTranscriptChangeRef.current(detail);
        }
      };

      recognition.onerror = (event: ISpeechRecognitionErrorEvent) => {
        // If the user intentionally stopped or cancelled the recording, suppress aborted/no-speech errors
        if (isManuallyStoppedRef.current && (event.error === 'aborted' || event.error === 'no-speech')) {
          setIsListening(false);
          return;
        }

        let message = '';
        switch (event.error) {
          case 'not-allowed':
          case 'service-not-allowed':
            message = 'Quyền truy cập microphone bị từ chối. Vui lòng cấp quyền micro trong trình duyệt.';
            break;
          case 'no-speech':
            message = 'Không nhận diện được giọng nói. Vui lòng nói lại rõ ràng hơn.';
            break;
          case 'audio-capture':
            message = 'Không tìm thấy microphone hoặc thiết bị thu âm đang bận.';
            break;
          case 'network':
            message = 'Lỗi kết nối mạng khi nhận diện giọng nói. Vui lòng kiểm tra lại kết nối.';
            break;
          case 'aborted':
            // Suppress aborted error without user notification
            setIsListening(false);
            return;
          default:
            message = `Lỗi nhận diện giọng nói: ${event.error || 'không xác định'}.`;
            break;
        }

        setErrorMessage(message);
        if (onErrorRef.current) {
          onErrorRef.current(message);
        }
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
        if (!isManuallyStoppedRef.current) {
          const latestDetail = sessionTranscriptRef.current;
          if (onEndRef.current) {
            onEndRef.current(latestDetail.fullTranscript);
          }
        }
      };

      recognitionRef.current = recognition;
    } catch (err) {
      console.warn('SpeechRecognition initialization error:', err);
      setIsSupported(false);
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
        recognitionRef.current = null;
      }
    };
  }, [continuous, interimResults, lang]);

  const startListening = useCallback(() => {
    if (!isSupported) {
      setErrorMessage('Trình duyệt của bạn chưa hỗ trợ nhận diện giọng nói (Web Speech API). Vui lòng dùng Google Chrome hoặc Microsoft Edge.');
      return;
    }
    if (!recognitionRef.current) return;

    try {
      setErrorMessage(null);
      isManuallyStoppedRef.current = false;
      setFinalTranscript('');
      setInterimTranscript('');
      sessionTranscriptRef.current = {
        finalTranscript: '',
        interimTranscript: '',
        fullTranscript: '',
      };
      recognitionRef.current.start();
    } catch (error) {
      console.warn('Error starting speech recognition:', error);
    }
  }, [isSupported]);

  const stopListening = useCallback(() => {
    isManuallyStoppedRef.current = true;
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch (e) {
        console.warn('Error stopping speech recognition:', e);
      }
    }
    setIsListening(false);
  }, []);

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  const resetTranscript = useCallback(() => {
    isManuallyStoppedRef.current = true;
    setFinalTranscript('');
    setInterimTranscript('');
    sessionTranscriptRef.current = {
      finalTranscript: '',
      interimTranscript: '',
      fullTranscript: '',
    };
  }, []);

  const clearError = useCallback(() => {
    setErrorMessage(null);
  }, []);

  return {
    isListening,
    isSupported,
    errorMessage,
    finalTranscript,
    interimTranscript,
    startListening,
    stopListening,
    toggleListening,
    resetTranscript,
    clearError,
  };
}
