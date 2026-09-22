import { useCallback, useEffect, useRef, useState } from 'react';
import { cleanSpeechText } from '../utils/cleanSpeechText.ts';

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

/** Chrome caps a single utterance at ~15 s of audio. We chunk text so
 * each piece is short enough to stay below the limit. */
const CHUNK_MAX_CHARS = 180;
const MOBILE_CHUNK_PAUSE_MS = 45;

/**
 * Split text into chunks suitable for TTS speech synthesis.
 * Uses cross-browser compatible regex (avoiding lookbehinds which crash on Safari/WebKit).
 */
export function splitIntoChunks(text: string): string[] {
  if (!text) return [];
  if (text.length <= CHUNK_MAX_CHARS) return [text];

  // Match sentences ending with punctuation (. ! ? ; :) or end of text.
  // Avoid lookbehind (?<=...) for cross-browser Safari / iOS WebKit compatibility.
  const sentenceMatches = text.match(/[^.!?;:]+([.!?;:]+|$)/g);
  const sentences = sentenceMatches && sentenceMatches.length > 0
    ? sentenceMatches.map((s) => s.trim()).filter(Boolean)
    : [text];

  const chunks: string[] = [];
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

function getVoiceDebugInfo(voices: SpeechSynthesisVoice[]) {
  return voices.map((voice, index) => ({
    index,
    name: voice.name || '',
    lang: voice.lang || '',
    default: Boolean(voice.default),
  }));
}

function logVoiceInventory(voices: SpeechSynthesisVoice[], source: string): void {
  const details = getVoiceDebugInfo(voices);
  const viVoices = details.filter((voice) => /^vi(?:-|$)/i.test(voice.lang));
  const minhVoices = details.filter((voice) => voice.name.toLowerCase().includes('minh'));

  console.log('[TTS] voice inventory source:', source);
  console.log('[TTS] all speechSynthesis voices:', details);
  console.log('[TTS] vi-related voices:', viVoices);
  console.log('[TTS] Minh/Nam Minh candidates:', minhVoices);
}
export function pickBestVoice(
  voices: SpeechSynthesisVoice[],
  targetLang: string,
  options: { preferMinh?: boolean } = {},
): SpeechSynthesisVoice | null {
  if (!voices || voices.length === 0) return null;

  const normTarget = targetLang.toLowerCase().replace('_', '-');
  const langPrefix = normTarget.split('-')[0]; // 'vi'
  const preferMinh = options.preferMinh === true && langPrefix === 'vi';

  // Score each voice – higher is better
  const scored = voices
    .map((v) => {
      const vLang = (v.lang || '').toLowerCase().replace('_', '-');
      const vName = (v.name || '').toLowerCase();
      let score = 0;
      let languageMatches = false;
      let languageRank = 0;

      // Locale priority stays vi-VN -> vi-* -> vi.
      if (vLang === normTarget) {
        score += 100; // vi-vn exact
        languageRank = 3;
        languageMatches = true;
      } else if (vLang.startsWith(langPrefix + '-')) {
        score += 80; // vi-*
        languageRank = 2;
        languageMatches = true;
      } else if (vLang === langPrefix) {
        score += 70; // vi
        languageRank = 1;
        languageMatches = true;
      }
      // Name hints for Vietnamese
      if (vName.includes('tiếng việt')) score += 50;
      else if (vName.includes('vietnamese')) score += 45;
      else if (vName.includes('vietnam')) score += 40;
      else if (vName.includes('hoaimy')) score += 35;
      else if (vName.includes('namminh')) score += 30;
      if (preferMinh && vName.includes('minh')) score += 60;

      // Prefer Google / Microsoft / natural voices (usually higher quality)
      if (vName.includes('google')) score += 20;
      else if (vName.includes('microsoft')) score += 15;
      else if (vName.includes('natural')) score += 10;

      // Prefer non-local (network) voices – they tend to sound better
      if (!v.localService) score += 5;

      return { voice: v, score, languageMatches, languageRank };
    })
    .filter((x) => x.languageMatches)
    .sort((a, b) => {
      if (preferMinh && b.languageRank !== a.languageRank) {
        return b.languageRank - a.languageRank;
      }
      return b.score - a.score;
    });
  if (preferMinh) {
    const bestLanguageRank = scored.reduce(
      (best, candidate) => Math.max(best, candidate.languageRank),
      0,
    );
    const bestLocaleCandidates = scored.filter(
      (candidate) => candidate.languageRank === bestLanguageRank,
    );
    const minhVoice = bestLocaleCandidates.find((candidate) =>
      candidate.voice.name.toLowerCase().includes('minh'),
    );

    if (minhVoice) {
      return minhVoice.voice;
    }

    console.warn('[TTS] Minh/Nam Minh voice is not available for target:', normTarget);
    return null;
  }

  if (scored.length > 0) {
    return scored[0].voice;
  }
  // Do not fall back to an unrelated voice for Vietnamese or English.
  // Mobile browsers commonly expose voices asynchronously; leaving the voice
  // unset while keeping utt.lang lets the browser resolve the requested locale.
  if (langPrefix === 'vi' || langPrefix === 'en') return null;

  // Fallback for non-language-specific/custom callers.
  return voices.find((v) => v.default) || voices[0] || null;
}

const ENGLISH_TERMS = [
  'sporthub',
  'sport',
  'sports',
  'football',
  'badminton',
  'pickleball',
  'basketball',
  'tennis',
  'volleyball',
  'ai',
  'assistant',
  'booking',
  'book',
  'court',
  'slot',
  'available',
  'support',
  'find',
  'help',
  'hello',
  'world',
  'the',
  'this',
  'that',
  'is',
  'and',
  'or',
  'to',
  'for',
  'with',
  'your',
  'you',
  'can',
  'good',
  'morning',
  'sentence',
  'english',
  'language',
  'welcome',
  'please',
  'thank',
  'thanks',
  'need',
  'want',
  'have',
  'what',
  'how',
  'where',
] as const;

const ENGLISH_TERM_SET = new Set<string>(ENGLISH_TERMS);
const VIETNAMESE_SIGNAL_PATTERN = /[À-ɏḀ-ỿ]/;

function looksLikeEnglishText(text: string): boolean {
  if (!text || VIETNAMESE_SIGNAL_PATTERN.test(text)) return false;

  const words = text.match(/[A-Za-z]+(?:['-][A-Za-z]+)*/g) || [];
  if (words.length === 0) return false;

  return words.some((word) => ENGLISH_TERM_SET.has(word.toLowerCase()));
}

/**
 * Select one language for the whole mobile utterance. Mixed Vietnamese +
 * English remains Vietnamese so it stays one continuous conversational utterance.
 */
export function detectMobileSpeechLanguage(text: string, targetLang = 'vi-VN'): string {
  const normalizedTarget = targetLang.toLowerCase().replace('_', '-');
  if (!normalizedTarget.startsWith('vi')) return targetLang;
  return looksLikeEnglishText(text) ? 'en-US' : targetLang;
}

/**
 * Keep punctuation in the utterance so Web Speech can turn it into pauses.
 * Only normalize whitespace around punctuation; never create punctuation-only
 * utterances, which some mobile voices may pronounce as "chấm"/"phẩy".
 */
export function normalizeMobileSpeechText(text: string): string {
  return text
    .replace(/\s+/g, ' ')
    .replace(/\s+([.!?,;:])/g, '$1')
    .trim();
}
export function isLikelyMobileSpeechDevice(): boolean {
  if (typeof navigator === 'undefined') return false;
  return /Android|webOS|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || '');
}

/* ------------------------------------------------------------------ */
/*  The hook                                                           */
/* ------------------------------------------------------------------ */

export function useSpeechSynthesis({
  lang = 'vi-VN',
  rate,
  pitch = 1.0,
  volume = 1.0,
  onEnd,
  onError,
}: UseSpeechSynthesisOptions = {}) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speakingId, setSpeakingId] = useState<string | number | null>(null);
  const [isSupported, setIsSupported] = useState(() => {
    return (
      typeof window !== 'undefined' &&
      'speechSynthesis' in window &&
      'SpeechSynthesisUtterance' in window &&
      Boolean(window.speechSynthesis) &&
      Boolean(window.SpeechSynthesisUtterance)
    );
  });
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);

  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const chunkQueueRef = useRef<string[]>([]);
  const currentIdRef = useRef<string | number | null>(null);
  const onEndRef = useRef(onEnd);
  const onErrorRef = useRef(onError);
  const voiceRetryTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    onEndRef.current = onEnd;
    onErrorRef.current = onError;
  }, [onEnd, onError]);

  // ---- voice loading ----
  const loadVoices = useCallback(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window) || !window.speechSynthesis) {
      return false;
    }

    try {
      if (typeof window.speechSynthesis.getVoices !== 'function') return false;
      const v = window.speechSynthesis.getVoices();
      logVoiceInventory(v, 'getVoices()/voice loading');
      if (v && v.length > 0) {
        setAvailableVoices(v);
        if (voiceRetryTimeoutRef.current !== null) {
          clearTimeout(voiceRetryTimeoutRef.current);
          voiceRetryTimeoutRef.current = null;
        }
        console.log('[TTS] voices loaded:', v.length);
        return true;
      }
    } catch (err) {
      console.warn('[TTS] getVoices error:', err);
    }

    return false;
  }, []);

  useEffect(() => {
    const ok =
      typeof window !== 'undefined' &&
      'speechSynthesis' in window &&
      'SpeechSynthesisUtterance' in window &&
      Boolean(window.speechSynthesis) &&
      Boolean(window.SpeechSynthesisUtterance);
    setIsSupported(ok);

    if (!ok || !window.speechSynthesis) return undefined;

    let disposed = false;
    let retryCount = 0;
    const retryLoadVoices = () => {
      if (disposed) return;
      const loaded = loadVoices();
      if (!loaded && retryCount < 20) {
        retryCount += 1;
        voiceRetryTimeoutRef.current = window.setTimeout(retryLoadVoices, 250);
      }
    };

    retryLoadVoices();

    try {
      if (typeof window.speechSynthesis.addEventListener === 'function') {
        window.speechSynthesis.addEventListener('voiceschanged', loadVoices);
      } else {
        window.speechSynthesis.onvoiceschanged = loadVoices;
      }
    } catch {
      /* noop */
    }

    return () => {
      disposed = true;
      if (voiceRetryTimeoutRef.current !== null) {
        clearTimeout(voiceRetryTimeoutRef.current);
        voiceRetryTimeoutRef.current = null;
      }
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        try {
          if (typeof window.speechSynthesis.removeEventListener === 'function') {
            window.speechSynthesis.removeEventListener('voiceschanged', loadVoices);
          } else {
            window.speechSynthesis.onvoiceschanged = null;
          }
        } catch {
          /* noop */
        }
      }
    };
  }, [loadVoices]);
  // ---- heartbeat: Chrome silently pauses after ~15 s ----
  useEffect(() => {
    if (isSpeaking) {
      heartbeatRef.current = window.setInterval(() => {
        try {
          const synth = window.speechSynthesis;
          if (synth && synth.speaking && synth.paused) synth.resume();
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
    try {
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    } catch { /* noop */ }
    setIsSpeaking(false);
    setSpeakingId(null);
    utteranceRef.current = null;
    try { (window as unknown as Record<string, unknown>).__sporthub_tts_utterance = null; } catch { /* noop */ }
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
      isMobileSpeech = false,
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
        console.log('[TTS] chunk start');
        setIsSpeaking(true);
        setSpeakingId(id ?? null);
      };

      utt.onend = () => {
        console.log('[TTS] chunk end, remaining:', chunkQueueRef.current.length);
        const next = chunkQueueRef.current.shift();
        const isCurrentSpeech = currentIdRef.current === (id ?? null);

        if (next && isCurrentSpeech) {
          const speakNextChunk = () => {
            if (currentIdRef.current !== (id ?? null)) return;
            speakChunk(
              next,
              voice,
              targetLang,
              vol,
              spRate,
              spPitch,
              id,
              customOnEnd,
              customOnError,
              isMobileSpeech,
            );
          };

          // Keep mobile chunks continuous while allowing punctuation in the
          // previous utterance to finish naturally.
          if (isMobileSpeech) {
            window.setTimeout(speakNextChunk, MOBILE_CHUNK_PAUSE_MS);
          } else {
            speakNextChunk();
          }
        } else {
          setIsSpeaking(false);
          setSpeakingId(null);
          utteranceRef.current = null;
          try { (window as unknown as Record<string, unknown>).__sporthub_tts_utterance = null; } catch { /* noop */ }
          onEndRef.current?.();
          customOnEnd?.();
        }
      };

      utt.onerror = (ev) => {
        if (ev.error === 'canceled' || ev.error === 'interrupted') {
          console.log('[TTS] cancelled/interrupted');
        } else {
          console.warn('[TTS] error:', ev.error);
          onErrorRef.current?.(ev);
          customOnError?.(ev);
        }
        chunkQueueRef.current = [];
        setIsSpeaking(false);
        setSpeakingId(null);
        utteranceRef.current = null;
        try { (window as unknown as Record<string, unknown>).__sporthub_tts_utterance = null; } catch { /* noop */ }
      };

      utteranceRef.current = utt;
      (window as unknown as Record<string, unknown>).__sporthub_tts_utterance = utt;

      console.log('[TTS] utterance before synth.speak:', {
        lang: utt.lang,
        voiceName: utt.voice?.name ?? null,
        voiceLang: utt.voice?.lang ?? null,
      });
      synth.speak(utt);
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
      const isMobileSpeech = isLikelyMobileSpeechDevice();
      const speechText = isMobileSpeech
        ? normalizeMobileSpeechText(cleaned)
        : cleaned;
      const vol = customOptions?.volume ?? volume ?? 1.0;
      const spRate = customOptions?.rate ?? (
        isMobileSpeech ? (rate ?? 1.08) : (rate ?? 1.0)
      );
      const spPitch = customOptions?.pitch ?? pitch ?? 1.0;

      // Resolve one voice for the complete speech. Mixed Vietnamese + English
      // stays one Vietnamese utterance so words are not read as isolated tokens.
      const runtimeVoices = synth.getVoices() || [];
      logVoiceInventory(runtimeVoices, 'speak() runtime getVoices');
      const voices = runtimeVoices.length > 0 ? runtimeVoices : availableVoices;
      const speechLang = isMobileSpeech
        ? detectMobileSpeechLanguage(speechText, targetLang)
        : targetLang;
      const chunks = splitIntoChunks(speechText);
      const voice = pickBestVoice(voices, speechLang, { preferMinh: isMobileSpeech });

      console.log('[TTS] voice selection:', {
        targetLang,
        speechLang,
        selectedVoiceName: voice?.name ?? null,
        selectedVoiceLang: voice?.lang ?? null,
        selectedVoiceDefault: voice?.default ?? null,
        preferredMobileVoice: isMobileSpeech && speechLang.toLowerCase().startsWith('vi')
          ? 'Minh/Nam Minh'
          : null,
      });
      if (!voice) {
        console.warn('[TTS] no explicit voice selected; utterance will use lang only:', speechLang);
      }
      console.log('[TTS] chunks:', chunks.length);
      chunkQueueRef.current = chunks.slice(1);

      // Speak the first chunk synchronously (preserves the user gesture).
      speakChunk(
        chunks[0],
        voice,
        speechLang,
        vol,
        spRate,
        spPitch,
        id,
        customOptions?.onEnd,
        customOptions?.onError,
        isMobileSpeech,
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
