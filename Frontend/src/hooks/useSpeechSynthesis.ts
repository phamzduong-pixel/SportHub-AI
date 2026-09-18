import { useCallback, useEffect, useRef, useState } from 'react';
import { cleanSpeechText } from '../utils/cleanSpeechText';

export interface UseSpeechSynthesisOptions {
  lang?: string;
  rate?: number;
  pitch?: number;
  volume?: number;
  onEnd?: () => void;
  onError?: (error: unknown) => void;
}

/* ------------------------------------------------------------------ */
/*  Tiny helpers                                                       */
/* ------------------------------------------------------------------ */

/** Chrome caps a single utterance at ~15 s of audio.  We chunk text so
 *  each piece is short enough to stay below the limit.  */
const CHUNK_MAX_CHARS = 180;

function splitIntoChunks(text: string): string[] {
  if (text.length <= CHUNK_MAX_CHARS) return [text];

  const chunks: string[] = [];
  // Split by sentence-ending punctuation first
  const sentences = text.split(/(?<=[.!?;:])\s+/);
  let current = '';

  for (const sentence of sentences) {
    if (current.length + sentence.length + 1 > CHUNK_MAX_CHARS && current) {
      chunks.push(current.trim());
      current = '';
    }
    current += (current ? ' ' : '') + sentence;
  }
  if (current.trim()) chunks.push(current.trim());

  // If any chunk is still too long, hard-split on word boundaries
  const finalChunks: string[] = [];
  for (const chunk of chunks) {
    if (chunk.length <= CHUNK_MAX_CHARS) {
      finalChunks.push(chunk);
    } else {
      const words = chunk.split(/\s+/);
      let buf = '';
      for (const w of words) {
        if (buf.length + w.length + 1 > CHUNK_MAX_CHARS && buf) {
          finalChunks.push(buf.trim());
          buf = '';
        }
        buf += (buf ? ' ' : '') + w;
      }
      if (buf.trim()) finalChunks.push(buf.trim());
    }
  }

  return finalChunks.length > 0 ? finalChunks : [text];
}

/* ------------------------------------------------------------------ */
/*  Voice selection – pick the best Vietnamese voice available          */
/* ------------------------------------------------------------------ */

function pickBestVoice(voices: SpeechSynthesisVoice[], targetLang: string): SpeechSynthesisVoice | null {
  if (!voices || voices.length === 0) return null;

  const normTarget = targetLang.toLowerCase().replace('_', '-');
  const langPrefix = normTarget.split('-')[0]; // 'vi'

  // Score each voice – higher is better
  const scored = voices
    .map((v) => {
      const vLang = (v.lang || '').toLowerCase().replace('_', '-');
      const vName = (v.name || '').toLowerCase();
      let score = 0;

      // Language match
      if (vLang === normTarget) score += 100;          // vi-vn exact
      else if (vLang.startsWith(langPrefix + '-')) score += 80;   // vi-*
      else if (vLang === langPrefix) score += 70;      // vi

      // Name hints for Vietnamese
      if (vName.includes('tiếng việt')) score += 50;
      else if (vName.includes('vietnamese')) score += 45;
      else if (vName.includes('vietnam')) score += 40;
      else if (vName.includes('hoaimy')) score += 35;
      else if (vName.includes('namminh')) score += 30;

      // Prefer Google / Microsoft / natural voices (usually higher quality)
      if (vName.includes('google')) score += 20;
      else if (vName.includes('microsoft')) score += 15;
      else if (vName.includes('natural')) score += 10;

      // Prefer non-local (network) voices – they tend to sound better
      if (!v.localService) score += 5;

      return { voice: v, score };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score);

  if (scored.length > 0) {
    return scored[0].voice;
  }

  // Fallback: default voice or first available
  return voices.find((v) => v.default) || voices[0] || null;
}

/* ------------------------------------------------------------------ */
/*  The hook                                                           */
/* ------------------------------------------------------------------ */

export function useSpeechSynthesis({
  lang = 'vi-VN',
  rate = 1.0,
  pitch = 1.0,
  volume = 1.0,
  onEnd,
  onError,
}: UseSpeechSynthesisOptions = {}) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speakingId, setSpeakingId] = useState<string | number | null>(null);
  const [isSupported, setIsSupported] = useState(true);
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);

  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const chunkQueueRef = useRef<string[]>([]);
  const currentIdRef = useRef<string | number | null>(null);
  const onEndRef = useRef(onEnd);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onEndRef.current = onEnd;
    onErrorRef.current = onError;
  }, [onEnd, onError]);

  // ---- voice loading ----
  const loadVoices = useCallback(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    try {
      const v = window.speechSynthesis.getVoices();
      if (v && v.length > 0) {
        setAvailableVoices(v);
        console.log('[TTS] voices loaded:', v.length);
      }
    } catch (err) {
      console.warn('[TTS] getVoices error:', err);
    }
  }, []);

  useEffect(() => {
    const ok =
      typeof window !== 'undefined' &&
      'speechSynthesis' in window &&
      'SpeechSynthesisUtterance' in window;
    setIsSupported(ok);

    if (ok) {
      loadVoices();
      // Chrome fires 'voiceschanged' when voices finish downloading
      window.speechSynthesis.addEventListener('voiceschanged', loadVoices);
    }

    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        try { window.speechSynthesis.removeEventListener('voiceschanged', loadVoices); } catch { /* noop */ }
      }
    };
  }, [loadVoices]);

  // ---- heartbeat: Chrome silently pauses after ~15 s ----
  useEffect(() => {
    if (isSpeaking) {
      heartbeatRef.current = window.setInterval(() => {
        try {
          const synth = window.speechSynthesis;
          if (synth.speaking && synth.paused) synth.resume();
        } catch { /* noop */ }
      }, 5_000);
    } else if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
    return () => {
      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
    };
  }, [isSpeaking]);

  // ---- stop ----
  const stop = useCallback(() => {
    chunkQueueRef.current = [];
    currentIdRef.current = null;
    try { window.speechSynthesis.cancel(); } catch { /* noop */ }
    setIsSpeaking(false);
    setSpeakingId(null);
    utteranceRef.current = null;
    try { delete (window as unknown as Record<string, unknown>).__sporthub_tts_utterance; } catch { /* noop */ }
  }, []);

  // ---- internal: speak a single chunk ----
  const speakChunk = useCallback(
    (
      text: string,
      voice: SpeechSynthesisVoice | null,
      targetLang: string,
      vol: number,
      spRate: number,
      spPitch: number,
      id: string | number | null | undefined,
      customOnEnd?: () => void,
      customOnError?: (e: unknown) => void,
    ) => {
      const synth = window.speechSynthesis;

      const utt = new SpeechSynthesisUtterance(text);
      utt.volume = vol;
      utt.rate = spRate;
      utt.pitch = spPitch;

      if (voice) {
        utt.voice = voice;
        utt.lang = voice.lang || targetLang;
      } else {
        utt.lang = targetLang;
      }

      utt.onstart = () => {
        console.log('[TTS] ▶ chunk start');
        setIsSpeaking(true);
        setSpeakingId(id ?? null);
      };

      utt.onend = () => {
        console.log('[TTS] ■ chunk end, remaining:', chunkQueueRef.current.length);
        // Play next chunk in queue
        const next = chunkQueueRef.current.shift();
        if (next && currentIdRef.current === id) {
          speakChunk(next, voice, targetLang, vol, spRate, spPitch, id, customOnEnd, customOnError);
        } else {
          // All chunks done
          setIsSpeaking(false);
          setSpeakingId(null);
          utteranceRef.current = null;
          try { delete (window as unknown as Record<string, unknown>).__sporthub_tts_utterance; } catch { /* noop */ }
          onEndRef.current?.();
          customOnEnd?.();
        }
      };

      utt.onerror = (ev) => {
        // 'canceled' / 'interrupted' are expected when user clicks stop
        if (ev.error === 'canceled' || ev.error === 'interrupted') {
          console.log('[TTS] cancelled/interrupted');
        } else {
          console.warn('[TTS] error:', ev.error);
          onErrorRef.current?.(ev);
          customOnError?.(ev);
        }
        // Clean up regardless
        chunkQueueRef.current = [];
        setIsSpeaking(false);
        setSpeakingId(null);
        utteranceRef.current = null;
        try { delete (window as unknown as Record<string, unknown>).__sporthub_tts_utterance; } catch { /* noop */ }
      };

      // Keep a strong reference so GC doesn't kill it mid-speech
      utteranceRef.current = utt;
      (window as unknown as Record<string, unknown>).__sporthub_tts_utterance = utt;

      synth.speak(utt);

      // Chrome sometimes needs a nudge
      if (synth.paused) synth.resume();
    },
    [],
  );

  // ---- public: speak ----
  const speak = useCallback(
    (rawText: string, id?: string | number, customOptions?: UseSpeechSynthesisOptions) => {
      if (!isSupported || typeof window === 'undefined' || !('speechSynthesis' in window)) {
        console.warn('[TTS] not supported');
        return;
      }

      const cleaned = cleanSpeechText(rawText);
      console.log('[TTS] speak() called, text length:', cleaned.length);
      if (!cleaned) {
        console.warn('[TTS] empty after clean, raw:', rawText?.slice(0, 80));
        return;
      }

      const synth = window.speechSynthesis;

      // -------- CRITICAL: cancel any ongoing speech synchronously --------
      // This MUST happen inside the click handler stack (no setTimeout)
      // so Chrome still counts it as "user gesture".
      try { synth.cancel(); } catch { /* noop */ }

      // Immediately update UI
      setIsSpeaking(true);
      setSpeakingId(id ?? null);
      currentIdRef.current = id ?? null;

      const targetLang = customOptions?.lang || lang || 'vi-VN';
      const vol = customOptions?.volume ?? volume ?? 1.0;
      const spRate = customOptions?.rate ?? rate ?? 1.0;
      const spPitch = customOptions?.pitch ?? pitch ?? 1.0;

      // Pick voice
      const voices =
        availableVoices.length > 0 ? availableVoices : synth.getVoices() || [];
      const voice = pickBestVoice(voices, targetLang);
      if (voice) {
        console.log('[TTS] voice:', voice.name, `(${voice.lang})`);
      } else {
        console.log('[TTS] no matching voice, using lang:', targetLang);
      }

      // Chunk the text to avoid Chrome's 15-sec silence bug
      const chunks = splitIntoChunks(cleaned);
      console.log('[TTS] chunks:', chunks.length);

      // Store remaining chunks (skip first, we speak it immediately)
      chunkQueueRef.current = chunks.slice(1);

      // -------- Speak the first chunk synchronously (user gesture!) --------
      speakChunk(
        chunks[0],
        voice,
        targetLang,
        vol,
        spRate,
        spPitch,
        id,
        customOptions?.onEnd,
        customOptions?.onError,
      );
    },
    [isSupported, lang, volume, rate, pitch, availableVoices, speakChunk],
  );

  // ---- toggle ----
  const toggle = useCallback(
    (rawText: string, id?: string | number, customOptions?: UseSpeechSynthesisOptions) => {
      if (
        isSpeaking &&
        (id === undefined || (speakingId !== null && String(speakingId) === String(id)))
      ) {
        stop();
      } else {
        speak(rawText, id, customOptions);
      }
    },
    [isSpeaking, speakingId, speak, stop],
  );

  return {
    isSpeaking,
    speakingId,
    isSupported,
    availableVoices,
    speak,
    stop,
    toggle,
    cleanText: cleanSpeechText,
  };
}
